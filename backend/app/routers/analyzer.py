from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from ..utils.recognizer_engine import recognize_pii_in_text
from ..utils.rag_integration import get_rag_engine
from ..database.mongodb import get_db
from ..auth.auth_utils import get_current_user  # ✅ 추가
from ..audit.logger import AuditLogger  # ✅ 추가
from ..audit.models import AuditEventType, AuditSeverity  # ✅ 추가

router = APIRouter()

class EmailContext(BaseModel):
    """이메일 맥락 정보"""
    sender_type: str = "internal"
    receiver_type: str = "external_customer"
    purpose: str = "일반 업무"
    has_consent: bool = False

class TextAnalysisRequest(BaseModel):
    text_content: str
    user_request: str = "default"
    ocr_data: Optional[Dict] = None
    email_context: Optional[EmailContext] = None
    enable_rag: bool = True

class PIICoordinate(BaseModel):
    pageIndex: int
    bbox: List[int]
    field_text: str

class PIIEntity(BaseModel):
    text: str
    type: str
    score: float
    start_char: int
    end_char: int
    coordinates: Optional[List[PIICoordinate]] = None

class MaskingDecision(BaseModel):
    """마스킹 결정 정보"""
    action: str
    reasoning: str
    referenced_guides: List[str]
    referenced_laws: List[str]
    confidence: float

class PIIEntityWithDecision(PIIEntity):
    """마스킹 결정이 포함된 PII 엔티티"""
    masking_decision: Optional[MaskingDecision] = None

class TextAnalysisResponse(BaseModel):
    full_text: str
    pii_entities: List[PIIEntity]

class TextAnalysisWithRAGResponse(BaseModel):
    """RAG 기반 분석 응답"""
    full_text: str
    pii_entities: List[PIIEntityWithDecision]
    rag_enabled: bool
    warnings: List[str] = []

@router.post("/analyze/text", response_model=TextAnalysisResponse)
async def analyze_text(request: TextAnalysisRequest, db = Depends(get_db)):
    """
    추출된 텍스트에서 PII를 분석하고 탐지합니다.
    """
    analysis_result = await recognize_pii_in_text(
        request.text_content,
        request.ocr_data,
        db_client=db
    )
    return analysis_result

@router.post("/analyze/text-with-rag", response_model=TextAnalysisWithRAGResponse)
async def analyze_text_with_rag(
    analysis_request: TextAnalysisRequest,
    http_request: Request,  # ✅ 이름 변경
    current_user: dict = Depends(get_current_user),  # ✅ 추가
    db = Depends(get_db)
):
    """
    RAG 기반 PII 분석 및 마스킹 결정
    """
    # 1. PII 탐지
    analysis_result = await recognize_pii_in_text(
        analysis_request.text_content,
        analysis_request.ocr_data,
        db_client=db
    )

    pii_entities = analysis_result.get("pii_entities", [])

    # 2. RAG 기반 마스킹 결정
    if analysis_request.enable_rag and pii_entities:
        rag_engine = get_rag_engine()

        context = None
        if analysis_request.email_context:
            context = {
                "sender_type": analysis_request.email_context.sender_type,
                "receiver_type": analysis_request.email_context.receiver_type,
                "purpose": analysis_request.email_context.purpose,
                "has_consent": analysis_request.email_context.has_consent
            }

        rag_result = rag_engine.get_masking_decisions(pii_entities, context)

        entities_with_decisions = []
        for decision_data in rag_result.get("decisions", []):
            entity = decision_data["entity"]
            decision = MaskingDecision(
                action=decision_data["action"],
                reasoning=decision_data["reasoning"],
                referenced_guides=decision_data["referenced_guides"],
                referenced_laws=decision_data["referenced_laws"],
                confidence=decision_data["confidence"]
            )

            entity_with_decision = PIIEntityWithDecision(
                **entity,
                masking_decision=decision
            )
            entities_with_decisions.append(entity_with_decision)

        # ✅ 감사 로그 기록 (RAG 마스킹 결정)
        try:
            masked_count = sum(1 for e in entities_with_decisions if e.masking_decision and e.masking_decision.action != 'keep')
            
            await AuditLogger.log(
                event_type=AuditEventType.MASKING_DECISION,
                user_email=current_user["email"],
                user_role=current_user.get("role", "user"),
                action=f"RAG 마스킹 분석: {masked_count}/{len(pii_entities)}개 마스킹 권장",
                resource_type="analysis",
                details={
                    "total_pii": len(pii_entities),
                    "masked_pii": masked_count,
                    "context": context,
                    "rag_enabled": rag_result.get("rag_enabled", False)
                },
                request=http_request,
                success=True,
                severity=AuditSeverity.INFO
            )
        except Exception as log_error:
            print(f"⚠️ RAG 분석 감사 로그 실패: {log_error}")

        return TextAnalysisWithRAGResponse(
            full_text=analysis_result.get("full_text", ""),
            pii_entities=entities_with_decisions,
            rag_enabled=rag_result.get("rag_enabled", False),
            warnings=rag_result.get("warnings", [])
        )
    else:
        entities_with_decisions = [
            PIIEntityWithDecision(**entity, masking_decision=None)
            for entity in pii_entities
        ]

        return TextAnalysisWithRAGResponse(
            full_text=analysis_result.get("full_text", ""),
            pii_entities=entities_with_decisions,
            rag_enabled=False,
            warnings=["RAG가 비활성화되었거나 PII가 없음"]
        )