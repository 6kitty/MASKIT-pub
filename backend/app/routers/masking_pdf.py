# app/routers/analyzer.py - RAG 분석에도 감사 로그 추가

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os
import base64

from ..utils.masking_engine import PdfMaskingEngine
from ..routers.uploads import UPLOAD_DIR
from ..models.email import MaskedEmailData, MaskedEmailResponse, AttachmentData
from ..database.mongodb import get_db
from ..auth.auth_utils import get_current_user  # ✅ 추가
from ..audit.logger import AuditLogger  # ✅ 추가
from ..audit.models import AuditEventType, AuditSeverity  # ✅ 추가

def get_kst_now():
    """한국 표준시(KST) 반환"""
    return datetime.utcnow() + timedelta(hours=9)

router = APIRouter()

class PIIItemFromAnalysis(BaseModel):
    filename: str
    pii_type: str
    text: str
    pageIndex: int
    instance_index: int = 0
    bbox: Optional[List[int]] = None

@router.post("/masking/pdf")
async def mask_pii_in_pdf(
    pii_items: List[PIIItemFromAnalysis],
    request: Request,  # ✅ 추가
    current_user: dict = Depends(get_current_user)  # ✅ 추가
):
    """
    클라이언트에서 받은 PII 정보를 사용하여 PDF 또는 이미지 파일을 마스킹합니다.
    """
    
    print(f"[마스킹 API] 받은 PII 항목 수: {len(pii_items)}")
    
    pii_by_file = {}
    for item in pii_items:
        print(f"[마스킹 API] 처리 중: {item.pii_type} '{item.text}' in {item.filename}")
        
        if item.filename not in pii_by_file:
            pii_by_file[item.filename] = []
        
        entity_data = {
            "entity": item.pii_type,
            "pageIndex": item.pageIndex,
            "text": item.text,
            "instance_index": item.instance_index
        }
        
        if item.bbox is not None:
            entity_data["bbox"] = item.bbox
        
        pii_by_file[item.filename].append(entity_data)
    
    masked_file_paths = {}
    masking_engine = PdfMaskingEngine()
    
    for filename, entities in pii_by_file.items():
        original_file_path = os.path.join(UPLOAD_DIR, filename)
        
        if not os.path.exists(original_file_path):
            print(f"[마스킹 API] 파일을 찾을 수 없음: {original_file_path}")
            masked_file_paths[filename] = "File not found"
            continue
        
        file_ext = os.path.splitext(filename)[1]
        masked_filename = f"masked_{filename}"
        masked_file_path = os.path.join(UPLOAD_DIR, masked_filename)
        
        try:
            print(f"[마스킹 API] 파일 마스킹 시작: {filename}")
            for entity in entities:
                if 'bbox' in entity:
                    print(f"  - {entity['entity']}: '{entity['text']}' at page {entity['pageIndex']} bbox {entity['bbox']}")
                else:
                    print(f"  - {entity['entity']}: '{entity['text']}' at page {entity['pageIndex']} instance {entity['instance_index']}")
            
            masking_engine.redact_pdf_with_entities(
                pdf_path=original_file_path,
                entities=entities,
                out_pdf_path=masked_file_path
            )
            
            masked_file_paths[filename] = f"/uploads/{masked_filename}"
            print(f"[마스킹 API] 마스킹 완료: {masked_filename}")
        
        except Exception as e:
            print(f"[마스킹 API] 마스킹 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            masked_file_paths[filename] = f"Masking failed: {str(e)}"

    # ✅ 감사 로그 기록
    try:
        await AuditLogger.log(
            event_type=AuditEventType.MASKING_APPLY,
            user_email=current_user["email"],
            user_role=current_user.get("role", "user"),
            action=f"첨부파일 마스킹: {len(pii_items)}개 PII",
            resource_type="attachment",
            details={
                "pii_count": len(pii_items),
                "files": list(pii_by_file.keys()),
                "masked_files": list(masked_file_paths.keys())
            },
            request=request,
            success=True,
            severity=AuditSeverity.INFO
        )
    except Exception as log_error:
        print(f"⚠️ 감사 로그 기록 실패: {log_error}")

    return {"status": "success", "masked_files": masked_file_paths}


class SaveMaskedEmailRequest(BaseModel):
    email_id: str
    from_email: str
    to_emails: List[str]
    subject: str
    masked_body: str
    masked_attachment_filenames: List[str] = []
    original_attachment_filenames: List[str] = []
    masking_decisions: dict = {}
    pii_masked_count: int = 0


@router.post("/masking/save-masked-email")
async def save_masked_email(
    request_data: SaveMaskedEmailRequest,
    request: Request,  # ✅ 추가
    current_user: dict = Depends(get_current_user),  # ✅ 추가
    db = Depends(get_db)
):
    """
    마스킹된 이메일을 MongoDB의 masked_emails 컬렉션에 저장
    """
    try:
        print("\n" + "="*80)
        print("💾 [Save Masked Email] 마스킹된 이메일 저장 시작")
        print("="*80)
        print(f"[Save] email_id: {request_data.email_id}")
        print(f"[Save] from_email: {request_data.from_email}")
        print(f"[Save] to_emails: {request_data.to_emails}")
        print(f"[Save] subject: {request_data.subject}")
        print(f"[Save] masked_attachment_filenames: {request_data.masked_attachment_filenames}")
        print(f"[Save] original_attachment_filenames: {request_data.original_attachment_filenames}")
        print("="*80 + "\n")

        # 마스킹된 첨부파일과 원본 첨부파일을 모두 Base64로 읽어서 저장
        masked_attachments_data = []
        masked_set = set(request_data.masked_attachment_filenames)
        print(f"[Save] 마스킹된 파일 목록: {masked_set}")

        # 모든 첨부파일 처리
        for idx, original_filename in enumerate(request_data.original_attachment_filenames):
            print(f"\n[Save] 첨부파일 #{idx}: {original_filename}")
            
            masked_filename = f"masked_{original_filename}"
            print(f"[Save] 마스킹 파일명: {masked_filename}")

            if masked_filename in masked_set:
                filename_to_use = masked_filename
                print(f"[Save] ✅ 마스킹된 파일 사용: {masked_filename}")
            else:
                filename_to_use = original_filename
                print(f"[Save] 📄 원본 파일 사용: {original_filename}")

            file_path = os.path.join(UPLOAD_DIR, filename_to_use)
            print(f"[Save] 파일 경로: {file_path}")

            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                print(f"[Save] 파일 읽기 성공: {len(file_content)} bytes")

                encoded_content = base64.b64encode(file_content).decode('utf-8')
                print(f"[Save] Base64 인코딩 완료: {len(encoded_content)} chars")
                
                preview = encoded_content[:30] + "..." if len(encoded_content) > 30 else encoded_content
                print(f"[Save] Base64 미리보기: {preview}")

                content_type = "application/octet-stream"
                if filename_to_use.lower().endswith('.pdf'):
                    content_type = "application/pdf"
                elif filename_to_use.lower().endswith(('.jpg', '.jpeg')):
                    content_type = "image/jpeg"
                elif filename_to_use.lower().endswith('.png'):
                    content_type = "image/png"
                
                print(f"[Save] content_type: {content_type}")

                masked_attachments_data.append({
                    "filename": filename_to_use,
                    "content_type": content_type,
                    "size": len(file_content),
                    "data": encoded_content
                })

                print(f"[Save] ✅ 첨부파일 데이터 추가 완료")
            else:
                print(f"[Save] ⚠️ 파일을 찾을 수 없음: {file_path}")

        print(f"\n[Save] 총 {len(masked_attachments_data)}개 첨부파일 준비 완료")

        # MaskedEmailData 객체 생성
        masked_email = MaskedEmailData(
            email_id=request_data.email_id,
            from_email=request_data.from_email,
            to_emails=request_data.to_emails,
            subject=request_data.subject,
            masked_body=request_data.masked_body,
            masked_attachments=[
                AttachmentData(**att) for att in masked_attachments_data
            ],
            masking_decisions=request_data.masking_decisions,
            pii_masked_count=request_data.pii_masked_count,
            created_at=datetime.utcnow()
        )

        print(f"\n[Save] MongoDB 저장 시작...")
        print(f"[Save] masked_attachments 개수: {len(masked_email.masked_attachments)}")

        # MongoDB에 저장
        result = await db.masked_emails.insert_one(masked_email.model_dump())

        print(f"[Save] ✅ MongoDB 저장 완료")
        print(f"[Save] MongoDB _id: {result.inserted_id}")
        print(f"[Save] email_id: {request_data.email_id}")

        # 저장된 데이터 확인
        saved_doc = await db.masked_emails.find_one({"email_id": request_data.email_id})
        if saved_doc:
            print(f"[Save] 저장 검증 성공")
            print(f"[Save] 저장된 문서 키: {list(saved_doc.keys())}")
            if saved_doc.get("masked_attachments"):
                print(f"[Save] 저장된 첨부파일 수: {len(saved_doc['masked_attachments'])}")
            else:
                print(f"[Save] ⚠️ masked_attachments 필드 없음!")
        else:
            print(f"[Save] ❌ 저장 검증 실패: 문서를 찾을 수 없음")

        print(f"\n{'='*80}")
        print(f"✅ [Save Masked Email] 저장 완료")
        print(f"{'='*80}\n")

        # ✅ 감사 로그 기록 (마스킹 결정)
        try:
            # 마스킹된 PII 타입별 집계
            masked_by_type = {}
            for decision_key, decision in request_data.masking_decisions.items():
                if decision.get('should_mask'):
                    pii_type = decision.get('type', 'unknown')
                    masked_by_type[pii_type] = masked_by_type.get(pii_type, 0) + 1

            await AuditLogger.log(
                event_type=AuditEventType.MASKING_DECISION,
                user_email=current_user["email"],
                user_role=current_user.get("role", "user"),
                action=f"마스킹 결정: {request_data.pii_masked_count}개 PII 마스킹",
                resource_type="email",
                resource_id=request_data.email_id,
                details={
                    "email_id": request_data.email_id,
                    "subject": request_data.subject,
                    "to_emails": request_data.to_emails,
                    "pii_masked_count": request_data.pii_masked_count,
                    "masked_by_type": masked_by_type,
                    "attachment_count": len(request_data.masked_attachment_filenames)
                },
                request=request,
                success=True,
                severity=AuditSeverity.INFO
            )
            print("[Save] ✅ 마스킹 결정 감사 로그 기록 완료")
        except Exception as log_error:
            print(f"[Save] ⚠️ 감사 로그 기록 실패 (무시): {log_error}")

        return {
            "success": True,
            "message": "마스킹된 이메일이 성공적으로 저장되었습니다",
            "email_id": request_data.email_id,
            "masked_attachments_count": len(masked_attachments_data),
            "pii_masked_count": request_data.pii_masked_count
        }

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ [Save Masked Email] 저장 실패")
        print(f"{'='*80}")
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        
        # ✅ 실패 로그 기록
        try:
            await AuditLogger.log(
                event_type=AuditEventType.MASKING_DECISION,
                user_email=current_user["email"],
                user_role=current_user.get("role", "user"),
                action=f"마스킹 결정 저장 실패: {request_data.email_id}",
                resource_type="email",
                resource_id=request_data.email_id,
                request=request,
                success=False,
                error_message=str(e),
                severity=AuditSeverity.ERROR
            )
        except Exception as log_error:
            print(f"[Save] ⚠️ 실패 로그 기록 실패 (무시): {log_error}")
        
        raise HTTPException(status_code=500, detail=f"마스킹된 이메일 저장 실패: {str(e)}")


@router.get("/masking/masked-email/{email_id}")
async def get_masked_email(
    email_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    MongoDB에서 마스킹된 이메일 조회
    """
    try:
        masked_email = await db.masked_emails.find_one({"email_id": email_id})

        if not masked_email:
            raise HTTPException(status_code=404, detail="마스킹된 이메일을 찾을 수 없습니다")

        masked_email.pop('_id', None)

        if "created_at" in masked_email and masked_email["created_at"]:
            from app.utils.datetime_utils import utc_to_kst
            kst_dt = utc_to_kst(masked_email["created_at"])
            masked_email["created_at"] = kst_dt.isoformat()

        print(f"✅ 마스킹된 이메일 조회: {email_id}")

        return MaskedEmailResponse(
            success=True,
            message="마스킹된 이메일 조회 성공",
            data=MaskedEmailData(**masked_email)
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 마스킹된 이메일 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"마스킹된 이메일 조회 실패: {str(e)}")