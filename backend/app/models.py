"""
ORM models.

Deliberately few tables in Pass 1. The big one conceptually is
`SiteSetting`: rather than one DB column per configurable field (which is
how the reference app's sprawl happened — a new column and a new admin
API endpoint for every setting), every configurable value is a row here,
keyed by a dotted key that's validated against `settings_registry.py`.
Later passes (booking, leads, chat, notifications) add their own
domain tables, but *configuration* always flows through this one table.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # bcrypt hash only — a plaintext password is never stored or logged.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Role scaffolding for Pass 9 (RBAC). "owner" can manage other admins;
    # "editor" can change content/settings but not users/security.
    role: Mapped[str] = mapped_column(String(16), default="owner", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["AdminSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AdminSession(Base):
    """Server-side session record. The cookie only carries the opaque
    session id (signed); nothing about the user is trusted from the
    client without a DB lookup, and a session can be revoked instantly
    by deleting this row (unlike a stateless JWT)."""

    __tablename__ = "admin_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex + uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("admin_user.id", ondelete="CASCADE"), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), default=_uuid)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["AdminUser"] = relationship(back_populates="sessions")

    __table_args__ = (Index("ix_admin_session_expires", "expires_at"),)


class SiteSetting(Base):
    """One row per configurable value. `key` is a dotted path (e.g.
    'branding.site_name', 'hours.workdays') that must exist in the
    settings registry — the registry is the schema; this table is just
    storage. `value` is always stored as text (JSON-encoded for
    non-string types); `is_secret` rows are Fernet-encrypted before
    being written here and never returned by the public config API."""

    __tablename__ = "site_setting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin_user.id"), nullable=True)


class AuditLog(Base):
    """Append-only trail of admin actions. Full RBAC/audit UI lands in
    Pass 9, but every write path from Pass 1 onward logs through this so
    there's no gap to backfill later."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ContentPage(Base):
    """One row per standalone content page (about/products/services/
    contact/...). `translations` is {lang_code: {field_key: str}},
    validated against content_schema.PAGE_FIELDS — see that module for
    why this is a JSON blob rather than a column per field: it unifies
    what used to be three separate hardcoded structures (nav label, home
    teaser, page tagline, full body) into one admin-editable record per
    page, and lets an admin add a whole new page without a migration."""

    __tablename__ = "content_page"

    slug: Mapped[str] = mapped_column(String(48), primary_key=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_in_nav: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    translations: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin_user.id"), nullable=True)


class ContentPageVersion(Base):
    """Snapshot of a ContentPage's translations taken immediately before
    each overwrite, so an admin can see history and roll back a bad
    edit without needing a full external CMS."""

    __tablename__ = "content_page_version"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(48), ForeignKey("content_page.slug", ondelete="CASCADE"), nullable=False, index=True)
    translations: Mapped[dict] = mapped_column(JSON, nullable=False)
    saved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    saved_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    saved_by_username: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FaqItem(Base):
    """One row per FAQ entry. Same translations-blob pattern as
    ContentPage, validated against content_schema.FAQ_FIELDS."""

    __tablename__ = "faq_item"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    translations: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin_user.id"), nullable=True)


class Appointment(Base):
    """One row per booking. `date`/`time` are kept as separate strings
    (ISO date, 'HH:MM') rather than a single datetime because every
    piece of booking logic — slot generation, availability, the
    workdays/hours settings — is inherently day-and-slot shaped, not a
    continuous timestamp; storing it that way avoids timezone-conversion
    bugs creeping into what's fundamentally a "which slot" question.
    The confirmation code (id) is the primary key and is what a visitor
    quotes back to look up, cancel, or reschedule — always paired with
    the email on file, checked in booking_service.py."""

    __tablename__ = "appointment"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM, 24h
    lang: Mapped[str] = mapped_column(String(8), default="en", nullable=False)  # for notification template language
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    service: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="confirmed", nullable=False)  # confirmed | cancelled
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("ix_appointment_date_status", "date", "status"),)


class Lead(Base):
    """A contact worth following up with — captured automatically
    whenever a booking is made (source='booking') or an email address
    appears in a chat conversation (source='chat'), rather than
    requiring a separate lead-capture form. Multiple touches from the
    same email upsert into one record (see leads_service.py) so a
    visitor who chats and later books shows up as one lead with a
    fuller picture, not two disconnected ones."""

    __tablename__ = "lead"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # chat | booking
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    # new | contacted | qualified | converted | lost
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)  # admin's own notes
    transcript: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{from, text, at}]
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class KnowledgeSource(Base):
    """A document (uploaded file) or web page an admin has added so the
    chat assistant can ground its answers in real, current information
    instead of only what's baked into the system prompt — a Perennia
    org chart, a pricing sheet, a policy document, a page from the
    live site, etc. No embeddings/vector search: chat_service.py
    concatenates the (capped) text of every active source into the
    system prompt for each reply, the same approach used by the
    reference implementation this was modeled on. `source_ref` is the
    original filename or the URL; re-fetching (URL sources only)
    updates `text` in place rather than creating a new row, so a
    source's identity persists across refreshes."""

    __tablename__ = "knowledge_source"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # file | url
    content_type: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf | docx | html | text | markdown
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(2048), nullable=False)  # filename or URL
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin_user.id"), nullable=True)
