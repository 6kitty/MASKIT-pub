"""
MASKIT Security Test Suite - conftest.py
========================================
공통 fixture: 테스트 계정 생성/삭제, 토큰 발급, httpx 클라이언트 설정

사용법:
  서버 실행 후 → pytest tests/security/ -v

환경변수:
  BASE_URL  : 테스트 대상 서버 (기본: http://localhost:8000)
  SECRET_KEY: JWT 서명 키 (만료/변조 토큰 생성용, .env에서 자동 로드)
"""

import os
import time
import pytest
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv
from jose import jwt

# .env 로드 (SECRET_KEY 참조)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("SECRET_KEY", "test-secret-key-for-ci-placeholder-32ch")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# 테스트 계정 정보 (실 DB에 생성 후 cleanup)
TEST_ADMIN = {"email": "sec_test_admin@maskit-security.com", "password": "SecTest!Admin#2024", "name": "SecTest Admin"}
TEST_USER_A = {"email": "sec_test_usera@maskit-security.com", "password": "SecTest!UserA#2024", "name": "SecTest UserA"}
TEST_USER_B = {"email": "sec_test_userb@maskit-security.com", "password": "SecTest!UserB#2024", "name": "SecTest UserB"}


# ──────────────────────────────────────────────
# 세션 스코프: 한 번만 계정 생성 → 전체 테스트 공유
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """동기 httpx 클라이언트 (세션 전체 재사용)"""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture(scope="session")
def registered_accounts(client):
    """
    테스트용 계정 3개 생성.
    - 첫 번째 등록 계정은 자동으로 ROOT_ADMIN이 되므로
      admin 계정을 가장 먼저 등록.
    - 테스트 종료 후 admin 토큰으로 전부 삭제.
    """
    created = []

    def _register(info):
        resp = client.post("/api/auth/register", json={
            "email": info["email"],
            "password": info["password"],
            "name": info["name"],
        })
        # 이미 존재하면 무시 (재실행 안전)
        assert resp.status_code in (201, 400), f"등록 실패: {resp.text}"
        if resp.status_code == 201:
            created.append(info["email"])

    # ① admin 먼저 (첫 유저 = ROOT_ADMIN)
    _register(TEST_ADMIN)
    _register(TEST_USER_A)
    _register(TEST_USER_B)

    yield

    # Cleanup: admin 토큰으로 테스트 계정 삭제
    login_resp = client.post("/api/auth/login", json={
        "email": TEST_ADMIN["email"], "password": TEST_ADMIN["password"]
    })
    if login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        for email in [TEST_USER_A["email"], TEST_USER_B["email"], TEST_ADMIN["email"]]:
            client.delete(f"/api/users/{email}", headers=headers)


@pytest.fixture(scope="session")
def admin_token(client, registered_accounts):
    """ROOT_ADMIN 유효 토큰"""
    resp = client.post("/api/auth/login", json={
        "email": TEST_ADMIN["email"], "password": TEST_ADMIN["password"]
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def user_a_token(client, registered_accounts):
    """일반 USER 유효 토큰 (User A)"""
    resp = client.post("/api/auth/login", json={
        "email": TEST_USER_A["email"], "password": TEST_USER_A["password"]
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def user_b_token(client, registered_accounts):
    """일반 USER 유효 토큰 (User B) - IDOR 테스트용"""
    resp = client.post("/api/auth/login", json={
        "email": TEST_USER_B["email"], "password": TEST_USER_B["password"]
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ──────────────────────────────────────────────
# 공격용 토큰 fixture
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def expired_token():
    """exp가 과거인 만료 JWT 토큰"""
    payload = {
        "sub": TEST_USER_A["email"],
        "exp": datetime.utcnow() - timedelta(hours=2),  # 2시간 전 만료
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture(scope="session")
def tampered_token(user_a_token):
    """서명 마지막 문자를 바꾼 변조 토큰"""
    parts = user_a_token.split(".")
    sig = parts[2]
    # 마지막 문자를 다른 문자로 교체
    bad_char = "A" if sig[-1] != "A" else "B"
    parts[2] = sig[:-1] + bad_char
    return ".".join(parts)


@pytest.fixture(scope="session")
def none_alg_token():
    """alg:none 공격 토큰 (서명 없음)"""
    import base64, json

    def b64url(data: str) -> str:
        return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()

    header = b64url('{"alg":"none","typ":"JWT"}')
    payload = b64url(json.dumps({
        "sub": TEST_ADMIN["email"],
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }))
    return f"{header}.{payload}."  # 빈 서명


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
