"""
VectorDB 및 정책 스키마 관리 라우터
- JSONL 파일 관리 (CRUD)
- OpenAI Vector Store 동기화
- source_document 기반 그룹화
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Optional, Dict, Any
import asyncio
from pathlib import Path
from datetime import datetime
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
import hashlib
from pydantic import BaseModel

from app.audit.logger import AuditLogger
from app.auth.auth_utils import get_current_user
from app.vectordb.rag_masking import decide_all_pii_with_rag
from app.utils.masking_rules import MaskingRules

load_dotenv()

router = APIRouter(prefix="/api/vectordb", tags=["VectorDB Management"])

# 경로 설정 - 절대 경로로 변환
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
STAGING_DIR = BASE_DIR / "app" / "rag" / "data" / "staging"

# 디렉토리 생성
STAGING_DIR.mkdir(parents=True, exist_ok=True)

# OpenAI 클라이언트
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# OpenAI Vector Store 설정
VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")


# Pydantic 모델
class PolicyGuide(BaseModel):
    guide_id: str
    source_authority: str
    source_document: str
    scenario: str
    context: Dict[str, Any]
    interpretation: str
    actionable_directive: str
    keywords: List[str]
    related_law_ids: List[str]
    examples: List[Dict[str, Any]]
    confidence_score: float
    reviewed: bool


class PolicyGuideCreate(BaseModel):
    source_authority: str
    source_document: str
    scenario: str
    context: Dict[str, Any]
    interpretation: str
    actionable_directive: str
    keywords: List[str]
    related_law_ids: List[str]
    examples: List[Dict[str, Any]]
    confidence_score: Optional[float] = 0.8
    reviewed: Optional[bool] = False


class PolicyGuideUpdate(BaseModel):
    source_authority: Optional[str] = None
    scenario: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    interpretation: Optional[str] = None
    actionable_directive: Optional[str] = None
    keywords: Optional[List[str]] = None
    related_law_ids: Optional[List[str]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    confidence_score: Optional[float] = None
    reviewed: Optional[bool] = None


def build_search_text(guide: Dict) -> str:
    """검색용 텍스트 구성"""
    parts = [
        f"Scenario: {guide.get('scenario', '')}",
        f"Directive: {guide.get('actionable_directive', '')}",
        f"Interpretation: {guide.get('interpretation', '')}",
        f"Keywords: {', '.join(guide.get('keywords', []))}",
    ]

    for example in guide.get('examples', []):
        parts.append(f"Example: {example.get('case_description', '')}")

    return "\n".join(parts)


def load_all_guides() -> Dict[str, List[Dict]]:
    """
    모든 JSONL 파일을 로드하고 source_document로 그룹화
    Returns: {source_document: [guides...]}
    """
    if not STAGING_DIR.exists():
        return {}

    grouped_guides = {}
    jsonl_files = list(STAGING_DIR.glob("*.jsonl"))

    for jsonl_file in jsonl_files:
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        guide = json.loads(line)
                        source_doc = guide.get("source_document", "Unknown")

                        if source_doc not in grouped_guides:
                            grouped_guides[source_doc] = []

                        guide["_jsonl_file"] = jsonl_file.name
                        grouped_guides[source_doc].append(guide)
        except Exception as e:
            print(f"파일 로드 실패 {jsonl_file.name}: {e}")

    return grouped_guides


def load_guides_from_file(filename: str) -> List[Dict]:
    """특정 JSONL 파일에서 가이드 로드"""
    file_path = STAGING_DIR / filename
    if not file_path.exists():
        return []

    guides = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                guides.append(json.loads(line))

    return guides


def save_guides_to_file(filename: str, guides: List[Dict]) -> bool:
    """가이드를 JSONL 파일에 저장"""
    try:
        file_path = STAGING_DIR / filename
        with open(file_path, "w", encoding="utf-8") as f:
            for guide in guides:
                # _jsonl_file 필드 제거
                guide_copy = guide.copy()
                guide_copy.pop("_jsonl_file", None)
                f.write(json.dumps(guide_copy, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"파일 저장 실패: {e}")
        return False


def search_openai_vector_store(query: str, top_k: int = 5) -> List[Dict]:
    """
    OpenAI Vector Store에서 검색
    """
    try:
        # File Search를 사용하여 Vector Store 검색
        response = openai_client.responses.create(
            model="gpt-4o-mini",
            input=query,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [VECTOR_STORE_ID]
            }],
            tool_choice={"type": "file_search"}
        )

        # 검색 결과 추출
        results = []
        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'content'):
                    for content in item.content:
                        if hasattr(content, 'text'):
                            results.append({
                                'content': content.text,
                                'score': 0.9
                            })

        return results[:top_k]

    except Exception as e:
        print(f"OpenAI Vector Store 검색 실패: {e}")
        return []


async def search_with_assistant(query: str, context: Dict = None) -> List[Dict]:
    """
    OpenAI Assistants API의 File Search 도구를 사용하여 Vector Store 검색
    """
    try:
        # 컨텍스트 정보를 쿼리에 추가
        receiver_type = context.get('receiver_type', 'external') if context else 'external'
        enhanced_query = f"이메일 {receiver_type} 전송 시 개인정보 마스킹 가이드라인: {query}"

        # Responses API로 File Search 수행
        response = openai_client.responses.create(
            model="gpt-4o-mini",
            input=enhanced_query,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [VECTOR_STORE_ID]
            }]
        )

        # 검색 결과 파싱
        results = []

        # output에서 file_search 결과 추출
        if hasattr(response, 'output'):
            for output_item in response.output:
                # file_search_call 타입 처리
                if hasattr(output_item, 'type') and output_item.type == 'file_search_call':
                    if hasattr(output_item, 'results') and output_item.results is not None:
                        for result in output_item.results:
                            results.append({
                                'content': result.get('text', ''),
                                'filename': result.get('filename', ''),
                                'score': result.get('score', 0.5)
                            })
                # message 타입 처리 (텍스트 응답)
                elif hasattr(output_item, 'content'):
                    for content in output_item.content:
                        if hasattr(content, 'text'):
                            # 주석(annotations)에서 파일 정보 추출
                            text = content.text
                            annotations = getattr(text, 'annotations', [])
                            for ann in annotations:
                                if hasattr(ann, 'file_citation'):
                                    results.append({
                                        'content': text.value if hasattr(text, 'value') else str(text),
                                        'file_id': ann.file_citation.file_id if hasattr(ann.file_citation, 'file_id') else '',
                                        'score': 0.8
                                    })

        # 결과가 없으면 기본 응답 텍스트 사용
        if not results and hasattr(response, 'output_text'):
            results.append({
                'content': response.output_text,
                'score': 0.7
            })

        print(f"✅ OpenAI Vector Store 검색 완료: {len(results)}개 결과")
        return results

    except Exception as e:
        print(f"⚠️ OpenAI Vector Store 검색 실패: {e}")
        import traceback
        traceback.print_exc()
        return []


@router.get("/guides/grouped")
async def get_guides_grouped(current_user: dict = Depends(get_current_user)):
    """source_document로 그룹화된 모든 가이드 조회"""
    try:
        grouped = load_all_guides()

        # 통계 정보 추가
        result = []
        for source_doc, guides in grouped.items():
            result.append({
                "source_document": source_doc,
                "count": len(guides),
                "authorities": list(set(g.get("source_authority", "") for g in guides)),
                "jsonl_files": list(set(g.get("_jsonl_file", "") for g in guides)),
                "guides": guides
            })

        # source_document 이름으로 정렬
        result.sort(key=lambda x: x["source_document"])

        return JSONResponse({
            "success": True,
            "data": {
                "total_source_documents": len(result),
                "total_guides": sum(item["count"] for item in result),
                "groups": result
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가이드 조회 실패: {str(e)}")


@router.get("/guides/by-source/{source_document}")
async def get_guides_by_source(source_document: str, current_user: dict = Depends(get_current_user)):
    """특정 source_document의 가이드 조회"""
    try:
        grouped = load_all_guides()
        guides = grouped.get(source_document, [])

        return JSONResponse({
            "success": True,
            "data": {
                "source_document": source_document,
                "count": len(guides),
                "guides": guides
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가이드 조회 실패: {str(e)}")


@router.get("/guides/{guide_id}")
async def get_guide_by_id(guide_id: str, current_user: dict = Depends(get_current_user)):
    """특정 가이드 조회"""
    try:
        grouped = load_all_guides()

        for source_doc, guides in grouped.items():
            for guide in guides:
                if guide.get("guide_id") == guide_id:
                    return JSONResponse({
                        "success": True,
                        "data": guide
                    })

        raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가이드 조회 실패: {str(e)}")


@router.post("/guides")
async def create_guide(guide_data: PolicyGuideCreate, current_user: dict = Depends(get_current_user)):
    """새 가이드 생성"""
    try:
        # guide_id 생성
        timestamp = datetime.now().strftime("%Y%m")
        random_str = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:6]

        # 해당 source_document의 기존 가이드 개수 확인
        grouped = load_all_guides()
        existing_guides = grouped.get(guide_data.source_document, [])
        guide_index = len(existing_guides)

        authority_code = "UNK"
        if "개인정보보호위원회" in guide_data.source_authority:
            authority_code = "PIPC"
        elif "금융보안원" in guide_data.source_authority:
            authority_code = "FSI"

        guide_id = f"GUIDE-{authority_code}-{timestamp}-{random_str}-{guide_index:03d}"

        # 새 가이드 생성
        new_guide = {
            "guide_id": guide_id,
            **guide_data.model_dump()
        }

        # JSONL 파일명 결정 (source_document 기반)
        safe_filename = guide_data.source_document.replace(" ", "_").replace("/", "_")[:50]
        jsonl_filename = f"application_guides_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename}.jsonl"

        # 기존 파일에 추가 또는 새 파일 생성
        target_file = None
        if existing_guides:
            # 기존 파일 중 하나 선택
            target_file = existing_guides[0].get("_jsonl_file")

        if not target_file:
            target_file = jsonl_filename

        # 파일에서 기존 가이드 로드
        all_guides = load_guides_from_file(target_file) if target_file else []
        all_guides.append(new_guide)

        # 파일 저장
        if not save_guides_to_file(target_file, all_guides):
            raise HTTPException(status_code=500, detail="파일 저장 실패")

        return JSONResponse({
            "success": True,
            "message": "가이드가 성공적으로 생성되었습니다",
            "data": {
                "guide_id": guide_id,
                "jsonl_file": target_file
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가이드 생성 실패: {str(e)}")


@router.put("/guides/{guide_id}")
async def update_guide(guide_id: str, guide_data: PolicyGuideUpdate, current_user: dict = Depends(get_current_user)):
    """가이드 업데이트"""
    try:
        grouped = load_all_guides()

        target_file = None
        updated_guide = None

        # 가이드 찾기
        for source_doc, guides in grouped.items():
            for guide in guides:
                if guide.get("guide_id") == guide_id:
                    target_file = guide.get("_jsonl_file")
                    break
            if target_file:
                break

        if not target_file:
            raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다")

        # 파일에서 모든 가이드 로드
        all_guides = load_guides_from_file(target_file)

        # 업데이트된 가이드 찾아서 수정
        for i, g in enumerate(all_guides):
            if g.get("guide_id") == guide_id:
                update_dict = guide_data.model_dump(exclude_unset=True)
                all_guides[i].update(update_dict)
                updated_guide = all_guides[i]
                break

        # 파일 저장
        if not save_guides_to_file(target_file, all_guides):
            raise HTTPException(status_code=500, detail="파일 저장 실패")

        return JSONResponse({
            "success": True,
            "message": "가이드가 성공적으로 업데이트되었습니다",
            "data": updated_guide
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가이드 업데이트 실패: {str(e)}")


@router.delete("/guides/{guide_id}")
async def delete_guide(guide_id: str, current_user: dict = Depends(get_current_user)):
    """가이드 삭제"""
    try:
        grouped = load_all_guides()

        target_file = None

        # 가이드 찾기
        for source_doc, guides in grouped.items():
            for guide in guides:
                if guide.get("guide_id") == guide_id:
                    target_file = guide.get("_jsonl_file")
                    break
            if target_file:
                break

        if not target_file:
            raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다")

        # 파일에서 가이드 제거
        all_guides = load_guides_from_file(target_file)
        all_guides = [g for g in all_guides if g.get("guide_id") != guide_id]

        # 파일 저장
        if not save_guides_to_file(target_file, all_guides):
            raise HTTPException(status_code=500, detail="파일 저장 실패")

        return JSONResponse({
            "success": True,
            "message": "가이드가 성공적으로 삭제되었습니다"
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가이드 삭제 실패: {str(e)}")


@router.get("/stats")
async def get_vectordb_stats(current_user: dict = Depends(get_current_user)):
    """VectorDB 통계"""
    try:
        grouped = load_all_guides()

        total_guides = sum(len(guides) for guides in grouped.values())
        authorities = set()
        jsonl_files = set()

        for guides in grouped.values():
            for guide in guides:
                authorities.add(guide.get("source_authority", ""))
                jsonl_files.add(guide.get("_jsonl_file", ""))

        # OpenAI Vector Store 정보 확인
        vector_store_status = "unknown"
        vector_store_file_count = 0
        try:
            vs = openai_client.vector_stores.retrieve(VECTOR_STORE_ID)
            vector_store_status = vs.status if hasattr(vs, 'status') else "active"
            vector_store_file_count = vs.file_counts.total if hasattr(vs, 'file_counts') else 0
        except Exception as e:
            print(f"Vector Store 조회 실패: {e}")
            vector_store_status = "error"

        return JSONResponse({
            "success": True,
            "data": {
                "total_guides": total_guides,
                "total_source_documents": len(grouped),
                "total_jsonl_files": len(jsonl_files),
                "authorities": list(authorities),
                "vector_store_id": VECTOR_STORE_ID,
                "vector_store_status": vector_store_status,
                "vector_store_file_count": vector_store_file_count,
                "sync_status": "openai_vector_store"
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


# ===== RAG 분석 엔드포인트 =====

class RAGAnalysisRequest(BaseModel):
    email_body: str
    email_subject: str
    context: Dict[str, Any]
    detected_pii: List[Dict[str, str]]
    query: str


@router.post("/analyze-stream")
async def analyze_email_with_rag_stream(
    request: RAGAnalysisRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    OpenAI Vector Store 기반 이메일 분석 (스트리밍)
    """
    async def generate():
        progress_logs = []

        def log_progress(message: str):
            progress_logs.append(message)
            print(message)

        try:
            # Vector Store 검색
            search_query = f"{request.context.get('receiver_type', 'external')} 전송 개인정보 마스킹"

            relevant_guides = await search_with_assistant(search_query, request.context)

            if not relevant_guides:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Vector Store 검색 결과 없음'})}\n\n"
                return

            # PII 분석 시작
            total_pii = len(request.detected_pii)
            yield f"data: {json.dumps({'type': 'total', 'count': total_pii})}\n\n"

            # 각 PII 분석 (진행 상황 스트리밍)
            from app.vectordb.rag_masking import decide_masking_with_rag
            from app.utils.masking_rules import MaskingRules

            decisions = {}
            for i, pii in enumerate(request.detected_pii):
                pii_type = pii.get('type', '')
                pii_value = pii.get('value', '')

                # 터미널 로그 출력 (기존 방식)
                log_progress(f"[RAG] PII #{i+1}/{total_pii}: type={pii_type}, value={pii_value[:10]}...")

                # UI에는 진행률만 전송
                yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': total_pii})}\n\n"

                # RAG 분석
                decision = await decide_masking_with_rag(pii_type, pii_value, request.context, relevant_guides)

                masked_value = None
                if decision['should_mask']:
                    try:
                        masked_value = MaskingRules.apply_masking(pii_value, pii_type.lower(), 'full')
                    except Exception as e:
                        print(f"❌ 마스킹 미리보기 실패: {e}")
                        masked_value = "***"

                decisions[f"pii_{i}"] = {
                    "type": pii_type,
                    "value": pii_value,
                    "should_mask": decision["should_mask"],
                    "reason": decision.get("reason", ""),
                    "masked_value": masked_value,
                    "legal_basis": decision.get("legal_basis", ""),
                    "cited_guidelines": decision.get("cited_guidelines", []),
                    "masking_method": decision.get("masking_method", "none"),
                    "risk_level": (
                        "high" if pii_type.lower() in ['jumin', 'resident_id', 'account', 'bank_account', 'card_number', 'passport', 'driver_license']
                        else "medium" if pii_type.lower() in ['person', 'email', 'phone', 'address'] and decision['should_mask']
                        else "low"
                    )
                }

                # 터미널에 판단 완료 로그 출력
                log_progress(f"✅ PII #{i} 판단 완료: {decision.get('masking_method', 'none')}, 근거: {decision.get('legal_basis', 'N/A')}")

            # 최종 결과 전송 (generate_summary는 이미 같은 파일에 있음)
            summary = generate_summary(request.context, decisions, relevant_guides)

            cited_guide_texts = set()
            for decision in decisions.values():
                if decision.get('cited_guidelines'):
                    cited_guide_texts.update(decision['cited_guidelines'])

            masked_count = sum(1 for d in decisions.values() if d.get('should_mask', False))

            result = {
                "type": "complete",
                "data": {
                    "masking_decisions": decisions,
                    "summary": summary,
                    "relevant_guides": relevant_guides[:5],
                    "cited_guidelines": list(cited_guide_texts),
                    "total_guides_found": len(relevant_guides),
                    "total_cited": len(cited_guide_texts),
                }
            }

            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            print(f"스트리밍 오류: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/analyze")
