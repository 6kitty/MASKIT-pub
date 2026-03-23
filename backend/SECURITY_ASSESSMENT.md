# MASKIT API 보안 취약점 점검 보고서

> **점검 일자:** 2026-03-24
> **점검 방법:** OWASP API Security Top 10 기반 자동화 DAST
> **점검 도구:** pytest + httpx (custom security test suite)
> **점검 대상:** Enterprise GuardCAP API (FastAPI)
> **총 소요 시간:** 5.65초

---

## 1. 요약 (Executive Summary)

| 항목 | 수치 |
|------|------|
| 총 테스트 케이스 | 74개 |
| 취약점 발견 (FAIL) | **19개** |
| 정상 차단 확인 (PASS) | 30개 |
| 픽스처 오류 (ERROR) | 25개 ¹ |
| 취약점 발견율 | **38.8%** (실행 완료 기준) |

> ¹ 테스트 계정 이메일 도메인 오류(`.test` TLD 미지원)로 인한 픽스처 실패. 실제 취약점 아님. 수정 완료.

### 심각도 분포

| 심각도 | 건수 | CVSS 추정 | 분류 기준 |
|--------|------|-----------|----------|
| 🔴 Critical | 5건 | 9.1 | 인증 없이 민감 데이터 직접 접근 |
| 🟠 High | 8건 | 7.5 | 내부 정책·엔티티 정보 무단 노출 |
| 🟡 Medium | 2건 | 5.3 | 시스템 상태 정보 노출 |
| 🟣 기타 | 4건 | — | CORS, 토큰 검증 부분 취약 |

---

## 2. 취약점 상세

### 2-1. Critical: 비인증 원본 이메일 접근

**OWASP API2:2023 Broken Authentication**

| 항목 | 내용 |
|------|------|
| 엔드포인트 | `GET /api/v1/files/original_emails` |
| 엔드포인트 | `GET /api/v1/files/original_emails/{email_id}` |
| 엔드포인트 | `GET /api/v1/files/original_emails/{email_id}/attachment/{filename}` |
| 재현 조건 | Authorization 헤더 없이 요청 |
| 실제 응답 | **200 OK** (이메일 내용 반환) |
| 기대 응답 | 401 Unauthorized |

**위험성:** DLP 시스템이 처리하는 원본 이메일(PII 포함)이 인증 없이 전체 노출됨. 외부 공격자가 직접 URL 접근으로 전체 이메일 데이터베이스 열람 가능.

---

### 2-2. Critical: 비인증 마스킹 이메일 접근

**OWASP API2:2023 Broken Authentication**

| 항목 | 내용 |
|------|------|
| 엔드포인트 | `GET /api/v1/files/masked_emails/{email_id}` |
| 재현 조건 | Authorization 헤더 없이 요청 |
| 실제 응답 | **200 OK** |
| 기대 응답 | 401 Unauthorized |

**위험성:** 마스킹 처리 결과물도 외부에 그대로 노출됨. 마스킹 패턴 역분석 가능성 존재.

---

### 2-3. High: DLP 정책 및 PII 엔티티 정보 무단 노출 (8건)

**OWASP API2:2023 Broken Authentication**

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/policies/list` | DLP 정책 전체 목록 |
| `GET /api/policies/schemas` | 정책 스키마 구조 |
| `GET /api/policies/stats/summary` | 정책 통계 |
| `GET /api/policies/tasks/all` | 백그라운드 작업 목록 |
| `GET /api/entities/list` | PII 인식 엔티티 목록 |
| `GET /api/entities/categories` | 엔티티 카테고리 |
| `GET /api/entities/recognizers` | 인식기 상세 정보 |
| `GET /api/vectordb/stats` | VectorDB 통계 |

**위험성:** DLP 정책 구조와 PII 인식 패턴이 외부에 노출되면, 공격자가 탐지를 우회하는 데이터 형식을 파악할 수 있음. 내부 인프라 정보도 포함됨.

---

### 2-4. Medium: 시스템 상태 정보 노출 (2건)

**OWASP API8:2023 Security Misconfiguration**

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/v1/files/files` | 업로드 파일 목록 노출 |
| `GET /api/policies/sync/status` | 벡터스토어 동기화 상태 노출 |

---

