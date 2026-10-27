import os
import uuid
import pytest
import requests
from typing import Generator
from sqlalchemy.orm import Session
from src.database import SessionLocal


BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000/api")


@pytest.fixture(scope="session")
def api_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def session() -> requests.Session:
    """Базовый HTTP-клиент с настройкой повторных попыток и заголовков."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def create_user_and_get_token(session: requests.Session, api_url: str, role: str) -> dict:
    """Хелпер для создания изолированного пользователя под конкретный тест-ран."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"test_{role.lower()}_{unique_id}@example.com"
    password = "TestPassword123!"

    reg_payload = {"email": email, "password": password, "role": role}
    reg_resp = session.post(f"{api_url}/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201, f"Failed to register {role}: {reg_resp.text}"

    login_payload = {"email": email, "password": password}
    login_resp = session.post(f"{api_url}/auth/login", json=login_payload)
    assert login_resp.status_code == 200, f"Failed to login {role}: {login_resp.text}"

    token = login_resp.json()["access_token"]
    user_id = reg_resp.json()["id"]

    return {
        "user_id": user_id,
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


@pytest.fixture(scope="session")
def admin_auth(session: requests.Session, api_url: str) -> dict:
    return create_user_and_get_token(session, api_url, role="ADMIN")


@pytest.fixture(scope="function")
def user_auth(session: requests.Session, api_url: str) -> dict:
    return create_user_and_get_token(session, api_url, role="USER")


@pytest.fixture(scope="session")
def test_category(session: requests.Session, api_url: str, admin_auth: dict) -> int:
    """Создает стабильную категорию для связанных тестов компонентов."""
    slug = f"cpu-{uuid.uuid4().hex[:6]}"
    payload = {"name": f"CPU Category {slug}", "slug": slug}
    resp = session.post(
        f"{api_url}/catalog/categories",
        json=payload,
        headers=admin_auth["headers"]
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Предоставляет изолированную сессию БД с автоматическим откатом изменений."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()