from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from bson import ObjectId

from app.database.mongodb import get_db
from app.utils.datetime_utils import get_kst_now
from app.auth.auth_utils import get_current_user, get_current_auditor
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from app.audit.logger import AuditLogger
from app.audit.models import AuditEventType

router = APIRouter(prefix="/api/v1/emails", tags=["Emails"])

# ===== Auditor 전용: 전체 메일 로그 조회 API =====

@router.get("/all-logs")
async def get_all_email_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_auditor),  # Auditor 권한 체크
    db = Depends(get_db)
):
    """
    전체 사용자의 메일 전송 로그 조회 (Auditor 전용)
    
    - **skip**: 건너뛸 개수 (페이지네이션)
    - **limit**: 가져올 최대 개수 (기본 100, 최대 1000)
    
    반환 형식:
    ```json
    {
        "success": true,
        "total": 1234,
        "logs": [
            {
                "timestamp": "2025-01-18T12:34:56",
                "email_id": "507f1f77bcf86cd799439011",
                "team_name": "개발팀",
                "user_name": "홍길동",
                "from_email": "hong@example.com",
                "to_email": "recipient@example.com",
                "subject": "제목",
                "status": "approved"
            }
        ]
    }
    ```
    """
    try:
        print(f"[Auditor Logs API] 전체 메일 로그 조회 요청")
        print(f"  Auditor: {current_user['email']}")
        print(f"  Skip: {skip}, Limit: {limit}")
        
        # 전체 메일 개수 조회
        total = await db.emails.count_documents({})
        
        # 최신순으로 정렬하여 메일 로그 조회
        cursor = db.emails.find({}).sort("created_at", -1).skip(skip).limit(limit)
        emails = await cursor.to_list(length=limit)
        
        # 로그 포맷팅
        logs = []
        for email in emails:
            # 사용자 정보 조회 (from_email로)
            user = await db.users.find_one({"email": email.get("from_email")})
            user_name = user.get("nickname") if user else email.get("from_email", "알 수 없음")
            team_name = email.get("team_name") or (user.get("team_name") if user else "팀 없음")
            
            log_entry = {
                "timestamp": email.get("created_at").isoformat() if email.get("created_at") else None,
                "email_id": str(email["_id"]),
                "team_name": team_name,
                "user_name": user_name,
                "from_email": email.get("from_email"),
                "to_email": email.get("to_email"),
                "subject": email.get("subject", "(제목 없음)"),
                "status": email.get("status", "pending"),
                "has_attachments": bool(email.get("attachments")),
                "attachment_count": len(email.get("attachments", []))
            }
            logs.append(log_entry)
        
        print(f"[Auditor Logs API] ✅ {len(logs)}개 로그 조회 완료 (전체: {total}개)")
        
        return {
            "success": True,
            "total": total,
            "skip": skip,
            "limit": limit,
            "logs": logs
        }
        
    except Exception as e:
        print(f"[Auditor Logs API] ❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"메일 로그 조회 실패: {str(e)}"
        )


# ===== 기존 API들 (변경 없음) =====

