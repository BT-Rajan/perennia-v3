"""
The settings registry: THE single source of truth for "everything
configurable" on the site.

Why a registry instead of a settings table with real columns, or a
hand-written admin endpoint per field (the reference app's approach)?
Because both of those force you to touch N places — a migration, a
Pydantic model, a route handler, an admin form — every single time you
add one configurable field. That's exactly the repetition this project
was asked to avoid, and it's how a 57KB main.py happens.

Here, adding a new configurable field is ONE line: a `SettingDef` entry
below. Everything downstream — DB storage, validation, the generic
admin CRUD API (routers/admin_settings.py), the public config API
(routers/public_config.py), and (Pass 8) the generic admin settings
form — reads this registry and needs no per-field code.

Categories map directly to admin panel sections. Each pass adds entries
to existing or new categories; no pass should need to add a new *code
path*, only new *entries*.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class SettingType(str, Enum):
    STRING = "string"        # short single-line text
    TEXT = "text"             # multi-line text / markdown
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    COLOR = "color"           # hex color, admin renders a color picker
    URL = "url"
    EMAIL = "email"
    IMAGE = "image"           # URL to an uploaded image (Pass 3 adds upload)
    ENUM = "enum"              # one of `choices`
    LIST = "list"              # JSON list of strings
    JSON = "json"              # arbitrary JSON blob (structured content, Pass 2+)


@dataclass(frozen=True)
class SettingDef:
    key: str                      # dotted path, e.g. "branding.site_name"
    category: str                 # admin panel section, e.g. "branding"
    label: str                    # human label shown in admin UI
    type: SettingType
    default: Any
    help_text: str = ""
    secret: bool = False          # encrypted at rest, never in public config API
    choices: tuple[str, ...] | None = None   # required for ENUM
    i18n: bool = False            # if true, value is {lang_code: value} JSON
    validator: Callable[[Any], None] | None = field(default=None, repr=False)

    def validate(self, value: Any) -> None:
        if self.i18n:
            if not isinstance(value, dict):
                raise ValueError(f"{self.key}: expected an object keyed by language code")
            for lang, v in value.items():
                self._validate_single(v)
            return
        self._validate_single(value)

    def _validate_single(self, value: Any) -> None:
        t = self.type
        if t == SettingType.BOOL and not isinstance(value, bool):
            raise ValueError(f"{self.key}: expected bool")
        if t == SettingType.INT and not isinstance(value, int):
            raise ValueError(f"{self.key}: expected int")
        if t == SettingType.FLOAT and not isinstance(value, (int, float)):
            raise ValueError(f"{self.key}: expected number")
        if t == SettingType.COLOR:
            if not (isinstance(value, str) and _is_hex_color(value)):
                raise ValueError(f"{self.key}: expected hex color like #RRGGBB")
        if t == SettingType.ENUM:
            if value not in (self.choices or ()):
                raise ValueError(f"{self.key}: must be one of {self.choices}")
        if t == SettingType.LIST and not isinstance(value, list):
            raise ValueError(f"{self.key}: expected a list")
        if t == SettingType.JSON and not isinstance(value, (dict, list)):
            raise ValueError(f"{self.key}: expected an object or array")
        if t in (SettingType.STRING, SettingType.TEXT, SettingType.URL, SettingType.EMAIL, SettingType.IMAGE):
            if not isinstance(value, str):
                raise ValueError(f"{self.key}: expected string")
        if self.validator:
            self.validator(value)


def _is_hex_color(v: str) -> bool:
    import re
    return bool(re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", v))


def _url_or_empty(v: str) -> None:
    if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("/")):
        raise ValueError("must be an absolute URL or a root-relative path")


# ── Registry ──────────────────────────────────────────────────────────
# Grouped by category purely for readability; the flat dict below is
# what code actually consumes.

_DEFS: list[SettingDef] = [
    # branding ------------------------------------------------------
    SettingDef("branding.site_name", "branding", "Site name", SettingType.STRING, "Perennia",
               help_text="Shown in the header, browser tab, and emails."),
    SettingDef("branding.tagline", "branding", "Tagline", SettingType.STRING, {"en": "", "ar": ""}, i18n=True),
    SettingDef("branding.logo_url", "branding", "Logo", SettingType.IMAGE, "/static/logo.svg"),
    SettingDef("branding.favicon_url", "branding", "Favicon", SettingType.IMAGE, "/favicon.svg"),

    # locale ----------------------------------------------------------
    SettingDef("locale.default_language", "locale", "Default language", SettingType.ENUM, "en",
               choices=("en", "ar")),
    SettingDef("locale.supported_languages", "locale", "Supported languages", SettingType.LIST, ["en", "ar"]),

    # contact -----------------------------------------------------------
    SettingDef("contact.email", "contact", "Contact email", SettingType.EMAIL, ""),
    SettingDef("contact.phone", "contact", "Contact phone", SettingType.STRING, ""),
    SettingDef("contact.whatsapp_number", "contact", "WhatsApp number", SettingType.STRING, "",
               help_text="Include country code, digits only, e.g. 96599999999."),
    SettingDef("contact.address", "contact", "Address", SettingType.TEXT, {"en": "", "ar": ""}, i18n=True),

    # theme (expanded in Pass 3; minimal placeholders now so nothing is
    # hardcoded even in Pass 1) --------------------------------------
    SettingDef("theme.primary_color", "theme", "Primary color", SettingType.COLOR, "#fbbf24"),
    SettingDef("theme.accent_color", "theme", "Accent color", SettingType.COLOR, "#3b82f6"),

    # features (toggles for capabilities landing in later passes,
    # declared now so the admin can already see what's coming and
    # nothing needs a hardcoded `if` for "is this feature on") --------
    SettingDef("features.booking_enabled", "features", "Enable appointment booking", SettingType.BOOL, True),
    SettingDef("features.chat_enabled", "features", "Enable AI chat widget", SettingType.BOOL, True),
    SettingDef("features.whatsapp_widget_enabled", "features", "Enable WhatsApp widget", SettingType.BOOL, False),

    # copy — free-form UI microcopy blobs, grouped by the screen that
    # uses them (home / chat / booking). Kept as JSON blobs rather than
    # exploded into one registry entry per string: these ~10-15 strings
    # per screen are always edited together, so one admin form per
    # screen (Pass 8) makes more sense than fifteen tiny form fields.
    # Structured content that's genuinely record-shaped (pages, FAQ)
    # lives in content_schema.py / content_service.py instead — see
    # PASS2_NOTES.md for why the split.
    SettingDef("copy.home", "copy", "Home screen text", SettingType.JSON, {"en": {}, "ar": {}}, i18n=True,
               help_text="welcome, tagline, hint, lang_switch"),
    SettingDef("copy.chat", "copy", "Chat screen text", SettingType.JSON, {"en": {}, "ar": {}}, i18n=True,
               help_text="tagline_line1, tagline_line2, sub, header, book_btn, faq_title, input_placeholder, welcome_msg, lang_switch"),
    SettingDef("copy.booking", "copy", "Booking flow text", SettingType.JSON, {"en": {}, "ar": {}}, i18n=True,
               help_text="Field labels and status messages for the booking panel. Status messages support "
                          "{id}/{date}/{time} placeholders."),
]

for _d in _DEFS:
    if _d.type == SettingType.URL or _d.type == SettingType.IMAGE:
        object.__setattr__(_d, "validator", _url_or_empty)

REGISTRY: dict[str, SettingDef] = {d.key: d for d in _DEFS}

CATEGORIES: list[str] = sorted({d.category for d in _DEFS})


def defs_for_category(category: str) -> list[SettingDef]:
    return [d for d in _DEFS if d.category == category]


def encode_default(d: SettingDef) -> str:
    return json.dumps(d.default)


def get_def(key: str) -> SettingDef:
    d = REGISTRY.get(key)
    if d is None:
        raise KeyError(f"Unknown setting key: {key!r} (not in settings_registry.REGISTRY)")
    return d
