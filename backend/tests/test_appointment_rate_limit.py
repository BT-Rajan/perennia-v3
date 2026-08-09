"""
Runs in its own process (not sharing tests/conftest.py's relaxed
RATE_LIMIT_APPOINTMENT) so it can exercise the real default limit.

    python3 tests/test_appointment_rate_limit.py
"""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-prod-xxxxxxxxxxxxxxxx"
os.environ["COOKIE_SECURE"] = "false"
os.environ["RATE_LIMIT_APPOINTMENT"] = "6/hour"
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

    date = dt.date.today() + dt.timedelta(days=10)
    while date.weekday() > 4:
        date += dt.timedelta(days=1)

    statuses = []
    for i in range(8):
        resp = client.post("/api/booking/appointments/lookup", json={"id": "PRN-NOPE0000", "email": "x@x.com"})
        statuses.append(resp.status_code)

    assert statuses.count(429) == 0, "lookup is unauthenticated but not rate-limited by design — sanity check"

    statuses = []
    for i in range(8):
        resp = client.post("/api/booking/appointments/cancel", json={"id": f"PRN-NOPE{i:04d}", "email": "x@x.com"})
        statuses.append(resp.status_code)

    assert statuses[:6] == [200] * 6, f"expected first 6 to succeed (200, ok:false not_found), got {statuses[:6]}"
    assert statuses[6:] == [429, 429], f"expected requests 7-8 to be rate-limited, got {statuses[6:]}"
    print("OK: appointment endpoints rate-limit after 6 attempts/hour:", statuses)


if __name__ == "__main__":
    main()