### 2-5. CORS: 임의 Origin 반사 (1건)

**OWASP API8:2023 Security Misconfiguration**

| 항목 | 내용 |
|------|------|
| 재현 조건 | `Origin: https://evil-attacker.com` 헤더 포함 요청 |
| 실제 응답 헤더 | `Access-Control-Allow-Origin: https://evil-attacker.com` |
| 문제 설정 | `allow_origins=["*"]` in `main.py` |

**위험성:** 임의 도메인이 CORS 허용 출처로 반사됨. 악성 사이트에서 인증된 사용자의 세션을 이용한 CSRF 공격 가능.

---

### 2-6. Broken Auth: `/api/vectordb/guides/grouped` 토큰 검증 (2건)

**OWASP API2:2023 Broken Authentication**

| 공격 유형 | 결과 |
|----------|------|
| 만료 토큰으로 접근 | **200 OK** (토큰 수용됨) |
| alg:none 토큰으로 접근 | **200 OK** (서명 없는 토큰 수용됨) |

**위험성:** 해당 엔드포인트가 토큰의 만료 및 서명을 검증하지 않음. alg:none 수용은 JWT 표준 위반으로 인증 완전 우회 가능.

---

## 3. 정상 차단 확인 항목 (PASS, 30건)

보안이 올바르게 구현된 항목:

| 카테고리 | 내용 |
|---------|------|
| 만료 토큰 거부 | `/api/auth/me`, `/api/v1/emails/my-emails`, `/api/settings/all`, `/api/audit/logs` — 모두 401 반환 ✅ |
| alg:none 거부 | 위 4개 엔드포인트 모두 alg:none 토큰 거부 ✅ |
| 비정상 토큰 거부 | Bearer만, 빈 헤더, 잘못된 JWT 구조, Basic auth 스킴 등 — 모두 정상 차단 ✅ |
| CORS 민감 헤더 | Authorization, x-api-key 등 민감 헤더 미노출 ✅ |
| 정책 삭제 인증 | `DELETE /api/policies/{id}` — 인증 없이 403 반환 ✅ |
| VectorDB 가이드 | `GET/DELETE /api/vectordb/guides/{id}` — 인증 없이 차단 ✅ |
| 공개 엔드포인트 | `/`, `/health`, `/api/auth/login`, `/api/auth/register` — 정상 접근 ✅ |

---

## 4. Before 기준 정량 지표

| 지표 | 수치 |
|------|------|
| 실행 완료 테스트 수 | 49개 |
| 취약 엔드포인트 수 | **19개** |
| 인증 우회 성공률 | **38.8%** |
| Critical 취약점 | 5건 |
| High 취약점 | 8건 |
| Medium 취약점 | 2건 |
| CORS 취약 | 1건 (임의 Origin 반사) |
| alg:none 수용 | 1개 엔드포인트 (`/api/vectordb/guides/grouped`) |
| 만료 토큰 수용 | 1개 엔드포인트 (`/api/vectordb/guides/grouped`) |

---

## 5. 취약점 패치 방법 (일반화)

### 패치 유형 1 — OWASP API2: Broken Authentication
**인증 미적용 엔드포인트에 `Depends(get_current_user)` 추가**

FastAPI의 의존성 주입(Dependency Injection)을 이용해 모든 요청이 라우터 함수에 진입하기 전에 JWT를 검증하도록 강제한다. `get_current_user`는 Bearer 토큰을 파싱·검증하고, 실패 시 자동으로 `401 Unauthorized`를 반환한다.

**일반 패턴:**
```python
# Before (취약)
@router.get("/resource")
async def get_resource(db = Depends(get_db)):
    ...

# After (패치)
from app.auth.auth_utils import get_current_user

@router.get("/resource")
async def get_resource(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # ← 추가
):
    ...
```

**실제 적용 예시 — `uploads.py`의 원본 이메일 목록 엔드포인트:**
```python
# Before
@router.get("/original_emails")
async def list_original_emails(
    skip: int = 0,
    limit: int = 20,
    from_email: str = None,
    db = Depends(get_db)
):

# After
@router.get("/original_emails")
async def list_original_emails(
    skip: int = 0,
    limit: int = 20,
    from_email: str = None,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
```

