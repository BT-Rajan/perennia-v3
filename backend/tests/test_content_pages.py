EN_AR_TRANSLATIONS = {
    "en": {
        "nav_label": "About", "section_title": "About Us", "section_body": "Short teaser.",
        "tagline_line1": "Who We ", "tagline_line2": "Are", "tagline_sub": "SUB",
        "body_markdown": "# About\nFull body.",
    },
    "ar": {
        "nav_label": "من نحن", "section_title": "عنا", "section_body": "نبذة قصيرة.",
        "tagline_line1": "من ", "tagline_line2": "نحن", "tagline_sub": "فرعي",
        "body_markdown": "# من نحن\nالمحتوى الكامل.",
    },
}


def test_create_and_get_page(logged_in_client):
    resp = logged_in_client.put("/admin/api/content/pages/newpage", json={"translations": EN_AR_TRANSLATIONS})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["slug"] == "newpage"
    assert body["translations"]["en"]["nav_label"] == "About"

    resp2 = logged_in_client.get("/admin/api/content/pages/newpage")
    assert resp2.status_code == 200
    assert resp2.json()["translations"]["ar"]["nav_label"] == "من نحن"


def test_page_requires_required_field(logged_in_client):
    bad = {"en": {"nav_label": "About"}}  # missing section_title, section_body, body_markdown
    resp = logged_in_client.put("/admin/api/content/pages/broken", json={"translations": bad})
    assert resp.status_code == 400


def test_page_unsupported_language_rejected(logged_in_client):
    bad = {"fr": EN_AR_TRANSLATIONS["en"]}
    resp = logged_in_client.put("/admin/api/content/pages/frpage", json={"translations": bad})
    assert resp.status_code == 400


def test_page_edit_creates_version_and_rollback_works(logged_in_client):
    logged_in_client.put("/admin/api/content/pages/versioned", json={"translations": EN_AR_TRANSLATIONS})

    changed = {**EN_AR_TRANSLATIONS, "en": {**EN_AR_TRANSLATIONS["en"], "section_title": "Changed Title"}}
    logged_in_client.put("/admin/api/content/pages/versioned", json={"translations": changed})

    versions = logged_in_client.get("/admin/api/content/pages/versioned/versions").json()
    assert len(versions) == 1
    assert versions[0]["translations"]["en"]["section_title"] == "About Us"  # the pre-edit snapshot

    rollback = logged_in_client.post(f"/admin/api/content/pages/versioned/rollback/{versions[0]['id']}")
    assert rollback.status_code == 200
    assert rollback.json()["translations"]["en"]["section_title"] == "About Us"


def test_hidden_page_excluded_from_public_api(logged_in_client, client):
    logged_in_client.put("/admin/api/content/pages/hiddenpage",
                          json={"translations": EN_AR_TRANSLATIONS, "is_visible": False})
    resp = client.get("/api/content/pages")
    slugs = [p["slug"] for p in resp.json()]
    assert "hiddenpage" not in slugs


def test_visible_page_appears_in_public_api(logged_in_client, client):
    logged_in_client.put("/admin/api/content/pages/visiblepage", json={"translations": EN_AR_TRANSLATIONS})
    resp = client.get("/api/content/pages")
    slugs = [p["slug"] for p in resp.json()]
    assert "visiblepage" in slugs


def test_delete_page(logged_in_client):
    logged_in_client.put("/admin/api/content/pages/todelete", json={"translations": EN_AR_TRANSLATIONS})
    resp = logged_in_client.delete("/admin/api/content/pages/todelete")
    assert resp.status_code == 200
    resp2 = logged_in_client.get("/admin/api/content/pages/todelete")
    assert resp2.status_code == 404


def test_content_endpoints_require_auth(client):
    assert client.get("/admin/api/content/pages").status_code == 401
    assert client.put("/admin/api/content/pages/x", json={"translations": {}}).status_code == 401
