"""
Read/write access to configurable settings. Every value the site ever
shows — to a visitor or an admin — should be reached through
`get_setting`/`get_all_public`, never a hardcoded literal in a component
or route. A DB row is only written once an admin actually changes a
value from its default (sparse storage — an empty table is a fully
valid, fully-defaulted site).
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, SiteSetting
from app.security import decrypt_secret, encrypt_secret
from app.settings_registry import REGISTRY, SettingDef, get_def


def _decode(d: SettingDef, raw: str) -> Any:
    return json.loads(raw)


def _encode(value: Any) -> str:
    return json.dumps(value)


def get_setting(db: Session, key: str) -> Any:
    d = get_def(key)
    row = db.get(SiteSetting, key)
    if row is None:
        return d.default
    raw = decrypt_secret(row.value) if row.is_secret else row.value
    stored = _decode(d, raw)
    if d.i18n and isinstance(d.default, dict) and isinstance(stored, dict):
        # Merge so a language an admin hasn't translated yet still falls
        # back to the default rather than disappearing from the response.
        merged = dict(d.default)
        merged.update(stored)
        return merged
    return stored


def get_category(db: Session, category: str) -> dict[str, Any]:
    """Never decrypts secret-typed settings — a masked placeholder is
    returned instead (see _secret_placeholder), the same rule
    get_all_settings applies. This function backs the admin settings
    UI's edit forms, so a plaintext API key must never transit this
    path even to an authenticated admin: it shouldn't sit in a browser
    network log, get bound into a visible input value, or round-trip
    back on save (the UI leaves a secret field untouched to keep it)."""
    from app.settings_registry import defs_for_category
    out = {}
    for d in defs_for_category(category):
        if d.secret:
            out[d.key] = _secret_placeholder(db, d.key)
        else:
            out[d.key] = get_setting(db, d.key)
    return out


SECRET_PLACEHOLDER = "••••••••"


def _secret_placeholder(db: Session, key: str) -> str:
    """Decrypts only to check whether a real (non-empty) value is
    stored — the decrypted value itself is never returned. This is
    what distinguishes "never configured" (empty row or no row) from
    "configured" (masked placeholder) without leaking the secret."""
    row = db.get(SiteSetting, key)
    if row is None:
        return ""
    try:
        value = _decode(get_def(key), decrypt_secret(row.value))
    except ValueError:
        return ""
    return SECRET_PLACEHOLDER if value else ""


def get_all(db: Session, *, include_secrets: bool) -> dict[str, Any]:
    """include_secrets=False is what powers the PUBLIC config API — a
    secret-typed setting is simply omitted, never masked-and-included,
    so there's no risk of a masking bug leaking a fragment."""
    out: dict[str, Any] = {}
    for key, d in REGISTRY.items():
        if d.secret and not include_secrets:
            continue
        out[key] = get_setting(db, key)
    return out


def set_setting(db: Session, key: str, value: Any, *, actor_id: str | None, actor_username: str | None,
                 ip_address: str | None = None) -> None:
    d = get_def(key)

    # Defense in depth: the settings UI's edit form is populated from
    # get_category(), which returns this exact placeholder for a
    # secret that's already set (see _secret_placeholder) rather than
    # the real value — precisely so a naive "submit the whole form"
    # save can never round-trip a masked display string back in as
    # the new value and destroy the real secret. If it ever does slip
    # through, treat it as "no change" rather than overwriting.
    if d.secret and value == SECRET_PLACEHOLDER:
        return

    d.validate(value)
    raw = _encode(value)
    stored = encrypt_secret(raw) if d.secret else raw

    row = db.get(SiteSetting, key)
    if row is None:
        row = SiteSetting(key=key, value=stored, is_secret=d.secret)
        db.add(row)
    else:
        row.value = stored
        row.is_secret = d.secret
    row.updated_by = actor_id

    db.add(AuditLog(
        actor_id=actor_id,
        actor_username=actor_username,
        action="setting.update",
        target=key,
        detail="<redacted secret value>" if d.secret else raw[:500],
        ip_address=ip_address,
    ))


def set_many(db: Session, values: dict[str, Any], *, actor_id: str | None, actor_username: str | None,
             ip_address: str | None = None) -> list[str]:
    """Validates every key BEFORE writing any of them, so a bulk save
    from the admin panel is all-or-nothing rather than leaving settings
    half-updated on a validation error partway through."""
    unknown = [k for k in values if k not in REGISTRY]
    if unknown:
        raise KeyError(f"Unknown setting keys: {unknown}")
    for key, value in values.items():
        get_def(key).validate(value)

    for key, value in values.items():
        set_setting(db, key, value, actor_id=actor_id, actor_username=actor_username, ip_address=ip_address)
    return list(values.keys())