**적용 범위:** `uploads.py` 7개, `process.py` 2개, `analyzer.py` 1개, `ocr.py` 1개, `entity/routes.py` 5개, `policy/routes.py` 8개, `vectordb/routes.py` 7개 — 총 **31개 엔드포인트**

---

### 패치 유형 2 — OWASP API5: Broken Function Level Authorization
**역할별 접근 제어가 필요한 엔드포인트에 역할 전용 의존성 함수 적용**

단순 인증(로그인 여부)을 넘어, 특정 역할(ROOT_ADMIN, POLICY_ADMIN, AUDITOR)만 수행할 수 있는 작업에는 역할 전용 `Depends`를 사용한다.

**일반 패턴:**
```python
# 역할별 의존성 함수 (auth_utils.py에 정의됨)
# get_current_root_admin   → ROOT_ADMIN 전용
# get_current_policy_admin → ROOT_ADMIN + POLICY_ADMIN
# get_current_auditor      → ROOT_ADMIN + AUDITOR

# Before (인증은 있지만 역할 구분 없음)
@router.delete("/entity/{id}")
async def delete_entity(id: str, current_user = Depends(get_current_user)):
    ...

# After (POLICY_ADMIN 이상만 허용)
@router.delete("/entity/{id}")
async def delete_entity(id: str, current_user = Depends(get_current_policy_admin)):
    ...
```

**실제 적용 예시 — `entity/routes.py`의 엔티티 삭제 (기존 올바른 구현):**
```python
@router.delete("/{entity_id}")
async def delete_entity(
    entity_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_policy_admin)  # ← 역할 지정
):
```

---

### 패치 유형 3 — OWASP API8: Security Misconfiguration (CORS)
**`allow_origins=["*"]` 와일드카드를 명시적 허용 도메인으로 교체**

`allow_origins=["*"]`은 임의 출처의 요청을 모두 허용하여 CSRF 및 정보 탈취 공격에 노출된다. 허용 출처를 환경변수로 관리하면 운영/개발 환경을 유연하게 분리할 수 있다.

**일반 패턴:**
```python
# Before (취약)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# After (패치)
ALLOWED_ORIGINS = [o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,           # 명시적 허용 목록
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
```

**실제 적용 파일:** `app/main.py`
`.env`에 `ALLOWED_ORIGINS=https://your-domain.com` 추가 필요.

---

## 6. 패치 결과 (After)

> **패치 방법:** `Depends(get_current_user)` 주입, CORS 화이트리스트 교체 (섹션 5 참조)
> **패치 일자:** 2026-03-24

### SAST After 결과

| 항목 | Before | After | 개선 |
|------|--------|-------|------|
| 총 엔드포인트 | 80개 | 80개 | — |
| 인증 적용 | 44개 (55.0%) | **77개 (96.2%)** | **+33개** |
| 인증 누락 | 36개 | **3개** | **-33개** |
| 인증 커버리지 | 55.0% | **96.2%** | **+41.2%p** |

### 패치된 엔드포인트 파일별 집계

| 파일 | 패치 수 |
|------|---------|
| `app/routers/uploads.py` | 7개 |
| `app/routers/process.py` | 2개 |
| `app/routers/analyzer.py` | 1개 |
| `app/routers/ocr.py` | 1개 |
| `app/routers/ocr_needed.py` | 1개 |
| `app/routers/masking_pdf.py` | 1개 |
| `app/entity/routes.py` | 5개 |
| `app/policy/routes.py` | 8개 |
| `app/vectordb/routes.py` | 7개 |
| `app/main.py` (CORS) | 1건 |
| **합계** | **33개 엔드포인트 + CORS 1건** |

### 잔여 미적용 (3개 — 별도 앱)

| 파일 | 사유 |
|------|------|
| `app/rag/api/main.py` (3개) | 메인 라우터 미포함 별도 FastAPI 앱 — 별도 점검 필요 |

---

## 7. SAST 정적 분석 결과 (Before 상세)

> **점검 방법:** AST 파싱 기반 커스텀 정적 분석 (`check_auth_coverage.py`)
> **특징:** 서버 실행 없이 코드만으로 인증 누락 탐지

### SAST 도구 개선 이력

