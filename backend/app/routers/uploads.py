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
from app.auth.auth_utils import get_current_user

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
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    print(f"📧 이메일 업로드: {from_email} → {to_email} | 첨부파일: {len(attachments)}개")

    # 첨부파일 데이터 준비 (MongoDB에만 저장, 파일 시스템 사용 안 함)
    attachment_data_list: List[AttachmentData] = []

    for attachment in attachments:
        if attachment and attachment.filename:
            # 첨부파일 읽기
            file_path = os.path.join(UPLOAD_DIR, attachment.filename)
            file_content = await attachment.read()
            with open(file_path, 'wb') as f:
                f.write(file_content)

            # MongoDB에 저장할 첨부파일 데이터 준비 (Base64 인코딩)
            attachment_data = AttachmentData(
                filename=attachment.filename,
                content_type=attachment.content_type or "application/octet-stream",
                size=len(file_content),
                data=base64.b64encode(file_content).decode('utf-8')
            )
            attachment_data_list.append(attachment_data)
            print(f"✅ 첨부파일 준비: {attachment.filename} ({len(file_content)} bytes)")

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
def get_files(current_user: dict = Depends(get_current_user)):
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
async def watch_files(current_user: dict = Depends(get_current_user)):
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
async def get_original_email(
    email_id: str,
    include_attachments: bool = True,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    저장된 원본 이메일 조회
    - email_id: 이메일 고유 ID (커스텀 email_id 또는 MongoDB _id)
    - include_attachments: 첨부파일 데이터 포함 여부 (기본: True)
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

        # created_at을 KST 문자열로 변환
        if "created_at" in email_data and email_data["created_at"]:
            from app.utils.datetime_utils import utc_to_kst
            kst_dt = utc_to_kst(email_data["created_at"])
            email_data["created_at"] = kst_dt.isoformat()

        # 첨부파일 제외 옵션
        if not include_attachments and "attachments" in email_data:
            # 메타데이터만 포함
            email_data["attachments_summary"] = [
                {
                    "filename": att["filename"],
                    "content_type": att["content_type"],
                    "size": att["size"]
                }
                for att in email_data["attachments"]
            ]
            email_data.pop("attachments", None)

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
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
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

        # MongoDB Projection으로 첨부파일 데이터 제외 (성능 최적화)
        projection = {
            "_id": 0,
            "email_id": 1,
            "from_email": 1,
            "to_emails": 1,
            "subject": 1,
            "original_body": 1,
            "created_at": 1,
            # 첨부파일 메타데이터만 포함 (data 필드 제외)
            "attachments.filename": 1,
            "attachments.content_type": 1,
            "attachments.size": 1
        }

        # MongoDB에서 이메일 목록 조회 (최신순, projection 적용)
        cursor = db.original_emails.find(query, projection).sort("created_at", -1).skip(skip).limit(min(limit, 100))
        emails = await cursor.to_list(length=limit)

        # 전체 개수 조회
        total_count = await db.original_emails.count_documents(query)

        # 첨부파일 필드명 변경 및 날짜 포맷 변환
        result_emails = []
        for email in emails:
            # 첨부파일 메타데이터 생성
            if "attachments" in email and email["attachments"]:
                # data 필드를 제외한 메타데이터만 포함
                email["attachments_summary"] = [
                    {
                        "filename": att.get("filename"),
                        "content_type": att.get("content_type"),
                        "size": att.get("size")
                    }
                    for att in email["attachments"]
                    if att.get("filename")  # filename이 있는 것만 포함
                ]
                email.pop("attachments", None)  # 원본 attachments 제거
            else:
                email["attachments_summary"] = []

            # created_at을 KST 문자열로 변환
            if "created_at" in email and email["created_at"]:
                from app.utils.datetime_utils import utc_to_kst
                kst_dt = utc_to_kst(email["created_at"])
                email["created_at"] = kst_dt.isoformat()
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
async def download_attachment(email_id: str, filename: str, db = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
async def get_masked_email(
    email_id: str,
    include_attachments: bool = True,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    저장된 마스킹 이메일 조회
    - email_id: 이메일 고유 ID (커스텀 email_id 또는 MongoDB _id)
    - include_attachments: 첨부파일 데이터 포함 여부 (기본: True)
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

        # created_at을 KST 문자열로 변환
        if "created_at" in masked_data and masked_data["created_at"]:
            from app.utils.datetime_utils import utc_to_kst
            kst_dt = utc_to_kst(masked_data["created_at"])
            masked_data["created_at"] = kst_dt.isoformat()

        # 첨부파일 제외 옵션
        if not include_attachments and "masked_attachments" in masked_data:
            # 메타데이터만 포함 (masked_attachments 필드명 유지하되 data 제외)
            masked_data["masked_attachments"] = [
                {
                    "filename": att.get("filename"),
                    "content_type": att.get("content_type"),
                    "size": att.get("size")
                }
                for att in masked_data["masked_attachments"]
                if att.get("filename")  # filename이 있는 것만 포함
            ]

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