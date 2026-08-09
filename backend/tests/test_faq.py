FAQ_TRANSLATIONS = {
    "en": {"q": "Do you ship internationally?", "a": "Yes, worldwide."},
    "ar": {"q": "هل تشحنون دوليًا؟", "a": "نعم، حول العالم."},
}


def test_create_list_faq(logged_in_client):
    resp = logged_in_client.post("/admin/api/content/faq", json={"translations": FAQ_TRANSLATIONS})
    assert resp.status_code == 200, resp.text
    item_id = resp.json()["id"]

    resp2 = logged_in_client.get("/admin/api/content/faq")
    assert any(i["id"] == item_id for i in resp2.json())


def test_faq_missing_required_field_rejected(logged_in_client):
    resp = logged_in_client.post("/admin/api/content/faq", json={"translations": {"en": {"q": "Only a question"}}})
    assert resp.status_code == 400


def test_faq_update_and_delete(logged_in_client):
    created = logged_in_client.post("/admin/api/content/faq", json={"translations": FAQ_TRANSLATIONS}).json()
    updated = logged_in_client.put(f"/admin/api/content/faq/{created['id']}", json={
        "translations": {"en": {"q": "Updated?", "a": "Yes."}, "ar": {"q": "معدل؟", "a": "نعم."}},
    })
    assert updated.status_code == 200
    assert updated.json()["translations"]["en"]["q"] == "Updated?"

    deleted = logged_in_client.delete(f"/admin/api/content/faq/{created['id']}")
    assert deleted.status_code == 200
    missing = logged_in_client.delete(f"/admin/api/content/faq/{created['id']}")
    assert missing.status_code == 404


def test_faq_inactive_excluded_from_public(logged_in_client, client):
    created = logged_in_client.post("/admin/api/content/faq",
                                     json={"translations": FAQ_TRANSLATIONS, "is_active": False}).json()
    resp = client.get("/api/content/faq")
    ids = [i["id"] for i in resp.json()]
    assert created["id"] not in ids


def test_faq_reorder(logged_in_client):
    a = logged_in_client.post("/admin/api/content/faq", json={"translations": FAQ_TRANSLATIONS}).json()
    b = logged_in_client.post("/admin/api/content/faq", json={"translations": FAQ_TRANSLATIONS}).json()

    resp = logged_in_client.post("/admin/api/content/faq/reorder", json={"ordered_ids": [b["id"], a["id"]]})
    assert resp.status_code == 200

    listed = logged_in_client.get("/admin/api/content/faq").json()
    by_id = {i["id"]: i["order"] for i in listed}
    assert by_id[b["id"]] < by_id[a["id"]]


def test_faq_reorder_unknown_id_rejected(logged_in_client):
    resp = logged_in_client.post("/admin/api/content/faq/reorder", json={"ordered_ids": ["not-a-real-id"]})
    assert resp.status_code == 400
