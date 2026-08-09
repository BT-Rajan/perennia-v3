def test_public_config_uses_defaults_when_nothing_set(client):
    resp = client.get("/api/config/public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["branding.site_name"] == {"en": "Perennia", "ar": "بيرينيا"}
    assert body["theme.primary_color"] == "#fbbf24"
    assert body["features.booking_enabled"] is True


def test_admin_can_read_category_schema(logged_in_client):
    resp = logged_in_client.get("/admin/api/settings/branding")
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "branding"
    keys = {s["key"] for s in body["schema_"]}
    assert "branding.site_name" in keys
    assert body["values"]["branding.site_name"] == {"en": "Perennia", "ar": "بيرينيا"}


def test_admin_update_persists_and_reflects_in_public_config(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/branding", json={
        "branding.site_name": {"en": "Acme Clinic", "ar": "عيادة أكمي"},
    })
    assert resp.status_code == 200

    resp2 = logged_in_client.get("/api/config/public")
    assert resp2.json()["branding.site_name"]["en"] == "Acme Clinic"


def test_update_rejects_unknown_key(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/branding", json={"branding.not_a_real_field": "x"})
    assert resp.status_code == 400


def test_update_rejects_wrong_category(logged_in_client):
    # theme.primary_color exists, but not under the 'branding' category
    resp = logged_in_client.put("/admin/api/settings/branding", json={"theme.primary_color": "#000000"})
    assert resp.status_code == 400


def test_color_validation_rejects_bad_hex(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/theme", json={"theme.primary_color": "not-a-color"})
    assert resp.status_code == 400


def test_bulk_update_is_atomic_on_validation_failure(logged_in_client):
    """One invalid field in a bulk PUT must roll back the whole batch —
    a valid field earlier in the dict must not get persisted."""
    resp = logged_in_client.put("/admin/api/settings/theme", json={
        "theme.accent_color": "#123456",
        "theme.primary_color": "still-not-a-color",
    })
    assert resp.status_code == 400

    check = logged_in_client.get("/admin/api/settings/theme")
    assert check.json()["values"]["theme.accent_color"] == "#3b82f6"  # unchanged default


def test_update_without_csrf_header_rejected(client):
    login = client.post("/admin/api/auth/login", json={"username": "admin", "password": "correct-horse-battery-staple"})
    assert login.status_code == 200
    # deliberately not attaching X-CSRF-Token
    resp = client.put("/admin/api/settings/branding", json={"branding.site_name": {"en": "Hijacked"}})
    assert resp.status_code == 403


def test_enum_validation(logged_in_client):
    ok = logged_in_client.put("/admin/api/settings/locale", json={"locale.default_language": "ar"})
    assert ok.status_code == 200
    bad = logged_in_client.put("/admin/api/settings/locale", json={"locale.default_language": "fr"})
    assert bad.status_code == 400
