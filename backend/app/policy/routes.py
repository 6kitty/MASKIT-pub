"""
정책 관리 라우터
- 정책 추가/수정/삭제
- 멀티모달 파일 업로드 (PDF, 이미지)
- 임베딩 생성 및 VectorDB 저장
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime,timedelta
import hashlib
import fitz  # PyMuPDF
from dotenv import load_dotenv
from app.auth.auth_utils import get_current_policy_admin, get_current_user
from app.audit.logger import AuditLogger
from app.audit.models import AuditEventType, AuditSeverity
from app.database.mongodb import get_db
from fastapi.background import BackgroundTasks
def get_kst_now():
    """한국 표준시(KST) 반환"""
    return datetime.utcnow() + timedelta(hours=9)
# OpenAI imports
try:
    from openai import AsyncOpenAI
    from pyzerox import zerox
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Database imports
from app.database.mongodb import get_db
from app.policy.models import PolicyDocument, PolicyMetadata, PolicyResponse

# Background tasks
from app.policy.background_tasks import process_policy_background, get_task_status, clear_old_tasks
from fastapi import BackgroundTasks

load_dotenv()

router = APIRouter(prefix="/api/policies", tags=["Policy Management"])

# 설정
# 절대 경로 사용
BASE_DIR = Path(__file__).parent.parent.parent.parent  # enterprise-guardcap 루트
UPLOAD_DIR = BASE_DIR / "backend" / "app" / "uploads" / "policies"
TEMP_DIR = BASE_DIR / "backend" / "app" / "uploads" / "temp"
PROCESSED_DIR = BASE_DIR / "backend" / "app" / "uploads" / "processed"
STAGING_DIR = BASE_DIR / "backend" / "app" / "rag" / "data" / "staging"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 정책 스키마 캐시
_policy_schemas_cache = None
_cache_timestamp = None
CACHE_EXPIRY_SECONDS = 3600  # 1시간

# OpenAI 클라이언트 초기화
if OPENAI_AVAILABLE:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = AsyncOpenAI(api_key=openai_api_key)
    else:
        openai_client = None
else:
    openai_client = None


class PolicyProcessor:
    """정책 문서 처리 클래스"""

    def __init__(self):
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

    async def process_pdf(self, file_path: str) -> dict:
        """PDF 파일을 처리하여 텍스트 추출"""
        try:
            # PDF 정보 확인
            doc = fitz.open(file_path)
            page_count = len(doc)
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            doc.close()

            # 작은 PDF는 Zerox 사용 (OCR + Vision)
            if page_count <= 50 and file_size_mb <= 20:
                if OPENAI_AVAILABLE and openai_client:
                    try:
                        result = await zerox(
                            file_path=file_path,
                            model=self.vision_model,
                            output_dir=str(TEMP_DIR),
                            cleanup=True,
                        )
                        markdown = result.get("content", "") if isinstance(result, dict) else str(result)
                        return {"text": markdown, "method": "zerox_ocr"}
                    except Exception as e:
                        print(f"Zerox failed: {e}, falling back to PyMuPDF")

            # Fallback: PyMuPDF로 텍스트 추출
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            return {"text": text, "method": "pymupdf"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 처리 실패: {str(e)}")

    async def process_image(self, file_path: str) -> dict:
        """이미지 파일을 OCR 처리"""
        if not OPENAI_AVAILABLE or not openai_client:
            raise HTTPException(status_code=400, detail="OpenAI API가 설정되지 않았습니다")

        try:
            # Vision API로 이미지 분석
            with open(file_path, "rb") as image_file:
                import base64
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            response = await openai_client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "이미지에서 모든 텍스트를 추출하고 정책 내용을 구조화하여 마크다운으로 작성해주세요."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4000
            )

            text = response.choices[0].message.content
            return {"text": text, "method": "vision_api"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"이미지 처리 실패: {str(e)}")

    async def extract_policy_metadata(self, text: str, title: str, authority: str) -> dict:
        """정책 텍스트에서 메타데이터 추출"""
        if not OPENAI_AVAILABLE or not openai_client:
            # OpenAI 없이 기본 메타데이터만 반환
            return {
                "title": title,
                "authority": authority,
                "summary": text[:500],
                "keywords": [],
                "entity_types": []
            }

        prompt = f"""
