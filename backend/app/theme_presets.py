"""
Theme presets for the admin "Theme" settings page.

Two curated, built-in looks an admin can pick from a dropdown without
touching a single field, plus the machinery to persist whatever an
admin *does* customize as one editable "Custom" theme.

Design choice: presets are NOT a new DB table. `theme.*` in
settings_registry.py / SiteSetting is already the single source of
truth the public site renders (see routers/public_config.py). Presets
sit on top of it:
  - BUILTIN_PRESETS below — static, code-defined, never stored, never
    editable.
  - one persisted "custom" snapshot, stored in the existing
    SiteSetting table under keys namespaced *outside* the registry
    (theme._custom_preset / theme._active_preset) so they can never
    be picked up by get_all() and leak through the public config API,
    which only ever reads REGISTRY keys.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, SiteSetting
from app.settings_registry import defs_for_category, get_def
from app.settings_service import set_many

_CUSTOM_KEY = "theme._custom_preset"   # JSON: {"name": "Custom", "tokens": {...}}
_ACTIVE_KEY = "theme._active_preset"   # plain string: a builtin id, or "custom"

CUSTOM_PRESET_ID = "custom"

_FONT_STACK = {
    "theme.font_display": '"Cormorant Garamond", Georgia, serif',
    "theme.font_body": '"Inter", system-ui, -apple-system, sans-serif',
    "theme.font_ar": '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    "theme.google_fonts_url": (
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700"
        "&family=Cormorant+Garamond:wght@500;600;700&family=Noto+Kufi+Arabic:wght@300;400;500;600;700"
        "&display=swap"
    ),
}

BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "builtin:midnight-gold",
        "name": "Midnight Gold",
        "tokens": {
            "theme.primary_color": "#d4af37",
            "theme.accent_color": "#c9a961",
            "theme.background_color": "#0b0b10",
            "theme.text_color": "#f4ead9",
            **_FONT_STACK,
            "theme.header_height_px": 72,
            "theme.content_max_width_px": 1200,
            "theme.corner_radius_px": 6,
            "theme.hero_auto_advance_seconds": 8,
        },
    },
    {
        "id": "builtin:ivory-marble",
        "name": "Ivory Marble",
        "tokens": {
            "theme.primary_color": "#b08d57",
            "theme.accent_color": "#7c8a8b",
            "theme.background_color": "#f7f3ec",
            "theme.text_color": "#2a2620",
            **_FONT_STACK,
            "theme.header_height_px": 76,
            "theme.content_max_width_px": 1200,
            "theme.corner_radius_px": 18,
            "theme.hero_auto_advance_seconds": 7,
        },
    },
]

_BUILTIN_BY_ID = {p["id"]: p for p in BUILTIN_PRESETS}


def _theme_keys() -> set[str]:
    return {d.key for d in defs_for_category("theme")}


def _validate_tokens(tokens: dict[str, Any]) -> None:
    """Every preset — builtin or custom — must cover exactly the
    current theme.* registry keys, each passing that field's own
    validator. Catches a stale/hand-edited preset before it's ever
    written live, rather than half-applying it."""
    keys = _theme_keys()
    missing = keys - set(tokens)
    extra = set(tokens) - keys
    if missing:
        raise ValueError(f"theme preset missing keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"theme preset has unknown keys: {sorted(extra)}")
    for key, value in tokens.items():
        get_def(key).validate(value)


def _load_custom(db: Session) -> dict[str, Any] | None:
    row = db.get(SiteSetting, _CUSTOM_KEY)
    return json.loads(row.value) if row is not None else None


def _load_active_id(db: Session) -> str:
    row = db.get(SiteSetting, _ACTIVE_KEY)
    return row.value if row is not None else BUILTIN_PRESETS[0]["id"]


def _set_active(db: Session, preset_id: str) -> None:
    row = db.get(SiteSetting, _ACTIVE_KEY)
    if row is None:
        db.add(SiteSetting(key=_ACTIVE_KEY, value=preset_id, is_secret=False))
    else:
        row.value = preset_id


def list_presets(db: Session) -> dict[str, Any]:
    presets = [
        {"id": p["id"], "name": p["name"], "is_builtin": True, "tokens": p["tokens"]}
        for p in BUILTIN_PRESETS
    ]
    custom = _load_custom(db)
    if custom is not None:
        presets.append({
            "id": CUSTOM_PRESET_ID, "name": custom.get("name", "Custom"),
            "is_builtin": False, "tokens": custom["tokens"],
        })
    return {"presets": presets, "active_id": _load_active_id(db)}


def get_preset_tokens(db: Session, preset_id: str) -> dict[str, Any]:
    if preset_id in _BUILTIN_BY_ID:
        return dict(_BUILTIN_BY_ID[preset_id]["tokens"])
    if preset_id == CUSTOM_PRESET_ID:
        custom = _load_custom(db)
        if custom is None:
            raise KeyError("No custom theme has been saved yet")
        return dict(custom["tokens"])
    raise KeyError(f"Unknown theme preset: {preset_id!r}")


def apply_preset(db: Session, preset_id: str, *, actor_id: str | None, actor_username: str | None,
                  ip_address: str | None) -> dict[str, Any]:
    """Admin picked a preset from the dropdown: push its tokens live
    onto the theme.* SiteSetting rows — the same rows the public site
    reads via settings_service.get_all — and remember it as active."""
    tokens = get_preset_tokens(db, preset_id)
    _validate_tokens(tokens)
    set_many(db, tokens, actor_id=actor_id, actor_username=actor_username, ip_address=ip_address)
    _set_active(db, preset_id)
    db.add(AuditLog(actor_id=actor_id, actor_username=actor_username, action="theme_preset.apply",
                     target=preset_id, ip_address=ip_address))
    db.commit()
    return {"applied": preset_id}


def record_theme_save(db: Session, effective_values: dict[str, Any], *, actor_id: str | None,
                       actor_username: str | None, ip_address: str | None) -> str:
    """Call after a normal Save on the Theme page. If the values just
    saved exactly match a known preset, that preset becomes active
    with nothing new written. Otherwise they're a genuine edit —
    persist them as the one "Custom" preset (upsert, not versioned:
    there's always at most one) and make it active. Returns the
    resulting active preset id."""
    for p in BUILTIN_PRESETS:
        if p["tokens"] == effective_values:
            _set_active(db, p["id"])
            db.commit()
            return p["id"]

    custom = _load_custom(db)
    if custom is not None and custom["tokens"] == effective_values:
        _set_active(db, CUSTOM_PRESET_ID)
        db.commit()
        return CUSTOM_PRESET_ID

    payload = json.dumps({"name": "Custom", "tokens": effective_values})
    row = db.get(SiteSetting, _CUSTOM_KEY)
    if row is None:
        db.add(SiteSetting(key=_CUSTOM_KEY, value=payload, is_secret=False, updated_by=actor_id))
    else:
        row.value = payload
        row.updated_by = actor_id
    _set_active(db, CUSTOM_PRESET_ID)
    db.add(AuditLog(actor_id=actor_id, actor_username=actor_username, action="theme_preset.save_custom",
                     target=CUSTOM_PRESET_ID, ip_address=ip_address))
    db.commit()
    return CUSTOM_PRESET_ID
