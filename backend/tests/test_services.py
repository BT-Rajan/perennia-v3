"""Pass 0 — admin-only Service catalog. See docs/CALENDAR_MODULE_PLAN.md."""


def _create(client, **overrides):
    body = {"name": "Consultation", "duration_minutes": 30, **overrides}
    return client.post("/admin/api/services", json=body)


def test_create_and_list_service(logged_in_client):
    resp = _create(logged_in_client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Consultation"
    assert body["slug"] == "consultation"
    assert body["duration_minutes"] == 30
    assert body["is_active"] is True
    assert body["questions"] == []

    listed = logged_in_client.get("/admin/api/services").json()
    assert any(s["id"] == body["id"] for s in listed)


def test_slug_auto_generated_and_deduplicated(logged_in_client):
    first = _create(logged_in_client, name="Follow Up Call").json()
    second = _create(logged_in_client, name="Follow Up Call").json()
    assert first["slug"] == "follow-up-call"
    assert second["slug"] == "follow-up-call-2"


def test_explicit_slug_is_slugified(logged_in_client):
    resp = _create(logged_in_client, slug="Home Visit!!")
    assert resp.json()["slug"] == "home-visit"


def test_duration_out_of_range_rejected(logged_in_client):
    resp = _create(logged_in_client, duration_minutes=1)
    assert resp.status_code == 422  # pydantic ge=5 constraint

    resp2 = logged_in_client.post("/admin/api/services", json={"name": "X", "duration_minutes": 30,
                                                                 "buffer_before_minutes": 500})
    assert resp2.status_code == 422


def test_invalid_location_type_rejected(logged_in_client):
    resp = _create(logged_in_client, location_type="teleport")
    assert resp.status_code == 400


def test_blank_name_rejected(logged_in_client):
    resp = logged_in_client.post("/admin/api/services", json={"name": "   ", "duration_minutes": 30})
    assert resp.status_code == 400


def test_get_update_delete_service(logged_in_client):
    created = _create(logged_in_client).json()
    sid = created["id"]

    got = logged_in_client.get(f"/admin/api/services/{sid}")
    assert got.status_code == 200
    assert got.json()["name"] == "Consultation"

    updated = logged_in_client.patch(f"/admin/api/services/{sid}", json={"duration_minutes": 45, "requires_confirmation": True})
    assert updated.status_code == 200
    assert updated.json()["duration_minutes"] == 45
    assert updated.json()["requires_confirmation"] is True

    deleted = logged_in_client.delete(f"/admin/api/services/{sid}")
    assert deleted.status_code == 200

    # soft delete: still fetchable, just inactive — not gone
    after = logged_in_client.get(f"/admin/api/services/{sid}")
    assert after.status_code == 200
    assert after.json()["is_active"] is False


def test_update_unknown_service_404(logged_in_client):
    resp = logged_in_client.patch("/admin/api/services/does-not-exist", json={"name": "X"})
    assert resp.status_code == 404


def test_delete_unknown_service_404(logged_in_client):
    resp = logged_in_client.delete("/admin/api/services/does-not-exist")
    assert resp.status_code == 404


def test_update_rejects_invalid_buffer_even_if_duration_unchanged(logged_in_client):
    created = _create(logged_in_client).json()
    resp = logged_in_client.patch(f"/admin/api/services/{created['id']}", json={"buffer_before_minutes": 500})
    assert resp.status_code == 422  # pydantic constraint catches this before it reaches the service layer


def test_requires_auth(client):
    resp = client.get("/admin/api/services")
    assert resp.status_code == 401


# ── Custom questions ─────────────────────────────────────────────────

def test_add_update_delete_question(logged_in_client):
    service = _create(logged_in_client).json()
    sid = service["id"]

    added = logged_in_client.post(f"/admin/api/services/{sid}/questions",
                                   json={"kind": "text", "label": "What's the issue?", "required": True})
    assert added.status_code == 200, added.text
    qid = added.json()["id"]

    fetched = logged_in_client.get(f"/admin/api/services/{sid}")
    assert len(fetched.json()["questions"]) == 1
    assert fetched.json()["questions"][0]["required"] is True

    updated = logged_in_client.patch(f"/admin/api/services/{sid}/questions/{qid}", json={"label": "Details?"})
    assert updated.status_code == 200
    assert updated.json()["label"] == "Details?"

    deleted = logged_in_client.delete(f"/admin/api/services/{sid}/questions/{qid}")
    assert deleted.status_code == 200

    after = logged_in_client.get(f"/admin/api/services/{sid}")
    assert after.json()["questions"] == []


def test_question_invalid_kind_rejected(logged_in_client):
    service = _create(logged_in_client).json()
    resp = logged_in_client.post(f"/admin/api/services/{service['id']}/questions",
                                  json={"kind": "essay", "label": "Tell me everything"})
    assert resp.status_code == 400


def test_question_on_unknown_service_404(logged_in_client):
    resp = logged_in_client.post("/admin/api/services/does-not-exist/questions",
                                  json={"kind": "text", "label": "Q?"})
    assert resp.status_code == 404


def test_question_reorder(logged_in_client):
    service = _create(logged_in_client).json()
    sid = service["id"]
    a = logged_in_client.post(f"/admin/api/services/{sid}/questions", json={"kind": "text", "label": "A"}).json()
    b = logged_in_client.post(f"/admin/api/services/{sid}/questions", json={"kind": "text", "label": "B"}).json()

    resp = logged_in_client.post(f"/admin/api/services/{sid}/questions/reorder",
                                  json={"ordered_ids": [b["id"], a["id"]]})
    assert resp.status_code == 200

    fetched = logged_in_client.get(f"/admin/api/services/{sid}").json()
    by_id = {q["id"]: q["position"] for q in fetched["questions"]}
    assert by_id[b["id"]] < by_id[a["id"]]


def test_question_reorder_unknown_id_rejected(logged_in_client):
    service = _create(logged_in_client).json()
    resp = logged_in_client.post(f"/admin/api/services/{service['id']}/questions/reorder",
                                  json={"ordered_ids": ["not-a-real-id"]})
    assert resp.status_code == 400


def test_deleting_service_cascades_its_questions(logged_in_client):
    service = _create(logged_in_client).json()
    sid = service["id"]
    logged_in_client.post(f"/admin/api/services/{sid}/questions", json={"kind": "text", "label": "A"})

    # deactivate (soft delete) leaves questions in place — they belong
    # to the service's history, not to whether it's currently bookable
    logged_in_client.delete(f"/admin/api/services/{sid}")
    after = logged_in_client.get(f"/admin/api/services/{sid}").json()
    assert len(after["questions"]) == 1