다음 정책 문서에서 메타데이터를 추출하세요.

정책 제목: {title}
발행 기관: {authority}

문서 내용:
{text[:4000]}

다음 JSON 형식으로 반환하세요:
{{
    "summary": "정책 요약 (200자 이내)",
    "keywords": ["키워드1", "키워드2", ...],
    "entity_types": ["개인정보 유형1", "개인정보 유형2", ...],
    "scenarios": ["적용 시나리오1", "적용 시나리오2", ...],
    "directives": ["실행 지침1", "실행 지침2", ...]
}}

반드시 유효한 JSON만 반환하세요.
"""

        try:
            response = await openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            content = response.choices[0].message.content.strip()
            # JSON 추출
            import re
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

            metadata = json.loads(content)
            metadata["title"] = title
            metadata["authority"] = authority

            return metadata

        except Exception as e:
            print(f"메타데이터 추출 실패: {e}")
            return {
                "title": title,
                "authority": authority,
                "summary": text[:500],
                "keywords": [],
                "entity_types": []
            }



@router.post("/upload")
async def upload_policy_file(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    authority: str = Form(default="내부"),
    description: str = Form(default=""),
        db = Depends(get_db),
    current_user = Depends(get_current_policy_admin)
):
    """
    정책 파일 업로드 (PDF, 이미지 등)
    멀티모달 처리 및 임베딩 생성
    """

    # 파일 확장자 확인
    file_ext = os.path.splitext(file.filename)[1].lower()
    supported_exts = ['.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff']

    if file_ext not in supported_exts:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(supported_exts)}"
        )

    # 파일 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename

    try:
        # 파일 저장
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 파일 처리
        processor = PolicyProcessor()

        if file_ext == '.pdf':
            result = await processor.process_pdf(str(file_path))
        else:
            result = await processor.process_image(str(file_path))

        extracted_text = result["text"]
        processing_method = result["method"]

        # 메타데이터 추출
        metadata_dict = await processor.extract_policy_metadata(
            extracted_text,
            title,
            authority
        )

        # PolicyMetadata 모델로 변환
        metadata = PolicyMetadata(**metadata_dict)

        # 정책 ID 생성
        policy_id = hashlib.md5(f"{title}_{timestamp}".encode()).hexdigest()[:12]

        # PolicyDocument 모델 생성
        policy_doc = PolicyDocument(
            policy_id=policy_id,
            title=title,
            authority=authority,
            description=description,
            original_filename=file.filename,
            saved_filename=safe_filename,
            file_type=file_ext,
            file_size_mb=len(content) / (1024 * 1024),
            processing_method=processing_method,
            extracted_text=extracted_text,
            metadata=metadata,
            created_by=None  # TODO: 현재 사용자 이메일
        )

        # MongoDB에 저장
        await db["policies"].insert_one(policy_doc.model_dump(mode='json'))

        # ✅ 감사 로그 기록
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_UPLOAD,
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 업로드: {title}",
            resource_type="policy",
            resource_id=policy_id,
            details={
                "title": title,
                "authority": authority,
                "file_type": file_ext,
                "file_size_mb": len(content) / (1024 * 1024)
            },
            request=request,
            severity=AuditSeverity.INFO
        )

        # 백업용으로 파일에도 저장
        processed_file = PROCESSED_DIR / f"policy_{policy_id}.json"
        with open(processed_file, "w", encoding="utf-8") as f:
            json.dump(policy_doc.model_dump(mode='json'), f, ensure_ascii=False, indent=2)

        # 백그라운드에서 가이드라인 추출 및 VectorDB 임베딩 실행
        background_tasks.add_task(
            process_policy_background,
            policy_id,
            policy_doc.model_dump(mode='json'),
            db
        )

        return JSONResponse({
            "success": True,
            "message": "정책 파일이 성공적으로 업로드되었습니다. 백그라운드에서 가이드라인 추출 중입니다.",
            "data": {
                "policy_id": policy_id,
                "title": title,
                "authority": authority,
                "file_type": file_ext,
                "processing_method": processing_method,
                "metadata": metadata_dict,
                "text_length": len(extracted_text),
                "created_at": policy_doc.created_at.isoformat(),
                "task_id": f"policy_{policy_id}"
            }
        })

    except Exception as e:
        # 오류 발생 시 업로드된 파일 삭제
        if file_path.exists():
            file_path.unlink()
        # ✅ 실패 로그
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_UPLOAD,
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 업로드 실패: {title}",
            resource_type="policy",
            request=request,
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류 발생: {str(e)}")


@router.get("/list")
async def list_policies(
    skip: int = 0,
    limit: int = 50,
    authority: str = None,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """정책 목록 조회"""
    try:
        print(f"\n[Policy List] ===== 정책 목록 조회 시작 =====")
        print(f"[Policy List] skip={skip}, limit={limit}, authority={authority}")
        
        # 필터 조건
        query = {}
        if authority and authority != 'all':
            query["authority"] = authority
            print(f"[Policy List] 필터 조건: {query}")

        # 총 개수 조회
        total = await db["policies"].count_documents(query)
        print(f"[Policy List] 총 개수: {total}")

        # 정책 목록 조회 (전체 텍스트 제외)
        cursor = db["policies"].find(
            query,
            {
                "extracted_text": 0  # 전체 텍스트는 제외
            }
        ).sort("created_at", -1).skip(skip).limit(limit)

        policies = []
        async for doc in cursor:
            try:
                # _id를 문자열로 변환
                doc["_id"] = str(doc["_id"])

                # datetime 필드를 ISO 문자열로 변환
                for key in ["created_at", "updated_at", "processed_at", "vector_store_synced_at"]:
                    if key in doc and doc[key] is not None:
                        if hasattr(doc[key], 'isoformat'):
                            doc[key] = doc[key].isoformat()

                policies.append(doc)
                print(f"[Policy List] 정책 추가: {doc.get('title', 'Unknown')}")
            except Exception as e:
                print(f"[Policy List] ⚠️ 정책 변환 오류: {e}")
                continue

        print(f"[Policy List] ✅ {len(policies)}개 정책 조회 완료")
        print(f"[Policy List] ===== 정책 목록 조회 끝 =====\n")

        return JSONResponse({
            "success": True,
            "data": {
                "policies": policies,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        })

    except Exception as e:
        print(f"[Policy List] ❌ 정책 목록 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"정책 목록 조회 실패: {str(e)}"
        )


# ===== 정책 스키마 로딩 및 캐싱 =====

async def load_policy_schemas_from_staging():
    """staging 디렉토리에서 정책 스키마 로드"""
    global _policy_schemas_cache, _cache_timestamp

    # 캐시 유효성 확인
    if _policy_schemas_cache and _cache_timestamp:
        elapsed = (datetime.now() - _cache_timestamp).total_seconds()
        if elapsed < CACHE_EXPIRY_SECONDS:
            print(f"✅ 캐시된 정책 스키마 반환 (캐시 유효 시간: {CACHE_EXPIRY_SECONDS - elapsed:.0f}초 남음)")
            return _policy_schemas_cache

    print(f"📂 Staging 디렉토리에서 정책 스키마 로딩 중... ({STAGING_DIR})")

    if not STAGING_DIR.exists():
        print(f"⚠️ Staging 디렉토리가 존재하지 않습니다: {STAGING_DIR}")
        return []

    schemas = []
    jsonl_files = list(STAGING_DIR.glob("*.jsonl"))

    if not jsonl_files:
        print(f"⚠️ JSONL 파일이 없습니다: {STAGING_DIR}")
        return []

    print(f"📄 {len(jsonl_files)}개의 JSONL 파일 발견")

    for jsonl_file in jsonl_files:
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        schema = json.loads(line)
                        schemas.append({
                            "source_file": jsonl_file.name,
                            "line_number": line_num,
                            **schema
                        })
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON 파싱 오류 ({jsonl_file.name}:{line_num}): {e}")
        except Exception as e:
            print(f"⚠️ 파일 읽기 오류 ({jsonl_file.name}): {e}")

    # 캐시 업데이트
    _policy_schemas_cache = schemas
    _cache_timestamp = datetime.now()

    print(f"✅ {len(schemas)}개의 정책 스키마 로드 완료 (캐시됨)")
    return schemas


@router.get("/schemas")
async def get_policy_schemas(
    skip: int = 0,
    limit: int = 50,
    refresh_cache: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    정책 스키마 목록 조회 (staging 디렉토리에서 로드)
    - skip: 건너뛸 개수
    - limit: 반환할 최대 개수  
    - refresh_cache: True면 캐시 무시하고 재로드
    """
    global _policy_schemas_cache, _cache_timestamp

    # 캐시 강제 새로고침
    if refresh_cache:
        _policy_schemas_cache = None
        _cache_timestamp = None

    schemas = await load_policy_schemas_from_staging()

    total = len(schemas)
    schemas_page = schemas[skip:skip + limit]

    cache_expires_in = 0
    if _cache_timestamp:
        cache_expires_in = CACHE_EXPIRY_SECONDS - (datetime.now() - _cache_timestamp).total_seconds()

    return JSONResponse({
        "success": True,
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "cached": _cache_timestamp is not None,
            "cache_expires_in": max(0, cache_expires_in),
            "schemas": schemas_page
        }
    })

