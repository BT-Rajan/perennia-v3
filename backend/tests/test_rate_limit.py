"""
Runs in its own process (not sharing tests/conftest.py's relaxed
RATE_LIMIT_LOGIN) so it can exercise the real default limit end to end.

    python3 tests/test_rate_limit.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-prod-xxxxxxxxxxxxxxxx"
os.environ["COOKIE_SECURE"] = "false"
os.environ["RATE_LIMIT_LOGIN"] = "5/minute"
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp(prefix="perennia-test-uploads-")

from cryptography.fernet import Fernet
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app.db import Base, engine
from app.main import app
from fastapi.testclient import TestClient


def main():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    statuses = []
    for _ in range(7):
        resp = client.post("/admin/api/auth/login", json={"username": "admin", "password": "wrong"})
        statuses.append(resp.status_code)

    assert statuses[:5] == [401] * 5, f"expected first 5 attempts to be 401, got {statuses[:5]}"
    assert statuses[5:] == [429, 429], f"expected requests 6-7 to be rate-limited (429), got {statuses[5:]}"
    print("OK: login endpoint rate-limits after 5 attempts/minute:", statuses)


if __name__ == "__main__":
    main()
