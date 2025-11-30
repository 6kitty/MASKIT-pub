"""
SMTP 메일 전송 및 이메일 관리 API 라우터 (수정됨)
"""
from fastapi import APIRouter, HTTPException, status, Query, Depends, Request
from typing import Optional, Any # <<< [수정] Any 또는 dict를 위해 추가
from datetime import datetime,timedelta
from bson import ObjectId
from app.utils.datetime_utils import get_kst_now
from app.database.mongodb import get_database, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS, SMTP_USE_SSL # 기본 설정 Import
from app.smtp_server.models import EmailSendRequest, EmailSendResponse, EmailListResponse
from app.smtp_server.client import smtp_client
from app.audit.logger import AuditLogger
from app.audit.models import AuditEventType

# [!!! 오류 수정 지점 !!!]
# 'User' 모델을 찾을 수 없으므로, import 라인을 제거하고
# 'get_current_user'가 반환하는 타입을 'dict' 또는 'Any'로 변경합니다.
#
# 아래 from ... import ... 부분을 실제 파일 위치에 맞게 수정해주세요.
from app.auth.auth_utils import get_current_user # <<< [중요] 이 경로는 올바르다고 가정합니다.
# from app.auth.models import User # <<< [수정] 'User' 모델을 찾을 수 없으므로 이 라인을 제거합니다.


router = APIRouter(prefix="/smtp", tags=["SMTP Email"])