@router.get("/{policy_id}")
async def get_policy_detail(
    policy_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """정책 상세 조회"""
    try:
        print(f"\n[Policy Detail] ===== 정책 상세 조회 시작 =====")
        print(f"[Policy Detail] Policy ID: {policy_id}")
        
        policy = await db["policies"].find_one({"policy_id": policy_id})

        if not policy:
            print(f"[Policy Detail] ❌ 정책을 찾을 수 없음: {policy_id}")
            raise HTTPException(
                status_code=404, 
                detail="정책을 찾을 수 없습니다"
            )

        # _id를 문자열로 변환
        policy["_id"] = str(policy["_id"])

        # ✅ datetime 객체를 ISO 문자열로 변환
        datetime_fields = ["created_at", "updated_at", "vector_store_synced_at"]
        for field in datetime_fields:
            if field in policy and hasattr(policy[field], "isoformat"):
                policy[field] = policy[field].isoformat()

        # ✅ guidelines 내부의 datetime 필드도 변환
        if "guidelines" in policy and policy["guidelines"]:
            for guide in policy["guidelines"]:
                if isinstance(guide, dict):
                    for key, value in guide.items():
                        if hasattr(value, "isoformat"):
                            guide[key] = value.isoformat()

        print(f"[Policy Detail] ✅ 정책 조회 성공: {policy.get('title')}")
        print(f"[Policy Detail] ===== 정책 상세 조회 끝 =====\n")

        return JSONResponse({
            "success": True,
            "data": policy
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Policy Detail] ❌ 정책 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"정책 조회 실패: {str(e)}"
        )

@router.delete("/{policy_id}")
async def delete_policy(
    policy_id: str,
    request: Request,  # ✅ Request 추가
    db = Depends(get_db),
    current_user = Depends(get_current_policy_admin)
):
    """정책 삭제"""
    try:
        # 정책 조회
        policy = await db["policies"].find_one({"policy_id": policy_id})

        if not policy:
            raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다")

        policy_title = policy.get("title", policy_id)

        # 원본 파일 삭제
        original_file = UPLOAD_DIR / policy["saved_filename"]
        if original_file.exists():
            original_file.unlink()

        # 백업 파일 삭제
        backup_file = PROCESSED_DIR / f"policy_{policy_id}.json"
        if backup_file.exists():
            backup_file.unlink()

        # MongoDB에서 삭제
        delete_result = await db["policies"].delete_one({"policy_id": policy_id})
        print(f"[Policy Delete] MongoDB 삭제 결과: {delete_result.deleted_count}개")

        if delete_result.deleted_count == 0:
            print(f"[Policy Delete] ⚠️ MongoDB에서 삭제 실패")
            raise HTTPException(status_code=500, detail="정책 삭제에 실패했습니다")

        # ✅ 감사 로그 기록
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_DELETE,
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 삭제: {policy_title}",
            resource_type="policy",
            resource_id=policy_id,
            details={"title": policy_title},
            request=request,
            severity=AuditSeverity.WARNING
        )

        return JSONResponse({
            "success": True,
            "message": "정책이 성공적으로 삭제되었습니다"
        })

    except HTTPException:
        raise
    except Exception as e:
        # ✅ 실패 로그
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_DELETE,
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 삭제 실패: {policy_id}",
            resource_type="policy",
            resource_id=policy_id,
            request=request,
            success=False,
            error_message=str(e),
            severity=AuditSeverity.ERROR
        )
        raise HTTPException(status_code=500, detail=f"정책 삭제 실패: {str(e)}")