@router.post("/upload-attachment")
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    첨부파일 업로드 (GridFS 사용)
    """
    try:
        fs = AsyncIOMotorGridFSBucket(db)
        file_data = await file.read()
        
        max_size = 10 * 1024 * 1024
        if len(file_data) > max_size:
            raise HTTPException(status_code=400, detail="파일 크기는 10MB를 초과할 수 없습니다")
        
        file_id = await fs.upload_from_stream(
            file.filename,
            file_data,
            metadata={
                "content_type": file.content_type,
                "uploaded_by": current_user["email"],
                "uploaded_at": get_kst_now(),
                "size": len(file_data)
            }
        )
        
        print(f"✅ 파일 업로드 성공: {file.filename} (ID: {file_id})")
        
        return {
            "success": True,
            "file_id": str(file_id),
            "filename": file.filename,
            "size": len(file_data),
            "content_type": file.content_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 파일 업로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")


@router.get("/attachments/{file_id}")
async def download_attachment(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    첨부파일 다운로드
    """
    try:
        fs = AsyncIOMotorGridFSBucket(db)
        
        try:
            object_id = ObjectId(file_id)
        except:
            raise HTTPException(status_code=400, detail="잘못된 파일 ID입니다")
        
        try:
            grid_out = await fs.open_download_stream(object_id)
            filename = grid_out.filename
            content_type = grid_out.metadata.get("content_type", "application/octet-stream")
            
            async def file_iterator():
                while True:
                    chunk = await grid_out.readchunk()
                    if not chunk:
                        break
                    yield chunk
            
            print(f"✅ 파일 다운로드 시작: {filename} (ID: {file_id})")
            
            return StreamingResponse(
                file_iterator(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
            
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 파일 다운로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"파일 다운로드 실패: {str(e)}")


@router.get("/email/{email_id}")
async def get_email_detail(
    email_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    이메일 상세 조회 (권한 확인 포함)
    email_id는 MongoDB ObjectId 또는 커스텀 email_id (email_20251126_161911_a14eeebd 형식) 모두 가능
    """
    try:
        print(f"\n[Email Detail] ===== 이메일 조회 시작 =====")
        print(f"[Email Detail] email_id: {email_id}")
        print(f"[Email Detail] current_user: {current_user.get('email')}")
        
        # 먼저 ObjectId로 시도
        email = None
        try:
            obj_id = ObjectId(email_id)
            email = await db.emails.find_one({"_id": obj_id})
            print(f"[Email Detail] ObjectId 조회 결과: {'발견' if email else '없음'}")
        except:
            pass

        # ObjectId로 못 찾았으면 email_id 필드로 조회
        if not email:
            print(f"[Email Detail] email_id 필드로 조회 시도")
            # original_emails 컬렉션에서 조회
            original_email = await db.original_emails.find_one({"email_id": email_id})
            
            if original_email:
                print(f"[Email Detail] original_emails에서 발견")
                # masked_emails에서도 조회
                masked_email = await db.masked_emails.find_one({"email_id": email_id})

                # 두 데이터를 합쳐서 반환
                email = {
                    "_id": str(original_email.get("_id", "")),
                    "id": email_id,
                    "email_id": email_id,
                    "from_email": original_email.get("from_email"),
                    "to_email": original_email.get("to_emails", [])[0] if original_email.get("to_emails") else "",
                    "to_emails": original_email.get("to_emails", []),
                    "subject": original_email.get("subject"),
                    "body": original_email.get("original_body"),
                    "original_body": original_email.get("original_body"),
                    "masked_body": masked_email.get("masked_body") if masked_email else None,
                    "attachments": original_email.get("attachments", []),
                    "masked_attachments": masked_email.get("masked_attachments", []) if masked_email else [],
                    "masking_decisions": masked_email.get("masking_decisions", {}) if masked_email else {},
                    "pii_masked_count": masked_email.get("pii_masked_count", 0) if masked_email else 0,
                    "created_at": original_email.get("created_at"),
                    "sent_at": original_email.get("created_at"),
                    "team_name": current_user.get("team_name"),
                }

        if not email:
            print(f"[Email Detail] ❌ 이메일을 찾을 수 없음")
            raise HTTPException(status_code=404, detail="이메일을 찾을 수 없습니다")

        # 권한 확인
        user_email = current_user["email"]
        to_emails = email.get("to_emails", [])
        if isinstance(to_emails, str):
            to_emails = [to_emails]

        is_sender = email.get("from_email") == user_email
        is_receiver = user_email in to_emails or email.get("to_email") == user_email
        is_admin = current_user.get("role") in ["root_admin", "auditor", "approver"]

        print(f"[Email Detail] 권한 확인:")
        print(f"  - is_sender: {is_sender}")
        print(f"  - is_receiver: {is_receiver}")
        print(f"  - is_admin: {is_admin}")

        if not (is_sender or is_receiver or is_admin):
            print(f"[Email Detail] ❌ 권한 없음")
            raise HTTPException(status_code=403, detail="이메일 조회 권한이 없습니다")

        # ✅ 읽음 처리 (받은 메일인 경우) - 조건 개선
        if is_receiver and not email.get("read_at"):
            print(f"[Email Detail] 📖 읽음 처리 시도")
            
            # emails 컬렉션에서 ObjectId로 업데이트 시도
            if "_id" in email and len(str(email.get("_id", ""))) == 24:
                try:
                    obj_id = ObjectId(email["_id"])
                    update_result = await db.emails.update_one(
                        {"_id": obj_id},
                        {"$set": {"read_at": get_kst_now()}}
                    )
                    print(f"[Email Detail] emails 컬렉션 읽음 처리: matched={update_result.matched_count}, modified={update_result.modified_count}")
                    if update_result.modified_count > 0:
                        email["read_at"] = get_kst_now()
                except Exception as e:
                    print(f"[Email Detail] ⚠️ emails 컬렉션 업데이트 실패: {e}")
            
            # ✅ email_id 필드로도 업데이트 시도 (SMTP로 받은 메일)
            if "email_id" in email:
                try:
                    update_result = await db.emails.update_one(
                        {"email_id": email["email_id"]},
                        {"$set": {"read_at": get_kst_now()}}
                    )
                    print(f"[Email Detail] email_id로 읽음 처리: matched={update_result.matched_count}, modified={update_result.modified_count}")
                    if update_result.modified_count > 0:
                        email["read_at"] = get_kst_now()
                        email["read"] = True
                except Exception as e:
                    print(f"[Email Detail] ⚠️ email_id 업데이트 실패: {e}")

        # ID 필드 정규화
        if "_id" in email and not isinstance(email["_id"], str):
            email["_id"] = str(email["_id"])
        if "id" not in email:
            email["id"] = email.get("email_id") or email.get("_id")
        
        print(f"[Email Detail] ✅ 이메일 조회 완료")
        print(f"[Email Detail] read_at: {email.get('read_at')}")
        print(f"[Email Detail] ===== 이메일 조회 끝 =====\n")
        
        return email
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Email Detail] ❌ 메일 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"메일 조회 실패: {str(e)}")

@router.get("/email/{email_id}/attachments/by-filename/{filename}")
async def download_email_attachment_by_filename(
    email_id: str,
    filename: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    특정 이메일의 첨부파일을 파일명으로 다운로드 (SMTP로 전송된 이메일용)
    MongoDB masked_emails 컬렉션에서 Base64 데이터를 가져와서 반환
    """
    try:
        import base64
        from io import BytesIO

        # 1. 이메일 권한 확인
        email = await db.emails.find_one({"_id": ObjectId(email_id)})

        if not email:
            raise HTTPException(status_code=404, detail="이메일을 찾을 수 없습니다")

        if email["from_email"] != current_user["email"] and email["to_email"] != current_user["email"]:
            raise HTTPException(status_code=403, detail="첨부파일 다운로드 권한이 없습니다")

        # 2. 첨부파일이 이메일에 존재하는지 확인
        attachment_exists = False
        for att in email.get("attachments", []):
            if isinstance(att, dict) and att.get("filename") == filename:
                attachment_exists = True
                break

        if not attachment_exists:
            raise HTTPException(status_code=404, detail="이메일에 해당 첨부파일이 없습니다")

        # 3. MongoDB masked_emails 컬렉션에서 Base64 데이터 조회
        # email 레코드에서 masked_email_id를 가져와서 사용
        masked_email_id = email.get("masked_email_id")

        if not masked_email_id:
            # masked_email_id가 없으면 현재 email_id로 시도 (구버전 호환성)
            masked_email_id = email_id

        masked_email = await db.masked_emails.find_one({"email_id": masked_email_id})

        if not masked_email or not masked_email.get("masked_attachments"):
            raise HTTPException(status_code=404, detail="마스킹된 이메일 데이터를 찾을 수 없습니다")

        # 4. 파일명으로 첨부파일 찾기
        file_data = None
        content_type = "application/octet-stream"

        for att in masked_email["masked_attachments"]:
            if att.get("filename") == filename:
                base64_data = att.get("data")
                if not base64_data:
                    raise HTTPException(status_code=404, detail="첨부파일 데이터가 없습니다")

                # Base64 디코딩
                file_data = base64.b64decode(base64_data)
                content_type = att.get("content_type", "application/octet-stream")
                break

        if not file_data:
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {filename}")

        print(f"✅ Base64 첨부파일 다운로드: {filename} ({len(file_data)} bytes, Email: {email_id}, User: {current_user['email']})")

        # 5. 파일 다운로드 응답
        # RFC 2231 인코딩으로 한글 파일명 처리
        from urllib.parse import quote
        encoded_filename = quote(filename)

        return StreamingResponse(
            BytesIO(file_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Base64 첨부파일 다운로드 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"첨부파일 다운로드 실패: {str(e)}")


class SendEmailRequest(BaseModel):
    """이메일 전송 요청"""
    from_email: EmailStr
    to: str
    subject: str
    body: str
    attachments: List[dict] = []
    masking_applied: bool = False
    masking_decisions: dict = {}


@router.post("/send")
async def send_email(
    email_request: SendEmailRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    이메일 전송 (임시 저장)
    """
    try:
        recipients = [email.strip() for email in email_request.to.split(',')]
        email_ids = []

        attachment_records = []
        for att in email_request.attachments:
            if isinstance(att, dict) and att.get("file_id"):
                attachment_records.append({
                    "file_id": att["file_id"],
                    "filename": att.get("filename", "unknown"),
                    "size": att.get("size", 0),
                    "content_type": att.get("content_type", "application/octet-stream")
                })
            elif isinstance(att, str):
                attachment_records.append({"filename": att})

        # 마스킹된 PII 개수 계산
        masked_count = sum(1 for d in email_request.masking_decisions.values() if d.get('should_mask', False))

        for recipient in recipients:
            email_record = {
                "from_email": email_request.from_email,
                "to_email": recipient,
                "subject": email_request.subject,
                "body": email_request.body,
                "attachments": attachment_records,
                "team_name": current_user.get("team_name"),
                "masking_decisions": email_request.masking_decisions,
                "created_at": get_kst_now(),
                "sent_at": get_kst_now(),
                "read_at": None,
            }

            result = await db.emails.insert_one(email_record)
            email_ids.append(str(result.inserted_id))

        print(f"✅ 이메일 전송: {len(recipients)}명, 첨부파일: {len(attachment_records)}개")

        # 감사 로그 기록
        await AuditLogger.log_email_send(
            user_email=current_user["email"],
            user_role=current_user.get("role", "user"),
            to_emails=recipients,
            subject=email_request.subject,
            has_attachments=len(attachment_records) > 0,
            masked_count=masked_count,
            request=http_request,
        )

        return JSONResponse({
            "success": True,
            "message": f"{len(recipients)}명의 수신자에게 이메일이 전송되었습니다",
            "email_ids": email_ids,
            "data": {
                "from": email_request.from_email,
                "to": recipients,
                "subject": email_request.subject,
                "sent_at": get_kst_now().isoformat(),
                "attachments": len(attachment_records)
            }
        })

    except Exception as e:
        print(f"❌ 이메일 전송 오류: {e}")

        # 실패 로그 기록
        await AuditLogger.log(
            event_type=AuditEventType.EMAIL_SEND,
            user_email=current_user["email"],
            user_role=current_user.get("role", "user"),
            action=f"이메일 전송 실패: {email_request.subject}",
            resource_type="email",
            request=http_request,
            success=False,
            error_message=str(e),
        )

        raise HTTPException(status_code=500, detail=f"이메일 전송 실패: {str(e)}")


@router.get("/my-emails")
async def get_my_emails(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    내가 보낸 이메일 목록 조회
    """
    try:
        query = {"from_email": current_user["email"]}
        cursor = db.emails.find(query).sort("created_at", -1).limit(100)
        emails = []

        async for email in cursor:
            email["_id"] = str(email["_id"])
            email["id"] = str(email["_id"])
            emails.append(email)

        print(f"✅ 보낸 메일 조회: {current_user['email']} - {len(emails)}개")
        return emails

    except Exception as e:
        print(f"❌ 보낸 메일 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"메일 조회 실패: {str(e)}")


@router.get("/received-emails")
async def get_received_emails(
    status_filter: Optional[str] = Query(None, description="read/unread"),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    내가 받은 이메일 목록 조회
    """
    try:
        query = {"to_email": current_user["email"]}
        
        if status_filter == "unread":
            query["read_at"] = None
        elif status_filter == "read":
            query["read_at"] = {"$ne": None}
        
        cursor = db.emails.find(query).sort("sent_at", -1).limit(100)
        emails = []
        
        async for email in cursor:
            email["_id"] = str(email["_id"])
            email["id"] = str(email["_id"])
            email["read"] = email.get("read_at") is not None
            emails.append(email)

        print(f"✅ 받은 메일 조회: {current_user['email']} - {len(emails)}개")
        return emails
        
    except Exception as e:
        print(f"❌ 받은 메일 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"메일 조회 실패: {str(e)}")


@router.get("/email/{email_id}")
async def get_email_detail(
    email_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    이메일 상세 조회 (권한 확인 포함)
    email_id는 MongoDB ObjectId 또는 커스텀 email_id (email_20251126_161911_a14eeebd 형식) 모두 가능
    """
    try:
        # 먼저 ObjectId로 시도
        email = None
        try:
            obj_id = ObjectId(email_id)
            email = await db.emails.find_one({"_id": obj_id})
        except:
            # ObjectId가 아니면 커스텀 email_id로 조회
            pass

        # ObjectId로 못 찾았으면 email_id 필드로 조회
        if not email:
            # original_emails 컬렉션에서 조회
            original_email = await db.original_emails.find_one({"email_id": email_id})
            if original_email:
                # masked_emails에서도 조회
                masked_email = await db.masked_emails.find_one({"email_id": email_id})

                # 두 데이터를 합쳐서 반환
                email = {
                    "_id": str(original_email.get("_id", "")),
                    "id": email_id,
                    "email_id": email_id,
                    "from_email": original_email.get("from_email"),
                    "to_email": original_email.get("to_emails", [])[0] if original_email.get("to_emails") else "",
                    "to_emails": original_email.get("to_emails", []),
                    "subject": original_email.get("subject"),
                    "body": original_email.get("original_body"),
                    "original_body": original_email.get("original_body"),
                    "masked_body": masked_email.get("masked_body") if masked_email else None,
                    "attachments": original_email.get("attachments", []),
                    "masked_attachments": masked_email.get("masked_attachments", []) if masked_email else [],
                    "masking_decisions": masked_email.get("masking_decisions", {}) if masked_email else {},
                    "pii_masked_count": masked_email.get("pii_masked_count", 0) if masked_email else 0,
                    "created_at": original_email.get("created_at"),
                    "sent_at": original_email.get("created_at"),
                    "team_name": current_user.get("team_name"),
                }

        if not email:
            raise HTTPException(status_code=404, detail="이메일을 찾을 수 없습니다")

        # 권한 확인
        user_email = current_user["email"]
        to_emails = email.get("to_emails", [])
        if isinstance(to_emails, str):
            to_emails = [to_emails]

        is_sender = email.get("from_email") == user_email
        is_receiver = user_email in to_emails or email.get("to_email") == user_email
        is_admin = current_user.get("role") in ["root_admin", "auditor", "approver"]

        if not (is_sender or is_receiver or is_admin):
            raise HTTPException(status_code=403, detail="이메일 조회 권한이 없습니다")

        # 읽음 처리 (받은 메일인 경우)
        if is_receiver and not email.get("read_at"):
            if isinstance(email.get("_id"), str) and len(email.get("_id", "")) == 24:
                try:
                    obj_id = ObjectId(email["_id"])
                    await db.emails.update_one(
                        {"_id": obj_id},
                        {"$set": {"read_at": get_kst_now()}}
                    )
                    email["read_at"] = get_kst_now()
                except:
                    pass

        # ID 필드 정규화
        if "_id" in email and not isinstance(email["_id"], str):
            email["_id"] = str(email["_id"])
        if "id" not in email:
            email["id"] = email.get("email_id") or email.get("_id")
        
        print(f"✅ 메일 상세 조회: {email_id} by {user_email}")
        return email
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 메일 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"메일 조회 실패: {str(e)}")