@router.post("/send", response_model=EmailSendResponse)
async def send_email(
    email_data: EmailSendRequest,
    http_request: Request,
    db: get_database = Depends(),
    current_user: dict = Depends(get_current_user)
):
    """
    SMTP를 통해 이메일 전송 (인증된 사용자의 SMTP 설정 사용)
    """
    try:
        print("\n" + "="*80)
        print("📧 [SMTP Send] 이메일 전송 요청 시작")
        print("="*80)
        print(f"[SMTP Send] 사용자: {current_user.get('email')}")
        print(f"[SMTP Send] 발신자: {email_data.from_email}")
        print(f"[SMTP Send] 수신자: {email_data.to}")
        print(f"[SMTP Send] 제목: {email_data.subject}")
        print(f"[SMTP Send] use_masked_email: {email_data.use_masked_email}")
        print(f"[SMTP Send] masked_email_id: {email_data.masked_email_id}")
        print(f"[SMTP Send] 요청의 attachments: {email_data.attachments}")
        print("="*80 + "\n")

        # 첨부파일 준비
        attachments_to_send = []

        # 마스킹된 이메일 사용 시
        if email_data.use_masked_email and email_data.masked_email_id:
            print(f"[SMTP Send] 🔍 MongoDB에서 마스킹된 이메일 조회 중...")
            print(f"[SMTP Send] 조회할 email_id: {email_data.masked_email_id}")
            
            masked_email = await db.masked_emails.find_one({"email_id": email_data.masked_email_id})

            if masked_email:
                print(f"[SMTP Send] ✅ MongoDB 문서 발견")
                print(f"[SMTP Send] 문서 키: {list(masked_email.keys())}")
                
                if masked_email.get("masked_attachments"):
                    print(f"[SMTP Send] 📎 masked_attachments 필드 존재: {len(masked_email['masked_attachments'])}개")
                    
                    for idx, att in enumerate(masked_email["masked_attachments"]):
                        print(f"\n[SMTP Send] 첨부파일 #{idx}:")
                        print(f"  - filename: {att.get('filename')}")
                        print(f"  - content_type: {att.get('content_type')}")
                        print(f"  - size: {att.get('size')}")
                        print(f"  - data 존재: {'data' in att}")
                        print(f"  - data 길이: {len(att.get('data', ''))} chars")
                        
                        # 첨부파일 데이터 구조 검증
                        if not att.get('filename'):
                            print(f"  ⚠️ filename 없음, 건너뜀")
                            continue
                        
                        if not att.get('data'):
                            print(f"  ⚠️ data 없음, 건너뜀")
                            continue
                        
                        # Base64 데이터 앞 20자 출력 (디버깅용)
                        data_preview = att.get('data', '')[:20]
                        print(f"  - data 미리보기: {data_preview}...")
                        
                        attachments_to_send.append({
                            "filename": att.get("filename"),
                            "content_type": att.get("content_type", "application/octet-stream"),
                            "size": att.get("size", 0),
                            "data": att.get("data")  # Base64 문자열
                        })
                    
                    print(f"\n[SMTP Send] ✅ 총 {len(attachments_to_send)}개 첨부파일 준비 완료")
                else:
                    print(f"[SMTP Send] ⚠️ masked_attachments 필드가 없거나 비어있음")
            else:
                print(f"[SMTP Send] ❌ MongoDB에서 마스킹된 이메일을 찾을 수 없음")
                print(f"[SMTP Send] 조회 쿼리: {{'email_id': '{email_data.masked_email_id}'}}")
                
        # 원본 첨부파일 사용 시
        elif email_data.attachments:
            print(f"[SMTP Send] 📎 원본 첨부파일 사용: {len(email_data.attachments)}개")
            attachments_to_send = email_data.attachments

        print(f"\n[SMTP Send] 최종 전송할 첨부파일: {len(attachments_to_send)}개")

        # SMTP 설정 로드
        user_smtp_config = current_user.get("smtp_config")

        if not user_smtp_config or not user_smtp_config.get("smtp_host"):
            print(f"[SMTP Send] ⚠️ 사용자 SMTP 설정이 없어 기본 서버 설정을 사용합니다.")

            if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
                print(f"[SMTP Send] ❌ 기본 SMTP 설정도 없습니다!")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="SMTP 설정이 없습니다. 설정 페이지에서 SMTP 설정을 저장하거나, 관리자에게 문의하세요."
                )

            smtp_config = {
                "smtp_host": SMTP_HOST,
                "smtp_port": SMTP_PORT,
                "smtp_user": SMTP_USER,
                "smtp_password": SMTP_PASSWORD,
                "smtp_use_tls": SMTP_USE_TLS,
                "smtp_use_ssl": SMTP_USE_SSL,
            }
        else:
            print(f"[SMTP Send] ✅ 사용자 저장된 SMTP 설정을 사용합니다.")
            smtp_config = user_smtp_config

        # 본문 준비 (HTML)
        bodyHtml = email_data.body.replace('\n', '<br>')

        print(f"\n[SMTP Send] 🚀 SMTP 클라이언트 호출")
        print(f"[SMTP Send] SMTP Host: {smtp_config.get('smtp_host')}")
        print(f"[SMTP Send] SMTP Port: {smtp_config.get('smtp_port')}")
        print(f"[SMTP Send] 전달할 첨부파일: {len(attachments_to_send)}개")

        # SMTP 전송
        result = smtp_client.send_email(
            from_email=email_data.from_email,
            to=email_data.to,
            subject=email_data.subject,
            body=bodyHtml,
            cc=email_data.cc,
            bcc=email_data.bcc,
            attachments=attachments_to_send,
            smtp_config=smtp_config
        )

        if not result["success"]:
            print(f"[SMTP Send] ❌ SMTP 전송 실패: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["message"]
            )

        print(f"[SMTP Send] ✅ SMTP 전송 성공")

        # MongoDB에 전송 기록 저장
        attachments_for_db = []
        for att in attachments_to_send:
            attachments_for_db.append({
                "filename": att.get("filename"),
                "content_type": att.get("content_type"),
                "size": att.get("size")
            })

        email_record = {
            "from_email": email_data.from_email,
            "to_email": email_data.to,
            "cc": email_data.cc,
            "bcc": email_data.bcc,
            "subject": email_data.subject,
            "original_body": email_data.body,
            "masked_body": None,
            "status": "sent",
            "attachments": attachments_for_db,
            "sent_at": result["sent_at"],
            "created_at": get_kst_now(),
            "dlp_verified": False,
            "dlp_token": None,
            "owner_email": current_user.get("email"),
            "masked_email_id": email_data.masked_email_id if email_data.use_masked_email else None
        }

        insert_result = await db.emails.insert_one(email_record)
        print(f"[SMTP Send] 📝 MongoDB 기록 저장 완료: {insert_result.inserted_id}")

        # 감사 로그 기록
        await AuditLogger.log_email_send(
            user_email=current_user.get("email"),
            user_role=current_user.get("role", "user"),
            to_emails=email_data.to.split(',') if isinstance(email_data.to, str) else [email_data.to],
            subject=email_data.subject,
            has_attachments=len(attachments_to_send) > 0,
            masked_count=0,
            request=http_request,
        )

        print(f"\n{'='*80}")
        print(f"✅ [SMTP Send] 이메일 전송 완료")
        print(f"{'='*80}\n")

        return EmailSendResponse(
            success=True,
            message=result["message"],
            email_id=str(insert_result.inserted_id),
            sent_at=result["sent_at"]
        )

    except HTTPException as he:
        await AuditLogger.log(
            event_type=AuditEventType.EMAIL_SEND,
            user_email=current_user.get("email"),
            user_role=current_user.get("role", "user"),
            action=f"SMTP 이메일 전송 실패: {email_data.subject}",
            resource_type="email",
            request=http_request,
            success=False,
            error_message=str(he.detail),
        )
        raise
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ [SMTP Send] 예상치 못한 오류")
        print(f"{'='*80}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")

        await AuditLogger.log(
            event_type=AuditEventType.EMAIL_SEND,
            user_email=current_user.get("email"),
            user_role=current_user.get("role", "user"),
            action=f"SMTP 이메일 전송 실패: {email_data.subject}",
            resource_type="email",
            request=http_request,
            success=False,
            error_message=str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메일 전송 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/emails", response_model=EmailListResponse)
async def get_emails(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 당 항목 수"),
    status_filter: Optional[str] = Query(None, description="상태 필터 (sent, approved, rejected)"),
    db: get_database = Depends(),
    # [수정] current_user: User -> current_user: dict
    current_user: dict = Depends(get_current_user) # [추가] 인증
):
    """
    이메일 목록 조회 (로그인한 사용자의 이메일만)

    - **page**: 페이지 번호 (기본: 1)
    - **page_size**: 페이지 당 항목 수 (기본: 20, 최대: 100)
    - **status_filter**: 상태 필터 (옵션)
    """
    try:
        # 필터 조건
        query = {
            "owner_email": current_user.get("email") # [수정] 내 이메일만 조회
        }
        if status_filter:
            query["status"] = status_filter

        # 전체 개수
        total = await db.emails.count_documents(query)

        # 페이징된 이메일 목록
        skip = (page - 1) * page_size
        emails_cursor = db.emails.find(query).sort("created_at", -1).skip(skip).limit(page_size)
        emails = await emails_cursor.to_list(length=page_size)

        # ObjectId를 문자열로 변환
        for email in emails:
            email["_id"] = str(email["_id"])

        return EmailListResponse(
            emails=emails,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이메일 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/emails/{email_id}")
async def get_email(
    email_id: str,
    db: get_database = Depends(),
    # [수정] current_user: User -> current_user: dict
    current_user: dict = Depends(get_current_user) # [추가] 인증
):
    """
    특정 이메일 상세 조회 (본인 이메일만)

    - **email_id**: 이메일 ID
    """
    try:
        # ObjectId 변환
        try:
            obj_id = ObjectId(email_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 이메일 ID 형식입니다"
            )

        # [수정] 본인 이메일인지 확인
        query = {
            "_id": obj_id,
            "owner_email": current_user.get("email")
        }
        email = await db.emails.find_one(query)

        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, # <<< 오타 수정
                detail="이메일을 찾을 수 없거나 권한이 없습니다"
            )

        # ObjectId를 문자열로 변환
        email["_id"] = str(email["_id"])

        return email

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이메일 조회 중 오류가 발생했습니다: {str(e)}"
        )