@router.patch("/{policy_id}/text")
async def update_policy_text(
    policy_id: str,
    text_data: dict,
    request: Request,  # ✅ Request 추가
    current_user = Depends(get_current_policy_admin),
    db = Depends(get_db)
):
    """
    정책 추출 텍스트 수정
    """
    try:
        print(f"\n[Policy] ===== 텍스트 수정 시작 =====")
        print(f"[Policy] Policy ID: {policy_id}")
        
        # 새 텍스트 가져오기
        new_text = text_data.get("extracted_text")
        
        if not new_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="extracted_text 필드가 필요합니다"
            )
        
        print(f"[Policy] 새 텍스트 길이: {len(new_text)} 자")
        
        # 정책 존재 확인
        policy = await db["policies"].find_one({"policy_id": policy_id})
        policy_title = policy.get("title", policy_id)

        if not policy:
            print(f"[Policy] ❌ 정책을 찾을 수 없음: {policy_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="정책을 찾을 수 없습니다"
            )
        
        # 텍스트 업데이트
        result = await db["policies"].update_one(
            {"policy_id": policy_id},
            {
                "$set": {
                    "extracted_text": new_text,
                    "updated_at": get_kst_now()
                }
            }
        )
        
        print(f"[Policy] matched_count: {result.matched_count}")
        print(f"[Policy] modified_count: {result.modified_count}")
        
        if result.modified_count == 0 and result.matched_count == 0:
            print(f"[Policy] ❌ 업데이트 실패")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="정책 업데이트에 실패했습니다"
            )
        
        print(f"[Policy] ✅ 텍스트 수정 완료")
        print(f"[Policy] ===== 텍스트 수정 끝 =====\n")


        # ✅ 감사 로그 기록
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_UPDATE,  # ✅ 새 이벤트 타입
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 텍스트 수정: {policy_title}",
            resource_type="policy",
            resource_id=policy_id,
            details={
                "title": policy_title,
                "text_length": len(new_text)
            },
            request=request,
            severity=AuditSeverity.INFO
        )

        return JSONResponse({
            "success": True,
            "message": "텍스트가 성공적으로 수정되었습니다",
            "data": {
                "policy_id": policy_id,
                "text_length": len(new_text),
                "updated_at": get_kst_now().isoformat()
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Policy] ❌ 텍스트 수정 오류: {e}")
        # ✅ 실패 로그
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_UPDATE,
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 텍스트 수정 실패: {policy_id}",
            resource_type="policy",
            resource_id=policy_id,
            request=request,
            success=False,
            error_message=str(e),
            severity=AuditSeverity.ERROR
        )
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"텍스트 수정 중 오류가 발생했습니다: {str(e)}"
        )

