def test_i18n_setting_default_is_per_language_dict(client):
    resp = client.get("/api/config/public")
    body = resp.json()
    assert body["branding.tagline"] == {"en": "", "ar": ""}


def test_i18n_setting_partial_override_merges_with_default(logged_in_client, client):
    resp = logged_in_client.put("/admin/api/settings/branding", json={
        "branding.tagline": {"en": "Only English set"},
    })
    assert resp.status_code == 200

    public = client.get("/api/config/public").json()
    assert public["branding.tagline"]["en"] == "Only English set"
    assert public["branding.tagline"]["ar"] == ""  # untouched language still falls back to default


def test_i18n_setting_rejects_non_string_language_value(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/branding", json={
        "branding.tagline": {"en": 12345},
    })
    assert resp.status_code == 400


def test_copy_blob_json_setting_roundtrip(logged_in_client, client):
    resp = logged_in_client.put("/admin/api/settings/copy", json={
        "copy.home": {"en": {"welcome": "Hi!"}, "ar": {"welcome": "أهلاً!"}},
    })
    assert resp.status_code == 200

    public = client.get("/api/config/public").json()
    assert public["copy.home"]["en"]["welcome"] == "Hi!"
    assert public["copy.home"]["ar"]["welcome"] == "أهلاً!"


def test_copy_blob_rejects_non_object(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/copy", json={"copy.home": "not an object"})
    assert resp.status_code == 400
