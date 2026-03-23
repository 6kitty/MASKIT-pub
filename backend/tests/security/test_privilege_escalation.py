"""
실험 E: 수직적 권한 상승 테스트 (OWASP API5 - Broken Function Level Authorization)
===================================================================================
낮은 역할(USER)의 토큰으로 높은 권한(ROOT_ADMIN, AUDITOR, POLICY_ADMIN) 전용
엔드포인트 접근을 시도하여 역할 검증이 실제로 동작하는지 확인.

판정 기준:
  SECURE     : 403 Forbidden (인증은 통과했지만 권한 부족)
  VULNERABLE : 200/201 (권한 우회 성공)
"""

import pytest
from conftest import auth_headers


# ──────────────────────────────────────────────────────────────
# ROOT_ADMIN 전용 엔드포인트
# ──────────────────────────────────────────────────────────────

class TestRootAdminEndpoints:
    """USER 토큰으로 ROOT_ADMIN 전용 엔드포인트 접근 시도"""

    def test_user_cannot_list_all_users(self, client, user_a_token):
        """사용자 목록 조회는 ADMIN/AUDITOR 이상만 가능"""
        resp = client.get("/api/users/", headers=auth_headers(user_a_token))
        assert resp.status_code == 403, (
            f"[VULNERABLE-E] USER가 전체 사용자 목록 접근: {resp.status_code}"
        )

    def test_user_cannot_change_user_role(self, client, user_a_token):
        """역할 변경은 ROOT_ADMIN만 가능"""
        resp = client.patch(
            "/api/users/target@example.com/role",
            headers=auth_headers(user_a_token),
            json={"role": "root_admin"},
        )
        assert resp.status_code in (403, 404, 422), (
            f"[VULNERABLE-E] USER가 역할 변경 성공: {resp.status_code}"
        )

    def test_user_cannot_delete_user(self, client, user_a_token):
        """계정 삭제는 ROOT_ADMIN만 가능"""
        resp = client.delete(
            "/api/users/target@example.com",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code in (403, 404), (
            f"[VULNERABLE-E] USER가 계정 삭제 성공: {resp.status_code}"
        )

    def test_admin_can_list_users(self, client, admin_token):
        """ROOT_ADMIN은 사용자 목록 접근 가능 (기준선 확인)"""
        resp = client.get("/api/users/", headers=auth_headers(admin_token))
        assert resp.status_code == 200, (
            f"ROOT_ADMIN이 사용자 목록에 접근 불가: {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# POLICY_ADMIN 전용 엔드포인트
# ──────────────────────────────────────────────────────────────

class TestPolicyAdminEndpoints:
    """USER 토큰으로 POLICY_ADMIN 전용 엔드포인트 접근 시도"""

    def test_user_cannot_create_entity(self, client, user_a_token):
        """엔티티 생성은 POLICY_ADMIN/ROOT_ADMIN만 가능"""
        resp = client.post(
            "/api/entities/",
            headers=auth_headers(user_a_token),
            json={
                "name": "test_entity",
                "entity_type": "CUSTOM",
                "patterns": ["\\d{6}"],
                "description": "Security test entity",
            },
        )
        assert resp.status_code in (403, 422), (
            f"[VULNERABLE-E] USER가 엔티티 생성 성공: {resp.status_code}"
        )

    def test_user_cannot_delete_entity(self, client, user_a_token):
        """엔티티 삭제는 POLICY_ADMIN/ROOT_ADMIN만 가능"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.delete(
            f"/api/entities/{fake_id}",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code in (403, 404), (
            f"[VULNERABLE-E] USER가 엔티티 삭제 성공: {resp.status_code}"
        )

    def test_user_cannot_delete_policy(self, client, user_a_token):
        """정책 삭제는 POLICY_ADMIN/ROOT_ADMIN만 가능"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.delete(
            f"/api/policies/{fake_id}",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code in (403, 404), (
            f"[VULNERABLE-E] USER가 정책 삭제 성공: {resp.status_code}"
        )

    def test_user_cannot_patch_policy_text(self, client, user_a_token):
        """정책 내용 수정은 POLICY_ADMIN/ROOT_ADMIN만 가능"""
        fake_id = "aabbccddee1122334455aabb"
        resp = client.patch(
            f"/api/policies/{fake_id}/text",
            headers=auth_headers(user_a_token),
            json={"text": "malicious policy override"},
        )
        assert resp.status_code in (403, 404, 422), (
            f"[VULNERABLE-E] USER가 정책 내용 수정 성공: {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# AUDITOR 전용 엔드포인트
# ──────────────────────────────────────────────────────────────

class TestAuditorEndpoints:
    """USER 토큰으로 AUDITOR 전용 엔드포인트 접근 시도"""

    def test_user_cannot_access_audit_stats(self, client, user_a_token):
        """감사 통계는 AUDITOR/ROOT_ADMIN만 가능"""
        resp = client.get(
            "/api/audit/logs/stats",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code == 403, (
            f"[VULNERABLE-E] USER가 감사 통계 접근: {resp.status_code}"
        )

    def test_user_cannot_export_audit_logs(self, client, user_a_token):
        """감사 로그 내보내기는 AUDITOR/ROOT_ADMIN만 가능"""
        resp = client.get(
            "/api/audit/logs/export",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code == 403, (
            f"[VULNERABLE-E] USER가 감사 로그 내보내기 접근: {resp.status_code}"
        )

    def test_user_cannot_access_all_email_logs(self, client, user_a_token):
        """전체 이메일 로그는 AUDITOR/ROOT_ADMIN만 가능"""
        resp = client.get(
            "/api/v1/emails/all-logs",
            headers=auth_headers(user_a_token),
        )
        assert resp.status_code == 403, (
            f"[VULNERABLE-E] USER가 전체 이메일 로그 접근: {resp.status_code}"
        )

    def test_admin_can_access_audit_stats(self, client, admin_token):
        """ROOT_ADMIN은 감사 통계 접근 가능 (기준선)"""
        resp = client.get(
            "/api/audit/logs/stats",
            headers=auth_headers(admin_token),
        )
        assert resp.status_code in (200, 404), (
            f"ROOT_ADMIN이 감사 통계에 접근 불가: {resp.status_code}"
        )


# ──────────────────────────────────────────────────────────────
# 역할 자가 승격 시도
# ──────────────────────────────────────────────────────────────

class TestSelfPrivilegeEscalation:
    """USER가 자기 자신의 역할을 직접 변경하려는 시도"""

    def test_user_cannot_self_escalate_role(self, client, user_a_token):
        """자기 역할을 ROOT_ADMIN으로 바꾸려는 시도"""
        from conftest import TEST_USER_A
        resp = client.patch(
            f"/api/users/{TEST_USER_A['email']}/role",
            headers=auth_headers(user_a_token),
            json={"role": "root_admin"},
        )
        assert resp.status_code in (403, 422), (
            f"[CRITICAL] 자기 역할 승격 성공: {resp.status_code}"
        )
