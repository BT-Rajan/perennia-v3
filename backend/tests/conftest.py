from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-prod-xxxxxxxxxxxxxxxx")
os.environ.setdefault("COOKIE_SECURE", "false")
# High ceiling so the many logins across a test run don't trip the
# limiter itself; test_rate_limit.py exercises the real low limit
# in its own isolated process.
os.environ.setdefault("RATE_LIMIT_LOGIN", "1000/minute")

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from cryptography.fernet import Fernet  # noqa: E402
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.db import Base, engine, session_scope  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser  # noqa: E402
from app.security import hash_password  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

TEST_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    Base.metadata.create_all(bind=engine)
    with session_scope() as db:
        db.add(AdminUser(username="admin", password_hash=hash_password(TEST_PASSWORD), role="owner"))
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def logged_in_client(client):
    resp = client.post("/admin/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert resp.status_code == 200, resp.text
    csrf = resp.json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": csrf})
    return client
