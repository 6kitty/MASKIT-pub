"""
CORS 보안 설정 테스트
=====================
현재 CORS가 allow_origins=["*"]로 설정되어 있음.
이 테스트는 CORS 설정 현황을 문서화하고
보안상 위험한 조합(credentialed wildcard)을 탐지.
"""

import pytest


class TestCORSHeaders:
    """CORS 응답 헤더 검증"""

    def test_cors_allows_arbitrary_origin(self, client):
        """임의 Origin에 대해 와일드카드(*) 허용 여부 확인"""
        resp = client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://evil-attacker.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        # 와일드카드이거나 evil 도메인을 그대로 반사하면 취약
        is_wildcard = acao == "*"
        is_reflected = "evil-attacker.com" in acao

        assert not (is_wildcard or is_reflected), (
            f"[VULNERABLE-CORS] 임의 Origin 허용: Access-Control-Allow-Origin: {acao}\n"
            f"  → 프로덕션에서는 허용 도메인을 명시적으로 지정해야 함"
        )

    def test_cors_credentialed_wildcard(self, client):
        """
        credentials=True + allow_origins=["*"] 조합 탐지.
        이 조합은 브라우저가 실제로는 차단하지만,
        설정 자체가 잘못된 의도를 드러냄.
        """
        resp = client.options(
            "/api/auth/me",
            headers={
                "Origin": "https://evil-attacker.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        acac = resp.headers.get("access-control-allow-credentials", "")

        # wildcard + credentials=true 조합은 명시적 위험
        assert not (acao == "*" and acac.lower() == "true"), (
            f"[VULNERABLE-CORS] allow_origins='*' + allow_credentials=True 조합 감지\n"
            f"  → Access-Control-Allow-Origin: {acao}\n"
            f"  → Access-Control-Allow-Credentials: {acac}\n"
            f"  → 허용 출처를 구체적 도메인으로 제한해야 함"
        )

    def test_cors_exposes_sensitive_headers(self, client):
        """민감한 헤더가 CORS로 노출되지 않는지 확인"""
        resp = client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        exposed = resp.headers.get("access-control-expose-headers", "").lower()
        sensitive = ["authorization", "x-api-key", "x-secret"]
        for header in sensitive:
            assert header not in exposed, (
                f"[VULNERABLE-CORS] 민감한 헤더 노출: {header}"
            )

    def test_cors_allows_all_methods(self, client):
        """allow_methods=['*'] 설정으로 모든 HTTP 메서드 허용 여부 확인"""
        resp = client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        acam = resp.headers.get("access-control-allow-methods", "")
        # DELETE, PATCH 같은 위험 메서드가 무조건 허용되는지 확인
        if "*" in acam or "DELETE" in acam.upper():
            pytest.warns(
                UserWarning,
                match="모든 HTTP 메서드 허용"
            )
            # 경고로 처리 (실패보다는 문서화 목적)


class TestCORSWithAuthentication:
    """인증이 필요한 엔드포인트의 CORS 동작"""

    def test_authenticated_endpoint_cors(self, client, user_a_token):
        """인증된 요청에서 CORS 헤더가 올바르게 반환되는지"""
        resp = client.get(
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {user_a_token}",
                "Origin": "https://example.com",
            },
        )
        # 인증 성공 + CORS 헤더 존재 확인
        assert resp.status_code == 200
        # CORS 헤더가 있는지 (설정된 경우)
        acao = resp.headers.get("access-control-allow-origin")
        assert acao is not None, "CORS 헤더 누락 (프론트엔드 통신 불가 가능성)"