분석 중 `check_auth_coverage.py`의 AST 파서가 `async def`로 선언된 라우터 핸들러를 탐지하지 못하는 버그를 발견했다. FastAPI 라우터는 대부분 `async def`로 작성되므로, 수정 전에는 동기 함수(`def`)로 선언된 엔드포인트 2개만 탐지되고 있었다.

| 항목 | 수정 전 | 수정 후 | 개선 |
|------|---------|---------|------|
| 탐지된 총 엔드포인트 | 2개 | 80개 | **+78개** |
| 탐지 커버리지 | 2.5% | 100% | **+97.5%p** |
| 인증 누락 탐지 | 2개 | 36개 | **+1,700%** |

**원인:** `ast.FunctionDef`만 검사하도록 구현되어 있어 `ast.AsyncFunctionDef` 누락
**수정:** `isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))`로 변경

이 수정으로 실질적인 인증 누락 탐지율이 **97.5%p 향상**되었으며, 기존에 보이지 않던 34개의 추가 취약 엔드포인트를 식별할 수 있었다.

### 전체 현황 (수정 후 기준)

| 항목 | 수치 |
|------|------|
| 총 엔드포인트 | 80개 |
| 인증 적용 | 44개 |
| 인증 누락 | **36개** |
| 인증 커버리지 | **55.0%** |

### 인증 누락 엔드포인트 목록

#### 파일 업로드 / 이메일 처리 (`app/routers/`)

| Method | Path | 파일 | 라인 |
|--------|------|------|------|
| POST | `/upload_email` | uploads.py | 29 |
| GET | `/files` | uploads.py | 98 |
| GET | `/files/watch` | uploads.py | 128 |
| GET | `/original_emails/{email_id}` | uploads.py | 149 |
| GET | `/original_emails` | uploads.py | 218 |
| GET | `/original_emails/{email_id}/attachment/{filename}` | uploads.py | 303 |
| GET | `/masked_emails/{email_id}` | uploads.py | 356 |
| GET | `/masking/masked-email/{email_id}` | masking_pdf.py | 325 |
| POST | `/approve_and_send` | process.py | 140 |
| POST | `/documents` | process.py | 26 |
| POST | `/analyze/text` | analyzer.py | 64 |
| POST | `/extract/ocr` | ocr.py | 10 |
| POST | `/check-ocr` | ocr_needed.py | 23 |

#### 정책 관리 (`app/policy/routes.py`)

| Method | Path | 라인 |
|--------|------|------|
| GET | `/list` | 367 |
| GET | `/schemas` | 493 |
| GET | `/{policy_id}` | 533 |
| GET | `/stats/summary` | 875 |
| GET | `/tasks/{task_id}/status` | 917 |
| POST | `/batch/process` | 934 |
| GET | `/tasks/all` | 993 |
| GET | `/sync/status` | 1184 |

#### 엔티티 관리 (`app/entity/routes.py`)

| Method | Path | 라인 |
|--------|------|------|
| GET | `/list` | 268 |
| GET | `/categories` | 312 |
| GET | `/recognizers` | 345 |
| GET | `/recognizers/{entity_type}` | 363 |
| GET | `/{entity_id}` | 384 |

#### VectorDB (`app/vectordb/routes.py`)

| Method | Path | 라인 |
|--------|------|------|
| GET | `/guides/grouped` | 265 |
| GET | `/guides/by-source/{source_document}` | 298 |
| GET | `/guides/{guide_id}` | 318 |
| POST | `/guides` | 340 |
| PUT | `/guides/{guide_id}` | 401 |
| DELETE | `/guides/{guide_id}` | 449 |
| GET | `/stats` | 488 |

#### RAG API (`app/rag/api/main.py`) — 별도 앱, 메인 라우터 미포함

| Method | Path | 라인 |
|--------|------|------|
| GET | `/` | 61 |
| POST | `/mask-email` | 92 |
| GET | `/guides/search` | 156 |

---

## 8. 테스트 실행 방법

```bash
cd backend

# DAST 실행 (서버 + MongoDB 필요)
pytest tests/security/ -v \
  --json-report \
  --json-report-file=security_report.json

# 정량 리포트 출력
python tests/security/generate_report.py

# SAST 실행 (서버 불필요)
python tests/security/check_auth_coverage.py --app-dir app
```
