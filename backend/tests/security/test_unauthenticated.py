"""
실험 A: 비인증 접근 테스트 (OWASP API2 - Broken Authentication)
=================================================================
Authorization 헤더 없이 각 엔드포인트에 요청을 보내어
401/403을 반환해야 하는 엔드포인트가 실제로 보호되는지 확인.

판정 기준:
  VULNERABLE  : 200/201/422 응답 (인증 없이 처리됨)
  PROTECTED   : 401/403 응답 (올바르게 차단됨)
  INTENTIONAL : 공개 설계된 엔드포인트 (/ , /health 등)
"""

import pytest

# ──────────────────────────────────────────────────────────────
# 엔드포인트 목록: (method, path, severity, description)
# severity: critical / high / medium
# ──────────────────────────────────────────────────────────────

CRITICAL_ENDPOINTS = [
    ("GET",  "/api/v1/files/original_emails",          "원본 이메일 목록 전체 노출"),
    ("GET",  "/api/v1/files/original_emails/nonexistent_id", "원본 이메일 상세 열람"),
    ("GET",  "/api/v1/files/masked_emails/nonexistent_id",   "마스킹 이메일 열람"),
    ("GET",  "/api/v1/emails/my-emails",               "사용자 이메일 목록 열람"),
    ("GET",  "/api/v1/emails/received-emails",         "수신 이메일 목록 열람"),
    ("GET",  "/api/v1/emails/email/nonexistent_id",    "이메일 상세 무단 열람"),
]

HIGH_ENDPOINTS = [
    ("GET",  "/api/policies/list",                     "DLP 정책 목록 노출"),
    ("GET",  "/api/policies/schemas",                  "정책 스키마 노출"),
    ("GET",  "/api/policies/stats/summary",            "정책 통계 노출"),
    ("GET",  "/api/policies/tasks/all",                "백그라운드 작업 목록 노출"),
    ("GET",  "/api/entities/list",                     "PII 엔티티 목록 노출"),
    ("GET",  "/api/entities/categories",               "엔티티 카테고리 노출"),
    ("GET",  "/api/entities/recognizers",              "인식기 정보 노출"),
    ("GET",  "/api/vectordb/stats",                    "VectorDB 통계 노출"),
    ("POST", "/api/entities/recognizers/cache/clear",  "인식기 캐시 무단 초기화"),
    ("POST", "/api/policies/sync/vector-store",        "벡터스토어 무단 동기화"),
]

MEDIUM_ENDPOINTS = [
    ("GET",  "/api/v1/files/files",                    "파일 목록 노출"),
    ("GET",  "/api/policies/sync/status",              "동기화 상태 노출"),
]

# 공개 설계된 엔드포인트 (테스트 제외)
INTENTIONAL_PUBLIC = [
    ("GET",  "/",                                      "루트 (공개)"),
    ("GET",  "/health",                                "헬스체크 (공개)"),
    ("POST", "/api/auth/register",                     "회원가입 (공개)"),
    ("POST", "/api/auth/login",                        "로그인 (공개)"),
]


def _check_endpoint(client, method: str, path: str) -> int:
    """인증 헤더 없이 요청 → HTTP 상태코드 반환"""
    resp = getattr(client, method.lower())(path)
    return resp.status_code


def _is_protected(status_code: int) -> bool:
    """401 또는 403이면 보호된 것으로 판정"""
    return status_code in (401, 403)


# ──────────────────────────────────────────────────────────────
# Critical 엔드포인트 테스트
# ──────────────────────────────────────────────────────────────

class TestCriticalEndpoints:
    """Critical: 인증 없이 민감 데이터 접근 가능한 엔드포인트"""

    @pytest.mark.parametrize("method,path,desc", CRITICAL_ENDPOINTS)
    def test_critical_requires_auth(self, client, method, path, desc):
        status = _check_endpoint(client, method, path)
        assert _is_protected(status), (
            f"[VULNERABLE-CRITICAL] {method} {path} | {desc}\n"
            f"  → 인증 없이 {status} 응답 (예상: 401/403)"
        )


# ──────────────────────────────────────────────────────────────
# High 엔드포인트 테스트
# ──────────────────────────────────────────────────────────────

class TestHighEndpoints:
    """High: 정책/엔티티 정보 무단 접근"""

    @pytest.mark.parametrize("method,path,desc", HIGH_ENDPOINTS)
    def test_high_requires_auth(self, client, method, path, desc):
        status = _check_endpoint(client, method, path)
        assert _is_protected(status), (
            f"[VULNERABLE-HIGH] {method} {path} | {desc}\n"
            f"  → 인증 없이 {status} 응답 (예상: 401/403)"
        )


# ──────────────────────────────────────────────────────────────
# Medium 엔드포인트 테스트
# ──────────────────────────────────────────────────────────────

class TestMediumEndpoints:
    """Medium: 정보 노출 위험 엔드포인트"""

    @pytest.mark.parametrize("method,path,desc", MEDIUM_ENDPOINTS)
    def test_medium_requires_auth(self, client, method, path, desc):
        status = _check_endpoint(client, method, path)
        assert _is_protected(status), (
            f"[VULNERABLE-MEDIUM] {method} {path} | {desc}\n"
            f"  → 인증 없이 {status} 응답 (예상: 401/403)"
        )


# ──────────────────────────────────────────────────────────────
# 공개 엔드포인트 검증 (정상 동작 확인)
# ──────────────────────────────────────────────────────────────

class TestPublicEndpoints:
    """공개 설계 엔드포인트가 실제로 접근 가능한지 확인"""

    def test_root_is_public(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_health_is_public(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_login_endpoint_accessible(self, client):
        # 잘못된 자격증명으로 요청 → 401이지만 엔드포인트 자체는 접근됨
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "wrong"
        })
        assert resp.status_code in (401, 422)  # 인증 실패 or 입력 검증

    def test_register_endpoint_accessible(self, client):
        # 이미 존재하는 이메일로 요청 → 400이지만 엔드포인트 자체는 접근됨
        resp = client.post("/api/auth/register", json={
            "email": "already@test.com", "password": "pass", "name": "test"
        })
        assert resp.status_code in (201, 400, 422)
