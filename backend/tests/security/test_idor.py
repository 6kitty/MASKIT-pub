"""
실험 D: IDOR (Insecure Direct Object Reference) 테스트 (OWASP API1 - BOLA)
==========================================================================
User A의 토큰으로 User B의 리소스에 접근 가능한지 확인 (수평적 권한 상승).

시나리오:
  1. User B가 이메일/리소스를 생성
  2. User A의 토큰으로 해당 리소스 ID를 직접 요청
  3. 200 응답이면 IDOR 취약점

판정 기준:
  VULNERABLE : 타 사용자 리소스를 200으로 반환
  PROTECTED  : 403/404 반환 (접근 거부 또는 존재하지 않는 척)
"""

import pytest
from conftest import auth_headers


# ──────────────────────────────────────────────────────────────
# IDOR 테스트용 리소스 ID 수집
# ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def user_b_email_id(client, user_b_token):
    """
    User B가 이메일 전송 시도 → 생성된 이메일 ID 반환.
    실패 시 None 반환 (엔드포인트 자체가 인증 필요하면 스킵).
    """
    # User B로 간단한 이메일 전송 시도
    resp = client.post("/api/v1/emails/send", headers=auth_headers(user_b_token), json={
        "to": "test@example.com",
        "subject": "IDOR Test Email",
        "body": "Security test - IDOR",
    })
    if resp.status_code in (200, 201):
        data = resp.json()
        return data.get("id") or data.get("email_id") or data.get("_id")
    return None


@pytest.fixture(scope="module")
def user_b_email_from_list(client, user_b_token):
    """User B의 이메일 목록에서 첫 번째 이메일 ID 추출"""
    resp = client.get("/api/v1/emails/my-emails", headers=auth_headers(user_b_token))
    if resp.status_code == 200:
        emails = resp.json()
        if isinstance(emails, list) and emails:
            return str(emails[0].get("_id") or emails[0].get("id", ""))
        if isinstance(emails, dict):
            items = emails.get("items") or emails.get("emails") or []
            if items:
                return str(items[0].get("_id") or items[0].get("id", ""))
    return None


# ──────────────────────────────────────────────────────────────
# IDOR - 이메일 리소스
# ──────────────────────────────────────────────────────────────

class TestEmailIDOR:
    """이메일 ID를 직접 지정하여 타 사용자 리소스 접근 시도"""

    def test_user_a_cannot_access_user_b_email(
        self, client, user_a_token, user_b_email_from_list
    ):
        if not user_b_email_from_list:
            pytest.skip("User B의 이메일 ID를 가져올 수 없음 (이메일 없음)")

        resp = client.get(
            f"/api/v1/emails/email/{user_b_email_from_list}",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code in (403, 404), (
            f"[VULNERABLE-IDOR] User A가 User B의 이메일에 접근 성공\n"
            f"  → GET /api/v1/emails/email/{user_b_email_from_list} → {resp.status_code}\n"
            f"  → 객체 소유자 검증(BOLA) 누락"
        )

    def test_sequential_id_enumeration(self, client, user_a_token):
        """
        ID 추측 공격: 순차적 또는 예측 가능한 ID로 타인 이메일 열람 시도.
        404가 아닌 403을 반환해야 이상적 (존재 여부 노출 방지).
        """
        fake_ids = [
            "000000000000000000000001",
            "000000000000000000000002",
            "111111111111111111111111",
        ]
        exposed_count = 0
        for fid in fake_ids:
            resp = client.get(
                f"/api/v1/emails/email/{fid}",
                headers=auth_headers(user_a_token),
            )
            if resp.status_code == 200:
                exposed_count += 1

        assert exposed_count == 0, (
            f"[VULNERABLE-IDOR] ID 추측으로 {exposed_count}개 이메일 접근 성공"
        )


# ──────────────────────────────────────────────────────────────
# IDOR - 원본 이메일 파일
# ──────────────────────────────────────────────────────────────

class TestOriginalEmailIDOR:
    """원본 이메일 / 첨부파일 IDOR"""

    def test_unauthenticated_original_email_access(self, client):
        """인증 없이 임의 이메일 ID로 원본 이메일 접근"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.get(f"/api/v1/files/original_emails/{fake_id}")
        assert resp.status_code in (401, 403, 404), (
            f"[VULNERABLE-IDOR] 비인증으로 원본 이메일 접근: {resp.status_code}"
        )

    def test_unauthenticated_attachment_access(self, client):
        """인증 없이 임의 이메일의 첨부파일 접근"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.get(
            f"/api/v1/files/original_emails/{fake_id}/attachment/test.pdf"
        )
        assert resp.status_code in (401, 403, 404), (
            f"[VULNERABLE-IDOR] 비인증으로 첨부파일 접근: {resp.status_code}"
        )

    def test_user_a_cannot_access_user_b_masked_email(
        self, client, user_a_token, user_b_email_from_list
    ):
        if not user_b_email_from_list:
            pytest.skip("User B의 이메일 ID를 가져올 수 없음")

        resp = client.get(
            f"/api/v1/files/masked_emails/{user_b_email_from_list}",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code in (403, 404), (
            f"[VULNERABLE-IDOR] User A가 User B의 마스킹 이메일 열람: {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# IDOR - 정책 리소스
# ──────────────────────────────────────────────────────────────

class TestPolicyIDOR:
    """정책 ID 직접 접근 (소유자 검증 여부 확인)"""

    def test_policy_detail_requires_auth(self, client):
        """정책 상세 조회는 인증 없이 불가해야 함"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.get(f"/api/policies/{fake_id}")
        assert resp.status_code in (401, 403, 404), (
            f"[VULNERABLE] 비인증으로 정책 상세 접근: {resp.status_code}"
        )

    def test_policy_vector_delete_requires_auth(self, client):
        """정책 벡터 삭제는 인증 없이 불가해야 함"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.delete(f"/api/policies/sync/vector-store/{fake_id}")
        assert resp.status_code in (401, 403, 404), (
            f"[VULNERABLE] 비인증으로 정책 벡터 삭제: {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# IDOR - VectorDB 가이드
# ──────────────────────────────────────────────────────────────

class TestVectorDBIDOR:
    """VectorDB 가이드 ID 직접 접근"""

    def test_guide_detail_requires_auth(self, client):
        fake_id = "aabbccddee1122334455aabb"
        resp = client.get(f"/api/vectordb/guides/{fake_id}")
        assert resp.status_code in (401, 403, 404), (
            f"[VULNERABLE] 비인증으로 VectorDB 가이드 접근: {resp.status_code}"
        )

    def test_user_cannot_delete_others_guide(self, client, user_a_token):
        """일반 USER가 타인의 가이드 삭제 시도"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.delete(
            f"/api/vectordb/guides/{fake_id}",
            headers=auth_headers(user_a_token),
        )
        # 404(없음) 또는 403(권한없음) 모두 허용, 200/204는 취약
        assert resp.status_code in (403, 404), (
            f"[VULNERABLE-IDOR] USER가 가이드 삭제 성공: {resp.status_code}"
        )