async def analyze_email_with_rag(
    request: RAGAnalysisRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    OpenAI Vector Store 기반 이메일 분석 및 마스킹 결정 (기존 방식)
    """
    # 진행 상황 로그 수집
    progress_logs = []

    def log_progress(message: str):
        progress_logs.append(message)
        print(message)

    try:
        # OpenAI Vector Store에서 관련 가이드라인 검색
        search_query = f"{request.context.get('receiver_type', 'external')} 전송 개인정보 마스킹"

        log_progress(f"📝 Vector Store 검색 쿼리: {search_query}")

        relevant_guides = await search_with_assistant(search_query, request.context)

        if not relevant_guides:
            log_progress("⚠️ Vector Store 검색 결과 없음, fallback 사용")
            return fallback_analysis(request)

        log_progress(f"✅ {len(relevant_guides)}개 가이드라인 검색됨")

        # 가이드라인 출처 로깅
        guide_sources = set()
        for guide in relevant_guides[:3]:
            filename = guide.get('filename', '정책 문서')
            guide_sources.add(filename)

        if guide_sources:
            log_progress(f"📚 참조 문서: {', '.join(list(guide_sources)[:3])}")

        log_progress(f"🤖 총 {len(request.detected_pii)}개 PII 분석 시작...")

        # RAG 기반 마스킹 결정
        masking_decisions = await decide_all_pii_with_rag(
            request.detected_pii,
            request.context,
            relevant_guides,
            progress_callback=log_progress
        )

        # AI 요약 생성
        summary = generate_summary(request.context, masking_decisions, relevant_guides)

        # 실제 인용된 가이드라인만 추출
        cited_guide_texts = set()
        for decision in masking_decisions.values():
            if decision.get('cited_guidelines'):
                cited_guide_texts.update(decision['cited_guidelines'])

        # 마스킹된 PII 개수 계산
        masked_count = sum(1 for d in masking_decisions.values() if d.get('should_mask', False))

        log_progress(f"✅ 분석 완료: {masked_count}/{len(request.detected_pii)}개 PII 마스킹 권장")

        print(f"📊 총 수집된 로그: {len(progress_logs)}개")
        print(f"📋 로그 내용: {progress_logs[:3]}...")  # 처음 3개만 출력

        # 감사 로그 기록
        await AuditLogger.log_masking_decision(
            user_email=current_user["email"],
            user_role=current_user.get("role", "user"),
            pii_count=len(request.detected_pii),
            masked_count=masked_count,
            receiver_type=request.context.get('receiver_type', 'unknown'),
            cited_guidelines=list(cited_guide_texts),
            request=http_request,
        )

        return JSONResponse({
            "success": True,
            "data": {
                "masking_decisions": masking_decisions,
                "summary": summary,
                "relevant_guides": relevant_guides[:5],  # 상위 5개 표시
                "cited_guidelines": list(cited_guide_texts),  # 실제 인용된 규정 목록
                "total_guides_found": len(relevant_guides),
                "total_cited": len(cited_guide_texts),
                "vector_store_id": VECTOR_STORE_ID,
                "progress_logs": progress_logs  # 진행 상황 로그 추가
            }
        })

    except Exception as e:
        print(f"RAG 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return fallback_analysis(request)


async def decide_masking_with_llm(
    email_body: str,
    detected_pii: List[Dict[str, str]],
    context: Dict[str, Any],
    guides: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    가이드라인 기반 마스킹 결정 (규칙 엔진)
    """
    decisions = {}
    receiver_type = context.get('receiver_type', 'unknown')

    # 가이드라인에서 키워드 추출 (상위 5개 사용)
    guideline_keywords = set()
    guideline_texts = []
    guideline_sources = []  # 출처 정보 저장

    for guide in guides[:5]:  # 3개 -> 5개로 증가
        content = guide.get('content', '')
        filename = guide.get('filename', '정책 문서')

        # 파일명에서 정책명 추출
        policy_name = filename.replace('.pdf', '').replace('.jsonl', '')
        guideline_texts.append(content[:300])  # 200 -> 300자로 증가
        guideline_sources.append(policy_name)

        if '마스킹' in content or 'mask' in content.lower():
            guideline_keywords.add('mask_required')
        if '외부' in content or 'external' in content.lower():
            guideline_keywords.add('external_sensitive')
        if '내부' in content or 'internal' in content.lower():
            guideline_keywords.add('internal_allowed')
        if '제3자' in content or '제공' in content:
            guideline_keywords.add('third_party')
        if '고유식별' in content:
            guideline_keywords.add('unique_identifier')

    for i, pii in enumerate(detected_pii):
        pii_type = pii.get('type', '')
        should_mask = False
        reason = ""
        masking_method = "none"
        reasoning_steps = []
        cited_guidelines = []

        print(f"[DEBUG] PII #{i}: type={pii_type}, receiver={receiver_type}, keywords={guideline_keywords}")

        # PII 유형 한글명
        pii_type_kr = {
            'email': '이메일 주소',
            'phone': '전화번호',
            'jumin': '주민등록번호',
            'account': '계좌번호',
            'passport': '여권번호',
            'driver_license': '운전면허번호'
        }.get(pii_type, pii_type)

        # Step 1: 컨텍스트 분석
        reasoning_steps.append(f"1. 컨텍스트 확인: {receiver_type} 전송")
        reasoning_steps.append(f"2. PII 유형: {pii_type_kr}")

        # Step 3: 가이드라인 검토
        if guideline_texts:
            reasoning_steps.append(f"3. OpenAI Vector Store에서 {len(guideline_texts)}개 가이드라인 검토:")
            for idx, (text, source) in enumerate(zip(guideline_texts[:3], guideline_sources[:3]), 1):
                reasoning_steps.append(f"   - [{source}]: {text[:80]}...")
                # 실제 정책명을 인용 목록에 추가
                cited_guidelines.append(f"{source}")

        # ==================== 사외 전송 규칙 ====================
        if receiver_type == 'external':
            should_mask = True
            reasoning_steps.append("4. 판단 근거:")
            reasoning_steps.append(f"   ⚠️ 사외 전송 - 개인정보를 더욱 신중하게 보호합니다")

            # 고유식별정보: 완전 마스킹
            if pii_type in ['jumin', 'account', 'passport', 'driver_license', 'card_number']:
                masking_method = "full"
                reasoning_steps.append(f"   - 고유식별정보({pii_type_kr})는 외부 전송 시 완전 마스킹이 바람직합니다")
                reason = f"외부 전송으로 고유식별정보 완전 마스킹을 권장합니다 (개인정보보호법 제24조)"
                cited_guidelines.append("개인정보보호법 제24조 (고유식별정보 처리 제한)")

            # 이름: 사외는 완전 마스킹
            elif pii_type in ['name', 'person']:
                masking_method = "full"
                reasoning_steps.append(f"   - 외부 전송 시 개인 식별을 최소화하는 것이 좋습니다")
                reason = "외부 전송으로 이름 완전 마스킹을 권장합니다 (개인정보보호법 제17조)"
                cited_guidelines.append("개인정보보호법 제17조 (개인정보 제3자 제공)")

            # 연락처: 부분 마스킹
            elif pii_type in ['email', 'phone']:
                masking_method = "partial"
                reasoning_steps.append(f"   - 외부 제공 시 {pii_type_kr} 일부를 보호하는 것이 안전합니다")
                reason = f"외부 전송으로 {pii_type_kr} 부분 마스킹을 권장합니다 (개인정보보호법 제17조)"
                cited_guidelines.append("개인정보보호법 제17조 (개인정보 제3자 제공)")

            # 주소: 완전 마스킹
            elif pii_type in ['address']:
                masking_method = "full"
                reasoning_steps.append(f"   - 위치정보는 외부 전송 시 완전히 보호하는 것이 좋습니다")
                reason = "외부 전송으로 주소 완전 마스킹을 권장합니다 (위치정보법)"
                cited_guidelines.append("위치정보의 보호 및 이용 등에 관한 법률")

            # 기타: 기본적으로 부분 마스킹
            else:
                masking_method = "partial"
                reasoning_steps.append(f"   - 외부 전송 시 {pii_type_kr}를 보호하는 것이 바람직합니다")
                reason = f"외부 전송으로 {pii_type_kr} 부분 마스킹을 권장합니다"
                cited_guidelines.append("개인정보보호법 제17조 (개인정보 제3자 제공)")

            reasoning_steps.append(f"5. 권장사항: {masking_method.upper()} 마스킹 (사외 전송)")

        # ==================== 사내 전송 규칙 ====================
        elif receiver_type == 'internal':
            reasoning_steps.append("4. 판단 근거:")
            reasoning_steps.append(f"   ✓ 사내 전송 - 업무 효율을 고려하여 최소한의 보호를 적용합니다")

            # 고유식별정보: 사내에서도 완전 마스킹
            if pii_type in ['jumin', 'account', 'passport', 'driver_license', 'card_number']:
                should_mask = True
                masking_method = "full"
                reasoning_steps.append(f"   - 고유식별정보는 조직 내부에서도 보호가 필요합니다")
                reason = "사내 전송이지만 고유식별정보 완전 마스킹을 권장합니다 (개인정보보호법 제24조)"
                cited_guidelines.append("개인정보보호법 제24조 (고유식별정보 처리 제한)")
                reasoning_steps.append(f"5. 권장사항: FULL 마스킹 (사내 전송)")

            # 이름: 사내는 부분 마스킹 (가독성 유지)
            elif pii_type in ['name', 'person']:
                should_mask = True
                masking_method = "partial"
                reasoning_steps.append(f"   - 업무 가독성을 유지하면서 이름을 부분적으로 보호합니다")
                reason = "사내 전송으로 이름 부분 마스킹을 권장합니다 (가독성 유지)"
                cited_guidelines.append("개인정보보호법 제29조 (안전조치 의무)")
                reasoning_steps.append(f"5. 권장사항: PARTIAL 마스킹 (사내 전송)")

            # 연락처, 주소: 사내는 마스킹 안 함 (업무 연속성)
            elif pii_type in ['email', 'phone', 'address', 'company']:
                should_mask = False
                masking_method = "none"
                reasoning_steps.append(f"   - 조직 내 원활한 협업을 위해 연락처 정보를 유지합니다")
                reasoning_steps.append(f"   - 업무 연속성 확보를 위한 조치입니다")
                reason = "사내 전송으로 마스킹하지 않습니다 (업무 연속성)"
                reasoning_steps.append(f"5. 권장사항: 마스킹 미적용 (사내 전송)")

            # 기타: 가이드라인 확인
            else:
                if 'mask_required' in guideline_keywords:
                    should_mask = True
                    masking_method = "partial"
                    reasoning_steps.append(f"   - 정책상 부분 마스킹이 권장됩니다")
                    reason = f"사내 전송이지만 {pii_type_kr} 부분 마스킹을 권장합니다"
                    cited_guidelines.append("개인정보보호법 제29조 (안전조치 의무)")
                    reasoning_steps.append(f"5. 권장사항: PARTIAL 마스킹")
                else:
                    should_mask = False
                    masking_method = "none"
                    reasoning_steps.append(f"   - 민감정보가 아닌 것으로 판단됩니다")
                    reason = "사내 전송으로 마스킹하지 않습니다"
                    reasoning_steps.append(f"5. 권장사항: 마스킹 미적용")

        # ==================== 알 수 없는 경우 (안전하게 외부로 처리) ====================
        else:
            should_mask = True
            masking_method = "partial"
            reasoning_steps.append("4. 판단 근거:")
            reasoning_steps.append(f"   ⚠️ 수신자 타입 불명 - 안전을 위해 부분 마스킹을 적용합니다")
            reason = f"수신자 타입이 불분명하여 {pii_type_kr} 부분 마스킹을 권장합니다"
            cited_guidelines.append("개인정보보호법 제29조 (안전조치 의무)")
            reasoning_steps.append(f"5. 권장사항: PARTIAL 마스킹 (안전 모드)")

        # 마스킹 미리보기 생성
        masked_value = None
        if should_mask:
            masked_value = _generate_masked_preview(pii.get('value', ''), pii_type, masking_method)

        reasoning_text = "\n".join(reasoning_steps)

        decisions[f"pii_{i}"] = {
            "pii_id": f"pii_{i}",
            "type": pii_type,
            "value": pii['value'],
            "should_mask": should_mask,
            "masking_method": masking_method,
            "masked_value": masked_value,
            "reason": reason,
            "reasoning": reasoning_text,
            "cited_guidelines": cited_guidelines,
            "guideline_matched": len(guideline_keywords) > 0,
            "confidence": 0.85,
            "risk_level": "high" if pii_type in ['jumin', 'account'] else "medium" if should_mask else "low"
        }

    return decisions


def _generate_masked_preview(value: str, pii_type: str, method: str) -> str:
    """마스킹 미리보기 생성 - MaskingRules 사용"""
    from app.utils.masking_rules import MaskingRules

    try:
        # method를 masking_level로 변환
        masking_level = 'full' if method == 'full' else 'partial'
        return MaskingRules.apply_masking(value, pii_type, masking_level)
    except Exception as e:
        print(f"❌ 마스킹 미리보기 생성 실패: {e}, 기본 마스킹 적용")
        # 폴백: 기본 마스킹
        if method == "full":
            return "***"
        else:
            return value[:2] + "***" if len(value) > 2 else "***"


def generate_summary(context: Dict, decisions: Dict, guides: List[Dict]) -> str:
    """AI 분석 요약 생성"""
    from app.vectordb.rag_masking import normalize_receiver_type

    masked_count = sum(1 for d in decisions.values() if d.get('should_mask', False))
    total_count = len(decisions)

    # receiver_type 정규화 (한글 → 영어)
    receiver_type = normalize_receiver_type(context)
    receiver_text = "외부" if receiver_type == "external" else "내부"

    summary = f"{receiver_text} 전송으로 분류되어, "

    if masked_count > 0:
        summary += f"{total_count}개 개인정보 중 {masked_count}개를 마스킹하도록 권장합니다. "
    else:
        summary += "마스킹이 필요한 개인정보가 없습니다. "

    if guides:
        summary += f"\n\nOpenAI Vector Store에서 관련 규정 {len(guides)}개를 참고했습니다."

    return summary


def fallback_analysis(request: RAGAnalysisRequest) -> JSONResponse:
    """Vector Store 사용 불가 시 기본 규칙 기반 분석"""

    decisions = {}
    context = request.context
    receiver_type = context.get('receiver_type', 'external')

    for i, pii in enumerate(request.detected_pii):
        pii_type = pii['type']
        pii_value = pii['value']
        masking_method = "none"
        reasoning_steps = []
        cited_guidelines = []

        pii_type_kr = {
            'email': '이메일 주소',
            'phone': '전화번호',
            'jumin': '주민등록번호',
            'account': '계좌번호',
            'passport': '여권번호',
            'driver_license': '운전면허번호'
        }.get(pii_type, pii_type)

        reasoning_steps.append(f"1. 컨텍스트 확인: {receiver_type} 전송")
        reasoning_steps.append(f"2. PII 유형: {pii_type_kr}")
        reasoning_steps.append("3. Vector Store 사용 불가 → 기본 규칙 적용")

        if receiver_type == 'external':
            should_mask = True
            reasoning_steps.append("4. 판단 근거:")

            if pii_type in ['jumin', 'account']:
                masking_method = "full"
                reasoning_steps.append(f"   - 개인정보보호법 제24조: 고유식별정보는 외부 전송 시 원칙적 금지")
                reason = "고유식별정보 외부 전송 금지 (개인정보보호법 제24조)"
                cited_guidelines.append("개인정보보호법 제24조 (고유식별정보 처리 제한)")
            else:
                masking_method = "partial"
                reasoning_steps.append(f"   - 개인정보보호법 제17조: 제3자 제공 시 최소화")
                reason = "개인정보 최소화 원칙 (개인정보보호법 제17조)"
                cited_guidelines.append("개인정보보호법 제17조 (개인정보 제3자 제공)")

            reasoning_steps.append(f"5. 최종 결정: {masking_method.upper()} 마스킹 적용")
        else:
            if pii_type in ['jumin', 'account']:
                should_mask = True
                masking_method = "full"
                reasoning_steps.append("4. 판단 근거:")
                reasoning_steps.append(f"   - 내부 전송이나 고유식별정보는 최소 처리")
                reasoning_steps.append(f"5. 최종 결정: FULL 마스킹 적용")
                reason = "민감정보 최소 처리 (개인정보보호법 제24조)"
                cited_guidelines.append("개인정보보호법 제24조 (고유식별정보 최소 처리)")
            else:
                should_mask = False
                masking_method = "none"
                reasoning_steps.append("4. 판단 근거:")
                reasoning_steps.append(f"   - 내부 전송이며 일반 개인정보")
                reasoning_steps.append(f"5. 최종 결정: 마스킹 미적용")
                reason = "내부 전송으로 마스킹 불필요"

        masked_value = None
        if should_mask:
            masked_value = _generate_masked_preview(pii_value, pii_type, masking_method)

        reasoning_text = "\n".join(reasoning_steps)

        decisions[f"pii_{i}"] = {
            "pii_id": f"pii_{i}",
            "type": pii_type,
            "value": pii_value,
            "should_mask": should_mask,
            "masking_method": masking_method,
            "masked_value": masked_value,
            "reason": reason,
            "reasoning": reasoning_text,
            "cited_guidelines": cited_guidelines,
            "confidence": 0.8,
            "risk_level": "high" if pii_type in ['jumin', 'account'] else "medium" if should_mask else "low"
        }

    masked_count = sum(1 for d in decisions.values() if d['should_mask'])

    summary = f"기본 규칙에 따라 {len(decisions)}개 개인정보 중 {masked_count}개 마스킹을 권장합니다."

    return JSONResponse({
        "success": True,
        "data": {
            "masking_decisions": decisions,
            "summary": summary,
            "relevant_guides": [],
            "total_guides_found": 0,
            "fallback": True
        }
    })
