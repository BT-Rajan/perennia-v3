import io

# Minimal valid 1x1 PNG (smallest legal PNG byte sequence).
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415478da6360000002000155a5f9600000000049454e44ae42"
    "6082"
)


def test_theme_color_settings_have_expected_defaults(client):
    body = client.get("/api/config/public").json()
    assert body["theme.primary_color"] == "#ff7a45"
    assert body["theme.background_color"] == "#0c0a16"
    assert body["theme.header_height_px"] == 64


def test_theme_pixel_settings_reject_out_of_range(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/theme", json={"theme.header_height_px": 5})
    assert resp.status_code == 400

    resp2 = logged_in_client.put("/admin/api/settings/theme", json={"theme.corner_radius_px": 999})
    assert resp2.status_code == 400


def test_theme_pixel_settings_accept_in_range(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/theme", json={"theme.header_height_px": 72})
    assert resp.status_code == 200


def test_theme_font_is_free_text_string(logged_in_client, client):
    resp = logged_in_client.put("/admin/api/settings/theme", json={"theme.font_body": '"Poppins", sans-serif'})
    assert resp.status_code == 200
    assert client.get("/api/config/public").json()["theme.font_body"] == '"Poppins", sans-serif'


def test_theme_google_fonts_url_validation(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/theme", json={"theme.google_fonts_url": "not a url"})
    assert resp.status_code == 400


def test_upload_requires_auth(client):
    resp = client.post("/admin/api/uploads/image", files={"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")})
    assert resp.status_code == 401


def test_upload_valid_png_returns_url(logged_in_client):
    resp = logged_in_client.post("/admin/api/uploads/image",
                                  files={"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")})
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith("/uploads/")
    assert url.endswith(".png")


def test_upload_rejects_non_image_content_disguised_as_png(logged_in_client):
    """Content-Type header lies about what the bytes actually are —
    the endpoint must sniff real magic bytes, not trust the header."""
    fake = io.BytesIO(b"<script>alert(1)</script>")
    resp = logged_in_client.post("/admin/api/uploads/image", files={"file": ("logo.png", fake, "image/png")})
    assert resp.status_code == 400


def test_upload_rejects_svg(logged_in_client):
    """SVG can carry <script> — deliberately not accepted for re-serving."""
    svg = io.BytesIO(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    resp = logged_in_client.post("/admin/api/uploads/image", files={"file": ("logo.svg", svg, "image/svg+xml")})
    assert resp.status_code == 400


def test_upload_rejects_oversized_file(logged_in_client, monkeypatch):
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "MAX_UPLOAD_IMAGE_BYTES", 10)
    big = io.BytesIO(PNG_1PX)  # already > 10 bytes
    resp = logged_in_client.post("/admin/api/uploads/image", files={"file": ("logo.png", big, "image/png")})
    assert resp.status_code == 413


def test_uploaded_file_is_served_back(logged_in_client, client):
    resp = logged_in_client.post("/admin/api/uploads/image",
                                  files={"file": ("logo.png", io.BytesIO(PNG_1PX), "image/png")})
    url = resp.json()["url"]
    served = client.get(url)
    assert served.status_code == 200
    assert served.content == PNG_1PX
