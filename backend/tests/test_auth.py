from tests.conftest import TEST_PASSWORD


def test_login_success(client):
    resp = client.post("/admin/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "admin"
    assert body["role"] == "owner"
    assert body["csrf_token"]
    assert "perennia_admin_session" in resp.cookies


def test_login_wrong_password(client):
    resp = client.post("/admin/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user_same_status_as_wrong_password(client):
    """Guards against username enumeration: unknown user and wrong
    password must return identical status/shape."""
    r1 = client.post("/admin/api/auth/login", json={"username": "nobody", "password": "whatever"})
    r2 = client.post("/admin/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_me_requires_auth(client):
    resp = client.get("/admin/api/auth/me")
    assert resp.status_code == 401


def test_me_after_login(logged_in_client):
    resp = logged_in_client.get("/admin/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_logout_invalidates_session(logged_in_client):
    resp = logged_in_client.post("/admin/api/auth/logout")
    assert resp.status_code == 200
    resp2 = logged_in_client.get("/admin/api/auth/me")
    assert resp2.status_code == 401


def test_admin_settings_requires_auth(client):
    resp = client.get("/admin/api/settings/branding")
    assert resp.status_code == 401
