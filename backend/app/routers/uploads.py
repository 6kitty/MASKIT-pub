from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import shutil
import json
from typing import List
import asyncio
import base64
from datetime import datetime,timedelta
import uuid
from app.database.mongodb import get_db
from app.utils.datetime_utils import get_kst_now
from app.models.email import AttachmentData, OriginalEmailData

router = APIRouter()

class FileItem(BaseModel):
    id: str
    name: str
    kind: str
    path: str

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload_email")
async def upload_email(
    from_email: str = Form(...),
    to_email: str = Form(...),
    subject: str = Form(...),
    original_body: str = Form(...),
    attachments: List[UploadFile] = File([]),
    db = Depends(get_db)
):
    print("\n" + "="*80)
    print("📧 이메일 업로드 요청 받음")
    print("="*80)
    print(f"발신자: {from_email}")
    print(f"수신자: {to_email}")
    print(f"제목: {subject}")
    print(f"본문 길이: {len(original_body)} 자")
    print(f"첨부파일: {len(attachments)}개")
    print("="*80 + "\n")

    # 폴더 내용물 삭제 로직
    if os.path.exists(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

    # 이메일 본문 저장 (파일 시스템)
    with open(os.path.join(UPLOAD_DIR, "email_body.txt"), "w", encoding="utf-8") as f:
        f.write(original_body)

    # 실제 수신자와 제목 정보를 json 파일로 저장합니다.
    meta_data = {
        "recipients": [email.strip() for email in to_email.split(',')],
        "subject": subject
    }
    with open(os.path.join(UPLOAD_DIR, "email_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=4)

    # 첨부파일 저장 로직 (파일 시스템)
    attachment_data_list: List[AttachmentData] = []

    for attachment in attachments:
        if attachment and attachment.filename:
            # 파일 시스템에 저장
            file_path = os.path.join(UPLOAD_DIR, attachment.filename)
            file_content = await attachment.read()

            with open(file_path, "wb") as f:
                f.write(file_content)
            print(f"첨부파일 저장 완료: {attachment.filename}")

            # MongoDB에 저장할 첨부파일 데이터 준비 (Base64 인코딩)
            attachment_data = AttachmentData(
                filename=attachment.filename,
                content_type=attachment.content_type or "application/octet-stream",
                size=len(file_content),
                data=base64.b64encode(file_content).decode('utf-8')
            )
            attachment_data_list.append(attachment_data)

    # MongoDB에 원본 이메일 데이터 저장
    try:
        # 고유 이메일 ID 생성
        email_id = f"email_{get_kst_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # 수신자 리스트 파싱
        to_emails_list = [email.strip() for email in to_email.split(',')]

        # 원본 이메일 데이터 생성
        original_email = OriginalEmailData(
            email_id=email_id,
            from_email=from_email,
            to_emails=to_emails_list,
            subject=subject,
            original_body=original_body,
            attachments=attachment_data_list,
            created_at=get_kst_now()
        )

        # MongoDB에 저장
        result = await db.original_emails.insert_one(original_email.model_dump())
        print(f"✅ MongoDB에 원본 이메일 저장 완료: {email_id}")

        return {
            "message": "Email data received and saved to MongoDB",
            "email_id": email_id,
            "mongodb_id": str(result.inserted_id)
        }

    except Exception as e:
        print(f"❌ MongoDB 저장 실패: {e}")
        # MongoDB 저장 실패해도 파일 시스템에는 저장되었으므로 성공으로 처리
        return {
            "message": "Email data received (MongoDB save failed)",
            "error": str(e)
        }

@router.get("/files", response_model=list[FileItem])
def get_files():
    files_list = []
    
    for i, filename in enumerate(os.listdir(UPLOAD_DIR)):
        # <<< --- 수정된 부분: email_meta.json 파일은 목록에서 제외 --- >>>
        if filename == 'email_meta.json':
            continue
        # <<< ---------------------------------------------------- >>>
        file_kind = "text"
        if filename == "email_body.txt":
            file_kind = "email"
        elif filename.endswith((".png", ".jpg", ".jpeg", ".gif")):
            file_kind = "image"
        elif filename.endswith(".pdf"):
            file_kind = "pdf"
        elif filename.endswith(".docx"):
            file_kind = "docx"
        
        files_list.append(
            FileItem(
                id=f"file{i}",
                name=filename,
                kind=file_kind,
                path=f"/{UPLOAD_DIR}/{filename}"
            )
        )

    return files_list

@router.get("/files/watch")
async def watch_files():
    """Server-Sent Events를 사용한 파일 변경 감시"""
    async def event_generator():
        last_files = set()
        while True:
            try:
                current_files = set(os.listdir(UPLOAD_DIR)) if os.path.exists(UPLOAD_DIR) else set()
                if current_files != last_files:
                    yield f"data: {json.dumps({'files': list(current_files)})}\n\n"
                    last_files = current_files
                await asyncio.sleep(1)
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ================== 원본 이메일 조회 API ==================

@router.get("/original_emails/{email_id}")
async def get_original_email(email_id: str, db = Depends(get_db)):
    """
    저장된 원본 이메일 조회
    - email_id: 이메일 고유 ID (커스텀 email_id 또는 MongoDB _id)
    """
    try:
        # 1차: 커스텀 email_id로 조회
        email_data = await db.original_emails.find_one({"email_id": email_id})

        # 2차: MongoDB _id로 조회 (ObjectId 변환 시도)
        if not email_data:
            try:
                from bson import ObjectId
                email_data = await db.original_emails.find_one({"_id": ObjectId(email_id)})
            except:
                pass

        if not email_data:
            return {
                "success": False,
                "message": f"이메일을 찾을 수 없습니다: {email_id}",
                "data": None
            }

        # _id 필드 제거 (ObjectId는 JSON 직렬화 불가)
        email_data.pop("_id", None)

        return {
            "success": True,
            "message": "원본 이메일 조회 성공",
            "data": email_data
        }

    except Exception as e:
        print(f"❌ 원본 이메일 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"이메일 조회 중 오류 발생: {str(e)}",
            "data": None
        }


@router.get("/original_emails")
async def list_original_emails(
    skip: int = 0,
    limit: int = 20,
    from_email: str = None,
    db = Depends(get_db)
):
    """
    원본 이메일 목록 조회
    - skip: 건너뛸 개수 (페이지네이션)
    - limit: 가져올 개수 (최대 100)
    - from_email: 발신자 이메일로 필터링 (선택)
    """
    try:
        # 쿼리 필터 생성
        query = {}
        if from_email:
            query["from_email"] = from_email

        # MongoDB에서 이메일 목록 조회 (최신순)
        cursor = db.original_emails.find(query).sort("created_at", -1).skip(skip).limit(min(limit, 100))
        emails = await cursor.to_list(length=limit)

        # 전체 개수 조회
        total_count = await db.original_emails.count_documents(query)

        # _id 필드 제거 및 첨부파일 데이터 요약
        result_emails = []
        for email in emails:
            email.pop("_id", None)

            # 첨부파일 데이터는 용량이 크므로 메타데이터만 포함
            if "attachments" in email:
                email["attachments_summary"] = [
                    {
                        "filename": att["filename"],
                        "content_type": att["content_type"],
                        "size": att["size"]
                    }
                    for att in email["attachments"]
                ]
                # 실제 파일 데이터는 제외
                email.pop("attachments", None)

            result_emails.append(email)

        return {
            "success": True,
            "message": f"{len(result_emails)}개의 이메일 조회 완료",
            "total_count": total_count,
            "skip": skip,
            "limit": limit,
            "data": result_emails
        }

    except Exception as e:
        print(f"❌ 이메일 목록 조회 실패: {e}")
        return {
            "success": False,
            "message": f"이메일 목록 조회 중 오류 발생: {str(e)}",
            "data": []
        }


@router.get("/original_emails/{email_id}/attachment/{filename}")
async def download_attachment(email_id: str, filename: str, db = Depends(get_db)):
    """
    원본 이메일의 첨부파일 다운로드
    - email_id: 이메일 고유 ID
    - filename: 다운로드할 첨부파일명
    """
    try:
        # MongoDB에서 원본 이메일 조회
        email_data = await db.original_emails.find_one({"email_id": email_id})

        if not email_data:
            return {
                "success": False,
                "message": f"이메일을 찾을 수 없습니다: {email_id}"
            }

        # 첨부파일 찾기
        attachment = None
        for att in email_data.get("attachments", []):
            if att["filename"] == filename:
                attachment = att
                break

        if not attachment:
            return {
                "success": False,
                "message": f"첨부파일을 찾을 수 없습니다: {filename}"
            }

        # Base64 디코딩
        file_content = base64.b64decode(attachment["data"])

        # 파일 다운로드 응답
        from fastapi.responses import Response
        return Response(
            content=file_content,
            media_type=attachment["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename={attachment['filename']}"
            }
        )

    except Exception as e:
        print(f"❌ 첨부파일 다운로드 실패: {e}")
        return {
            "success": False,
            "message": f"첨부파일 다운로드 중 오류 발생: {str(e)}"
        }


# ================== 마스킹된 이메일 조회 API ==================

@router.get("/masked_emails/{email_id}")
async def get_masked_email(email_id: str, db = Depends(get_db)):
    """
    저장된 마스킹 이메일 조회
    - email_id: 이메일 고유 ID (커스텀 email_id 또는 MongoDB _id)
    """
    try:
        # 1차: 커스텀 email_id로 조회
        masked_data = await db.masked_emails.find_one({"email_id": email_id})

        # 2차: MongoDB _id로 조회 (ObjectId 변환 시도)
        if not masked_data:
            try:
                from bson import ObjectId
                # _id로 original_emails 조회 후 email_id 가져오기
                original_email = await db.original_emails.find_one({"_id": ObjectId(email_id)})
                if original_email and original_email.get("email_id"):
                    masked_data = await db.masked_emails.find_one({"email_id": original_email["email_id"]})
            except:
                pass

        if not masked_data:
            return {
                "success": False,
                "message": f"마스킹된 이메일을 찾을 수 없습니다: {email_id}",
                "data": None
            }

        # _id 필드 제거 (ObjectId는 JSON 직렬화 불가)
        masked_data.pop("_id", None)

        return {
            "success": True,
            "message": "마스킹된 이메일 조회 성공",
            "data": masked_data
        }

    except Exception as e:
        print(f"❌ 마스킹된 이메일 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"마스킹된 이메일 조회 중 오류 발생: {str(e)}",
            "data": None
        }