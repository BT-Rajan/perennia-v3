"""
Google Calendar sync — connection lifecycle (OAuth), busy-time lookup
for slot generation, and best-effort event creation/cleanup on
booking confirm/cancel/reschedule. See docs/CALENDAR_MODULE_PLAN.md
(Pass 12).

One connected account for the whole business (not per-admin-user) —
`get_active_credential` is the only lookup every other module needs;
nothing here assumes multiple connections will ever exist at once.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import google_calendar_client as google
from app.models import AuditLog, CalendarCredential
from app.security import decrypt_secret, encrypt_secret
from app.settings_service import get_setting

# Refresh a bit before actual expiry so a slow request never straddles
# the token becoming invalid mid-call.
_REFRESH_SKEW = dt.timedelta(minutes=2)


class CalendarSyncNotConfigured(Exception):
    """Raised when calendar_sync.google_client_id/secret aren't set —
    distinct from GoogleCalendarError (a real API failure) since this
    is an admin setup gap, not something retrying would fix."""


def _oauth_client(db: Session) -> tuple[str, str]:
    client_id = get_setting(db, "calendar_sync.google_client_id")
    client_secret = get_setting(db, "calendar_sync.google_client_secret")
    if not client_id or not client_secret:
        raise CalendarSyncNotConfigured(
            "calendar_sync.google_client_id / google_client_secret must be set before connecting"
        )
    return client_id, client_secret


def get_active_credential(db: Session) -> CalendarCredential | None:
    return db.scalar(select(CalendarCredential).where(CalendarCredential.is_active.is_(True)))


def get_pending_credential(db: Session, credential_id: str) -> CalendarCredential | None:
    """A credential mid-connect: tokens stored, calendar_id not yet
    chosen. Used by POST /select."""
    return db.get(CalendarCredential, credential_id)


def build_connect_url(db: Session, *, redirect_uri: str, admin_id: str) -> str:
    from app.security import sign_oauth_state
    client_id, _ = _oauth_client(db)
    return google.build_auth_url(client_id=client_id, redirect_uri=redirect_uri, state=sign_oauth_state(admin_id))


def complete_oauth_callback(db: Session, *, redirect_uri: str, code: str) -> tuple[CalendarCredential, list[dict]]:
    """Exchanges the code, stores the tokens (calendar not yet chosen),
    and returns the account's calendar list so the caller can present a
    choice. Any previously-connected credential is deactivated first —
    only one account is ever active at a time."""
    client_id, client_secret = _oauth_client(db)
    token_data = google.exchange_code(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, code=code)

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        # Google only issues one on first consent for this account+app;
        # without it we can't stay connected past the access token's
        # ~1 hour lifetime, so this must surface as an error, not a
        # credential that silently stops working later.
        raise google.GoogleCalendarError(
            "Google did not return a refresh_token — the account may have already granted access once "
            "before; revoke access at https://myaccount.google.com/permissions and reconnect."
        )

    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=token_data.get("expires_in", 3600))

    for existing in db.scalars(select(CalendarCredential).where(CalendarCredential.is_active.is_(True))):
        existing.is_active = False

    credential = CalendarCredential(
        provider="google",
        access_token=encrypt_secret(token_data["access_token"]),
        refresh_token=encrypt_secret(refresh_token),
        token_expires_at=expires_at,
        calendar_id=None, is_active=False,
    )
    db.add(credential)
    db.add(AuditLog(action="calendar_sync.connect"))
    db.flush()

    calendars = google.list_calendars(token_data["access_token"])
    return credential, calendars


def select_calendar(db: Session, credential_id: str, *, calendar_id: str,
                     actor_id: str | None, actor_username: str | None) -> CalendarCredential:
    credential = db.get(CalendarCredential, credential_id)
    if credential is None:
        raise KeyError(f"No calendar credential {credential_id!r}")
    credential.calendar_id = calendar_id
    credential.is_active = True
    db.add(AuditLog(actor_id=actor_id, actor_username=actor_username,
                     action="calendar_sync.select_calendar", target=credential_id, detail=calendar_id))
    return credential


def disconnect(db: Session, *, actor_id: str | None, actor_username: str | None) -> bool:
    """Deletes the credential locally regardless of whether Google's
    own revoke call succeeds — an admin must never be stuck with a
    connection they can't remove just because the revoke request
    itself failed (network blip, token already invalid, etc)."""
    credential = get_active_credential(db)
    if credential is None:
        return False
    try:
        google.revoke_token(decrypt_secret(credential.refresh_token))
    except Exception:
        pass  # best-effort; local disconnect proceeds regardless
    db.delete(credential)
    db.add(AuditLog(actor_id=actor_id, actor_username=actor_username, action="calendar_sync.disconnect"))
    return True


def _ensure_fresh_access_token(db: Session, credential: CalendarCredential) -> str:
    """Returns a valid access token, refreshing and persisting it first
    if the stored one is expired or about to be."""
    # SQLite doesn't actually persist tzinfo on a DateTime(timezone=True)
    # column - reads back naive - so normalize before comparing, same
    # as app/deps.py's session-expiry check.
    expires_at = credential.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
    if expires_at - _REFRESH_SKEW > dt.datetime.now(dt.timezone.utc):
        return decrypt_secret(credential.access_token)

    client_id, client_secret = _oauth_client(db)
    token_data = google.refresh_access_token(
        client_id=client_id, client_secret=client_secret, refresh_token=decrypt_secret(credential.refresh_token)
    )
    credential.access_token = encrypt_secret(token_data["access_token"])
    credential.token_expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=token_data.get("expires_in", 3600))
    db.flush()
    return token_data["access_token"]


def busy_minutes_for_date(db: Session, credential: CalendarCredential, date_str: str, *, timezone: str) -> list[tuple[int, int]]:
    """One Free/Busy API call for the whole day (not once per candidate
    slot), returned as (start_minutes, end_minutes) pairs relative to
    midnight local time — the same shape booking_service.py already
    uses for every other blocked-interval source, so it can be merged
    into the same overlap check with zero special-casing. Raises
    GoogleCalendarError on any failure; the caller decides fail-open vs
    fail-closed (booking.calendar_sync_fail_open)."""
    from zoneinfo import ZoneInfo

    access_token = _ensure_fresh_access_token(db, credential)
    date = dt.date.fromisoformat(date_str)
    tz = ZoneInfo(timezone)
    day_start = dt.datetime.combine(date, dt.time.min, tzinfo=tz)
    day_end = day_start + dt.timedelta(days=1)

    busy = google.get_busy_times(access_token, calendar_id=credential.calendar_id, time_min=day_start, time_max=day_end)

    ranges = []
    for start_iso, end_iso in busy:
        start_local = dt.datetime.fromisoformat(start_iso).astimezone(tz)
        end_local = dt.datetime.fromisoformat(end_iso).astimezone(tz)
        start_min = max(0, int((start_local - day_start).total_seconds() // 60))
        end_min = min(24 * 60, int((end_local - day_start).total_seconds() // 60))
        if end_min > start_min:
            ranges.append((start_min, end_min))
    return ranges


# ── Event creation on confirm (best-effort, mirrors notification_service.py) ──

def create_event_for_appointment(db: Session, appt_id: str) -> str | None:
    """Best-effort: creates a Google Calendar event for this
    appointment and persists its id onto Appointment.external_event_id
    if successful, returning that id so a caller holding an
    already-serialized copy of the appointment (as every router here
    does — the dict returned by booking_service.create_appointment is
    built *before* this runs) can patch it in rather than silently
    returning stale data. Never raises — an appointment is already
    confirmed by the time this runs, and a calendar-sync hiccup must
    never turn that into a broken booking response, matching
    notification_service.py's philosophy exactly."""
    if not get_setting(db, "features.calendar_sync_enabled"):
        return None
    credential = get_active_credential(db)
    if credential is None or not credential.calendar_id:
        return None
    from app.models import Appointment
    appt = db.get(Appointment, appt_id)
    if appt is None:
        return None
    try:
        access_token = _ensure_fresh_access_token(db, credential)
        timezone = get_setting(db, "booking.timezone")
        from zoneinfo import ZoneInfo
        start_local = dt.datetime.fromisoformat(f"{appt.date}T{appt.time}:00").replace(tzinfo=ZoneInfo(timezone))
        duration = _appointment_duration_minutes(db, appt)
        end_local = start_local + dt.timedelta(minutes=duration)
        event_id = google.create_event(
            access_token, calendar_id=credential.calendar_id,
            summary=f"{appt.service or 'Appointment'} — {appt.name}",
            description=appt.notes or "", start_iso=start_local.isoformat(), end_iso=end_local.isoformat(),
            timezone=timezone,
        )
        appt.external_event_id = event_id
        db.flush()
        return event_id
    except Exception:
        import logging
        logging.getLogger("perennia.calendar_sync").exception(
            "Google Calendar event creation failed for appointment %s", appt_id
        )
        return None


def delete_event_for_appointment(db: Session, appt_id: str) -> None:
    """Best-effort cleanup on cancel/reschedule — never raises. Clears
    external_event_id on success so a later call is a no-op rather
    than repeatedly attempting to delete an event that's already
    gone."""
    from app.models import Appointment
    appt = db.get(Appointment, appt_id)
    if appt is None or not appt.external_event_id:
        return
    credential = get_active_credential(db)
    if credential is None or not credential.calendar_id:
        return
    try:
        access_token = _ensure_fresh_access_token(db, credential)
        google.delete_event(access_token, calendar_id=credential.calendar_id, event_id=appt.external_event_id)
        appt.external_event_id = None
        db.flush()
    except Exception:
        import logging
        logging.getLogger("perennia.calendar_sync").exception(
            "Google Calendar event deletion failed for appointment %s", appt_id
        )


def _appointment_duration_minutes(db: Session, appt) -> int:
    from app.models import Service
    if appt.service_id:
        svc = db.get(Service, appt.service_id)
        if svc is not None:
            return svc.duration_minutes
    return get_setting(db, "booking.slot_minutes")