@router.patch("/{policy_id}/guidelines")
async def update_policy_guidelines(
    policy_id: str,
    guidelines_data: dict,
    request: Request,
    current_user = Depends(get_current_policy_admin),
    db = Depends(get_db)
):
    """
    정책 가이드라인 수정 - 동기화 상태 초기화됨
    """
    try:
        print(f"\n[Policy] ===== 가이드라인 수정 시작 =====")
        print(f"[Policy] Policy ID: {policy_id}")

        # 새 가이드라인 가져오기
        new_guidelines = guidelines_data.get("guidelines")

        if new_guidelines is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="guidelines 필드가 필요합니다"
            )

        print(f"[Policy] 새 가이드라인 개수: {len(new_guidelines)} 개")

        # 정책 존재 확인
        policy = await db["policies"].find_one({"policy_id": policy_id})
        policy_title = policy.get("title", policy_id)


        if not policy:
            print(f"[Policy] ❌ 정책을 찾을 수 없음: {policy_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="정책을 찾을 수 없습니다"
            )

        # 가이드라인 업데이트 및 동기화 상태 초기화
        result = await db["policies"].update_one(
            {"policy_id": policy_id},
            {
                "$set": {
                    "guidelines": new_guidelines,
                    "guidelines_count": len(new_guidelines),
                    "updated_at": get_kst_now(),
                    # 동기화 상태 초기화 - 다시 동기화 필요
                    "vector_store_file_id": None,
                    "vector_store_synced_at": None
                }
            }
        )

        print(f"[Policy] matched_count: {result.matched_count}")
        print(f"[Policy] modified_count: {result.modified_count}")

        if result.modified_count == 0 and result.matched_count == 0:
            print(f"[Policy] ❌ 업데이트 실패")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="정책 업데이트에 실패했습니다"
            )

        print(f"[Policy] ✅ 가이드라인 수정 완료 (동기화 상태 초기화됨)")
        print(f"[Policy] ===== 가이드라인 수정 끝 =====\n")

        # ✅ 감사 로그 기록
        await AuditLogger.log(
            event_type=AuditEventType.POLICY_UPDATE,
            user_email=current_user["email"],
            user_role=current_user.get("role", "policy_admin"),
            action=f"정책 가이드라인 수정: {policy_title}",
            resource_type="policy",
            resource_id=policy_id,
            details={
                "title": policy_title,
                "guidelines_count": len(new_guidelines)
            },
            request=request,
            severity=AuditSeverity.WARNING  # 동기화 필요
        )

        return JSONResponse({
            "success": True,
            "message": "가이드라인이 성공적으로 수정되었습니다. Vector Store에 다시 동기화가 필요합니다.",
            "data": {
                "policy_id": policy_id,
                "guidelines_count": len(new_guidelines),
                "updated_at": get_kst_now().isoformat(),
                "sync_required": True
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Policy] ❌ 가이드라인 수정 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"가이드라인 수정 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/stats/summary")
async def get_policy_stats(db = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """정책 통계 조회"""
    try:
        # 총 정책 수
        total_policies = await db["policies"].count_documents({})

        # 총 엔티티 수 (entities 컬렉션에서 조회)
        total_entities = await db.get_collection("entities").count_documents({})

        # 기관별 집계
        authority_pipeline = [
            {"$group": {"_id": "$authority", "count": {"$sum": 1}}}
        ]
        authority_cursor = db["policies"].aggregate(authority_pipeline)
        authority_count = {}
        async for doc in authority_cursor:
            authority_count[doc["_id"]] = doc["count"]

        # 파일 타입별 집계
        file_type_pipeline = [
            {"$group": {"_id": "$file_type", "count": {"$sum": 1}}}
        ]
        file_type_cursor = db["policies"].aggregate(file_type_pipeline)
        file_type_count = {}
        async for doc in file_type_cursor:
            file_type_count[doc["_id"]] = doc["count"]

        return JSONResponse({
            "success": True,
            "data": {
                "total_policies": total_policies,
                "total_entities": total_entities,
                "by_authority": authority_count,
                "by_file_type": file_type_count
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/tasks/{task_id}/status")
async def get_background_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """백그라운드 작업 상태 조회"""
    # 오래된 작업 정리
    clear_old_tasks()

    status = get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    return JSONResponse({
        "success": True,
        "data": status
    })


@router.post("/batch/process")
async def batch_process_policies(
    policy_ids: List[str],
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    여러 정책을 배치로 백그라운드 처리
    - 페이지를 나가도 백엔드에서 계속 처리됨
    """
    try:
        batch_task_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        processed = []
        failed = []

        for policy_id in policy_ids:
            # 정책 조회
            policy = await db["policies"].find_one({"policy_id": policy_id})
            if not policy:
                failed.append({"policy_id": policy_id, "reason": "정책을 찾을 수 없음"})
                continue

            # ObjectId 변환
            policy["_id"] = str(policy["_id"])

            # datetime 변환
            for key in ["created_at", "updated_at", "processed_at"]:
                if key in policy and policy[key] is not None:
                    if hasattr(policy[key], 'isoformat'):
                        policy[key] = policy[key].isoformat()

            # 백그라운드 작업 추가
            background_tasks.add_task(
                process_policy_background,
                policy_id,
                policy,
                db
            )
            processed.append({
                "policy_id": policy_id,
                "task_id": f"policy_{policy_id}",
                "title": policy.get("title", "")
            })

        return JSONResponse({
            "success": True,
            "message": f"{len(processed)}개 정책이 백그라운드에서 처리 중입니다. 페이지를 나가도 처리가 계속됩니다.",
            "data": {
                "batch_task_id": batch_task_id,
                "processed": processed,
                "failed": failed,
                "total_queued": len(processed)
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"배치 처리 시작 실패: {str(e)}")


@router.get("/tasks/all")
async def get_all_task_status(current_user: dict = Depends(get_current_user)):
    """모든 백그라운드 작업 상태 조회"""
    from app.policy.background_tasks import task_status

    # 오래된 작업 정리
    clear_old_tasks()

    return JSONResponse({
        "success": True,
        "data": {
            "tasks": list(task_status.values()),
            "total": len(task_status)
        }
    })


# ===== OpenAI Vector Store 동기화 =====

from openai import OpenAI
import tempfile

# OpenAI 동기 클라이언트 (Vector Store 관리용)
_openai_sync_client = None

def get_openai_sync_client():
    """OpenAI 동기 클라이언트 반환"""
    global _openai_sync_client
    if _openai_sync_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _openai_sync_client = OpenAI(api_key=api_key)
    return _openai_sync_client


@router.post("/sync/vector-store")
async def sync_policies_to_vector_store(
    db = Depends(get_db),
    current_user = Depends(get_current_policy_admin)
):
    """
    MongoDB의 모든 정책을 OpenAI Vector Store와 동기화
    - MongoDB에 있지만 Vector Store에 없는 정책 추가
    - 동기화 상태 반환
    """
    try:
        client = get_openai_sync_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다")

        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
        if not vector_store_id:
            raise HTTPException(status_code=500, detail="OPENAI_VECTOR_STORE_ID가 설정되지 않았습니다")

        print(f"\n[Sync] ===== Vector Store 동기화 시작 =====")
        print(f"[Sync] Vector Store ID: {vector_store_id}")

        # 1. Vector Store의 기존 파일 목록 조회
        existing_files = {}
        try:
            vs_files = client.vector_stores.files.list(vector_store_id=vector_store_id)
            for f in vs_files.data:
                # 파일 정보에서 policy_id 추출 시도
                try:
                    file_info = client.files.retrieve(f.id)
                    existing_files[file_info.filename] = f.id
                except:
                    pass
            print(f"[Sync] Vector Store 기존 파일: {len(existing_files)}개")
        except Exception as e:
            print(f"[Sync] ⚠️ Vector Store 파일 목록 조회 실패: {e}")

        # 2. MongoDB에서 모든 정책 조회
        cursor = db["policies"].find({})
        policies = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            policies.append(doc)

        print(f"[Sync] MongoDB 정책: {len(policies)}개")

        # 3. 동기화 실행
        synced = []
        skipped = []
        failed = []

        for policy in policies:
            policy_id = policy.get("policy_id", "")
            title = policy.get("title", "Unknown")
            filename = f"policy_{policy_id}.txt"

            # 이미 Vector Store에 있으면 스킵
            if filename in existing_files:
                skipped.append({
                    "policy_id": policy_id,
                    "title": title,
                    "reason": "이미 동기화됨",
                    "file_id": existing_files[filename]
                })
                continue

            # 텍스트 준비
            extracted_text = policy.get("extracted_text", "")
            if not extracted_text:
                failed.append({
                    "policy_id": policy_id,
                    "title": title,
                    "reason": "추출된 텍스트 없음"
                })
                continue

            # 메타데이터와 함께 텍스트 구성
            policy_content = f"""정책 제목: {title}
발행 기관: {policy.get('authority', 'Unknown')}
정책 ID: {policy_id}

=== 정책 내용 ===
{extracted_text[:50000]}
"""

            try:
                # 임시 파일 생성 및 업로드
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                    tmp.write(policy_content)
                    tmp_path = tmp.name

                # OpenAI에 파일 업로드
                with open(tmp_path, 'rb') as f:
                    uploaded_file = client.files.create(
                        file=f,
                        purpose="assistants"
                    )

                # Vector Store에 파일 추가
                client.vector_stores.files.create(
                    vector_store_id=vector_store_id,
                    file_id=uploaded_file.id
                )

                # 임시 파일 삭제
                os.unlink(tmp_path)

                # MongoDB에 동기화 상태 업데이트
                await db["policies"].update_one(
                    {"policy_id": policy_id},
                    {"$set": {
                        "vector_store_file_id": uploaded_file.id,
                        "vector_store_synced_at": get_kst_now()
                    }}
                )

                synced.append({
                    "policy_id": policy_id,
                    "title": title,
                    "file_id": uploaded_file.id
                })
                print(f"[Sync] ✅ 동기화 완료: {title}")

            except Exception as e:
                failed.append({
                    "policy_id": policy_id,
                    "title": title,
                    "reason": str(e)
                })
                print(f"[Sync] ❌ 동기화 실패: {title} - {e}")

        print(f"[Sync] ===== 동기화 완료 =====")
        print(f"[Sync] 동기화: {len(synced)}개, 스킵: {len(skipped)}개, 실패: {len(failed)}개\n")

        return JSONResponse({
            "success": True,
            "message": f"동기화 완료: {len(synced)}개 추가, {len(skipped)}개 스킵, {len(failed)}개 실패",
            "data": {
                "synced": synced,
                "skipped": skipped,
                "failed": failed,
                "total_in_mongodb": len(policies),
                "total_in_vector_store": len(existing_files) + len(synced),
                "vector_store_id": vector_store_id
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Sync] ❌ 동기화 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"동기화 실패: {str(e)}")


@router.get("/sync/status")
async def get_sync_status(db = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    MongoDB와 OpenAI Vector Store 동기화 상태 확인
    """
    try:
        client = get_openai_sync_client()
        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")

        # MongoDB 정책 수
        mongo_count = await db["policies"].count_documents({})
        mongo_synced = await db["policies"].count_documents({"vector_store_file_id": {"$exists": True}})

        # Vector Store 정보
        vs_info = None
        vs_file_count = 0
        if client and vector_store_id:
            try:
                vs = client.vector_stores.retrieve(vector_store_id)
                vs_info = {
                    "id": vs.id,
                    "name": vs.name,
                    "status": vs.status,
                    "file_counts": {
                        "total": vs.file_counts.total if hasattr(vs.file_counts, 'total') else 0,
                        "completed": vs.file_counts.completed if hasattr(vs.file_counts, 'completed') else 0,
                        "in_progress": vs.file_counts.in_progress if hasattr(vs.file_counts, 'in_progress') else 0,
                        "failed": vs.file_counts.failed if hasattr(vs.file_counts, 'failed') else 0
                    }
                }
                vs_file_count = vs.file_counts.total if hasattr(vs.file_counts, 'total') else 0
            except Exception as e:
                print(f"Vector Store 조회 실패: {e}")

        return JSONResponse({
            "success": True,
            "data": {
                "mongodb": {
                    "total_policies": mongo_count,
                    "synced_to_vector_store": mongo_synced,
                    "not_synced": mongo_count - mongo_synced
                },
                "vector_store": vs_info,
                "sync_needed": mongo_count - mongo_synced > 0
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"동기화 상태 조회 실패: {str(e)}")


@router.delete("/sync/vector-store/{policy_id}")
async def remove_policy_from_vector_store(
    policy_id: str,
    db = Depends(get_db),
    current_user = Depends(get_current_policy_admin)
):
    """
    특정 정책을 Vector Store에서 제거
    """
    try:
        client = get_openai_sync_client()
        if not client:
            raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다")

        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")

        # MongoDB에서 정책 조회
        policy = await db["policies"].find_one({"policy_id": policy_id})
        if not policy:
            raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다")

        file_id = policy.get("vector_store_file_id")
        if not file_id:
            return JSONResponse({
                "success": True,
                "message": "이 정책은 Vector Store에 동기화되지 않았습니다"
            })

        # Vector Store에서 파일 제거
        try:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            # OpenAI 파일도 삭제
            client.files.delete(file_id)
        except Exception as e:
            print(f"Vector Store 파일 삭제 오류: {e}")

        # MongoDB 업데이트
        await db["policies"].update_one(
            {"policy_id": policy_id},
            {"$unset": {"vector_store_file_id": "", "vector_store_synced_at": ""}}
        )

        return JSONResponse({
            "success": True,
            "message": f"정책 '{policy.get('title')}'이(가) Vector Store에서 제거되었습니다"
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector Store 제거 실패: {str(e)}")