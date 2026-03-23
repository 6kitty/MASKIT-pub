"""
실험 B/C: Broken Authentication 테스트 (OWASP API2)
====================================================
B: 만료 토큰을 서버가 거부하는지 확인
C: 변조된 서명 / alg:none 공격 토큰을 서버가 거부하는지 확인

판정 기준:
  SECURE    : 401 반환 (올바르게 거부)
  VULNERABLE: 200/201 반환 (공격 토큰이 수용됨)
"""

import pytest
from conftest import auth_headers

# 인증이 필요한 엔드포인트 (보호 여부 검증 가능한 것만 선택)
PROTECTED_ENDPOINTS = [
    ("GET",  "/api/auth/me",                         "내 정보 조회"),
    ("GET",  "/api/v1/emails/my-emails",             "내 이메일 목록"),
    ("GET",  "/api/settings/all",                    "설정 전체 조회"),
    ("GET",  "/api/audit/logs",                      "감사 로그 조회"),
    ("GET",  "/api/vectordb/guides/grouped",         "VectorDB 가이드 목록"),
]


# ──────────────────────────────────────────────────────────────
# 실험 B: 만료 토큰 테스트
# ──────────────────────────────────────────────────────────────

class TestExpiredToken:
    """만료된 JWT 토큰이 모든 보호 엔드포인트에서 거부되는지 확인"""

    @pytest.mark.parametrize("method,path,desc", PROTECTED_ENDPOINTS)
    def test_expired_token_rejected(self, client, expired_token, method, path, desc):
        resp = getattr(client, method.lower())(path, headers=auth_headers(expired_token))
        assert resp.status_code == 401, (
            f"[VULNERABLE-B] {method} {path} | {desc}\n"
            f"  → 만료 토큰으로 {resp.status_code} 응답 (예상: 401)\n"
            f"  → 만료 토큰 검증 로직 누락 의심"
        )

    def test_expired_token_error_message_safe(self, client, expired_token):
        """에러 메시지에 내부 스택 트레이스가 노출되지 않는지 확인"""
        resp = client.get("/api/auth/me", headers=auth_headers(expired_token))
        body = resp.text
        assert "traceback" not in body.lower(), "스택 트레이스 노출"
        assert "exception" not in body.lower() or resp.status_code == 401, \
            "내부 예외 정보 노출 가능성"


# ──────────────────────────────────────────────────────────────
# 실험 C-1: 서명 변조 토큰 테스트
# ──────────────────────────────────────────────────────────────

class TestTamperedToken:
    """서명이 변조된 JWT 토큰이 거부되는지 확인 (서명 검증 테스트)"""

    @pytest.mark.parametrize("method,path,desc", PROTECTED_ENDPOINTS)
    def test_tampered_token_rejected(self, client, tampered_token, method, path, desc):
        resp = getattr(client, method.lower())(path, headers=auth_headers(tampered_token))
        assert resp.status_code == 401, (
            f"[VULNERABLE-C1] {method} {path} | {desc}\n"
            f"  → 변조 토큰으로 {resp.status_code} 응답 (예상: 401)\n"
            f"  → JWT 서명 검증 누락"
        )


# ──────────────────────────────────────────────────────────────
# 실험 C-2: alg:none 공격 테스트
# ──────────────────────────────────────────────────────────────

class TestNoneAlgorithmAttack:
    """
    alg:none 공격: 서명 없는 토큰으로 ROOT_ADMIN 권한 획득 시도.
    python-jose는 기본적으로 alg:none을 거부하지만
    설정 미스가 있을 경우를 탐지.
    """

    @pytest.mark.parametrize("method,path,desc", PROTECTED_ENDPOINTS)
    def test_none_alg_token_rejected(self, client, none_alg_token, method, path, desc):
        resp = getattr(client, method.lower())(path, headers=auth_headers(none_alg_token))
        assert resp.status_code == 401, (
            f"[VULNERABLE-C2-CRITICAL] {method} {path} | {desc}\n"
            f"  → alg:none 토큰으로 {resp.status_code} 응답 (예상: 401)\n"
            f"  → alg:none 공격에 취약함! 즉시 수정 필요"
        )

    def test_none_alg_cannot_access_admin_endpoint(self, client, none_alg_token):
        """alg:none으로 ROOT_ADMIN 전용 엔드포인트 접근 불가 확인"""
        resp = client.get("/api/users/", headers=auth_headers(none_alg_token))
        assert resp.status_code in (401, 403), (
            f"[CRITICAL] alg:none 토큰으로 관리자 엔드포인트 접근 성공: {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# 실험 C-3: 잘못된 형식의 토큰 테스트
# ──────────────────────────────────────────────────────────────

class TestMalformedTokens:
    """비정상 형식의 Authorization 헤더 처리 검증"""

    MALFORMED_TOKENS = [
        ("Bearer",                    "Bearer 키워드만 (토큰 없음)"),
        ("Bearer ",                   "Bearer + 공백만"),
        ("Bearer invalid.jwt.token",  "잘못된 JWT 구조"),
        ("Bearer eyJ.eyJ.",           "불완전한 JWT"),
        ("Basic dXNlcjpwYXNz",        "Basic 인증 스킴 (Bearer 아님)"),
        ("",                          "빈 Authorization 헤더"),
    ]

    @pytest.mark.parametrize("auth_value,desc", MALFORMED_TOKENS)
    def test_malformed_token_rejected(self, client, auth_value, desc):
        headers = {"Authorization": auth_value} if auth_value else {}
        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code in (401, 403, 422), (
            f"[VULNERABLE] 비정상 토큰 수용: '{desc}' → {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# 유효 토큰 정상 동작 확인 (회귀 테스트)
# ──────────────────────────────────────────────────────────────

class TestValidTokenWorks:
    """유효한 토큰은 정상적으로 인증되는지 확인 (기준선)"""

    def test_valid_token_accepted(self, client, user_a_token):
        resp = client.get("/api/auth/me", headers=auth_headers(user_a_token))
        assert resp.status_code == 200, (
            f"유효 토큰이 거부됨: {resp.status_code} - {resp.text}"
        )

    def test_valid_token_returns_correct_user(self, client, user_a_token):
        resp = client.get("/api/auth/me", headers=auth_headers(user_a_token))
        assert resp.status_code == 200
        body = resp.json()
        assert "email" in body
        assert "sec_test_usera@maskit-security.test" in body["email"]
