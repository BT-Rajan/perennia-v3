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
    from app.settings_registry import defs_for_category
    return {d.key: get_setting(db, d.key) for d in defs_for_category(category)}


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
