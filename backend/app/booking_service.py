"""
Booking business logic. Every rule here — hours, workdays, slot length,
timezone, notice window, how far ahead you can book — comes from the
booking.* settings registry (app/settings_registry.py), read fresh on
every call. Nothing about "when is the business open" is hardcoded.
"""
from __future__ import annotations

import datetime as dt
import re
import secrets
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment
from app.settings_service import get_setting

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I — avoids lookalike confusion


def _booking_config(db: Session) -> dict:
    return {
        "timezone": get_setting(db, "booking.timezone"),
        "slot_minutes": get_setting(db, "booking.slot_minutes"),
        "day_start_hour": get_setting(db, "booking.day_start_hour"),
        "day_end_hour": get_setting(db, "booking.day_end_hour"),
        "workdays": set(get_setting(db, "booking.workdays")),
        "max_days_ahead": get_setting(db, "booking.max_days_ahead"),
        "min_notice_hours": get_setting(db, "booking.min_notice_hours"),
    }


def _now(cfg: dict) -> dt.datetime:
    return dt.datetime.now(ZoneInfo(cfg["timezone"]))


def _all_slots_for_day(cfg: dict, date: dt.date) -> list[str]:
    if date.weekday() not in cfg["workdays"]:
        return []
    if cfg["day_end_hour"] <= cfg["day_start_hour"]:
        return []  # inconsistent hours - treat as closed rather than erroring
    slots = []
    t = dt.datetime.combine(date, dt.time(hour=cfg["day_start_hour"]))
    end = dt.datetime.combine(date, dt.time(hour=cfg["day_end_hour"]))
    step = dt.timedelta(minutes=cfg["slot_minutes"])
    while t < end:
        slots.append(t.strftime("%H:%M"))
        t += step
    return slots


def _booked_times(db: Session, date_str: str, *, exclude_id: str | None = None) -> set[str]:
    stmt = select(Appointment.id, Appointment.time).where(
        Appointment.date == date_str, Appointment.status == "confirmed"
    )
    return {t for (aid, t) in db.execute(stmt) if aid != exclude_id}


def available_slots(db: Session, date_str: str, *, exclude_id: str | None = None) -> list[str]:
    """Raises ValueError on a malformed date string; returns [] (not an
    error) for any date that's simply unbookable - closed day, past,
    too far ahead - since "no slots" is a normal, expected outcome."""
    date = dt.date.fromisoformat(date_str)  # raises ValueError on bad format
    cfg = _booking_config(db)
    now = _now(cfg)
    today = now.date()

    if date < today or date > today + dt.timedelta(days=cfg["max_days_ahead"]):
        return []

    all_slots = _all_slots_for_day(cfg, date)
    if not all_slots:
        return []

    booked = _booked_times(db, date_str, exclude_id=exclude_id)
    earliest_bookable = now + dt.timedelta(hours=cfg["min_notice_hours"])

    out = []
    for s in all_slots:
        if s in booked:
            continue
        slot_dt = dt.datetime.combine(date, dt.time.fromisoformat(s), tzinfo=ZoneInfo(cfg["timezone"]))
        if slot_dt < earliest_bookable:
            continue
        out.append(s)
    return out


def _generate_code(db: Session) -> str:
    for _ in range(10):
        code = "PRN-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        if db.get(Appointment, code) is None:
            return code
    raise RuntimeError("Could not generate a unique appointment code")


def create_appointment(
    db: Session, *, date_str: str, time_str: str, name: str, email: str,
    phone: str = "", service: str = "", notes: str = "",
) -> dict:
    if not name.strip():
        return {"ok": False, "error": "invalid_name"}
    if not EMAIL_RE.match(email):
        return {"ok": False, "error": "invalid_email"}
    try:
        slots = available_slots(db, date_str)
    except ValueError:
        return {"ok": False, "error": "invalid_date"}

    if time_str not in slots:
        return {"ok": False, "error": "slot_unavailable"}

    appt = Appointment(
        id=_generate_code(db), date=date_str, time=time_str,
        name=name.strip(), email=email.strip(), phone=phone.strip(),
        service=service.strip(), notes=notes.strip(),
    )
    db.add(appt)
    db.flush()

    # A booking is a strong, unambiguous signal — always worth a lead
    # record, whether or not this person ever chatted first.
    from app import leads_service
    leads_service.capture_lead(
        db, email=appt.email, source="booking", name=appt.name, phone=appt.phone,
        transcript_entry={"from": "system", "text": f"Booked {appt.date} {appt.time} ({appt.service or 'general enquiry'})"},
    )

    return {"ok": True, "id": appt.id}


def _find_by_id_and_email(db: Session, appt_id: str, email: str) -> Appointment | None:
    appt = db.get(Appointment, appt_id)
    if appt is None or appt.email.lower() != email.strip().lower():
        return None
    return appt


def lookup_appointment(db: Session, appt_id: str, email: str) -> dict:
    appt = _find_by_id_and_email(db, appt_id, email)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "appointment": _serialize(appt)}


def _has_enough_notice(db: Session, appt: Appointment) -> bool:
    cfg = _booking_config(db)
    now = _now(cfg)
    appt_dt = dt.datetime.combine(
        dt.date.fromisoformat(appt.date), dt.time.fromisoformat(appt.time), tzinfo=ZoneInfo(cfg["timezone"])
    )
    # An appointment already in the past always allows cancellation
    # (nothing left to protect by refusing) — reschedules are guarded
    # separately, by the new slot's own notice window.
    if appt_dt <= now:
        return True
    return appt_dt - now >= dt.timedelta(hours=cfg["min_notice_hours"])


def cancel_appointment(db: Session, appt_id: str, email: str) -> dict:
    appt = _find_by_id_and_email(db, appt_id, email)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    if appt.status == "cancelled":
        return {"ok": True}  # idempotent
    if not _has_enough_notice(db, appt):
        return {"ok": False, "error": "notice_window_passed"}
    appt.status = "cancelled"
    return {"ok": True}


def reschedule_appointment(db: Session, appt_id: str, email: str, new_date_str: str, new_time_str: str) -> dict:
    appt = _find_by_id_and_email(db, appt_id, email)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    if appt.status == "cancelled":
        return {"ok": False, "error": "already_cancelled"}
    if not _has_enough_notice(db, appt):
        return {"ok": False, "error": "notice_window_passed"}

    try:
        slots = available_slots(db, new_date_str, exclude_id=appt.id)
    except ValueError:
        return {"ok": False, "error": "invalid_date"}
    if new_time_str not in slots:
        return {"ok": False, "error": "slot_unavailable"}

    appt.date = new_date_str
    appt.time = new_time_str
    return {"ok": True, "appointment": _serialize(appt)}


def _serialize(appt: Appointment) -> dict:
    return {
        "id": appt.id, "date": appt.date, "time": appt.time, "slot": appt.time,
        "name": appt.name, "email": appt.email, "phone": appt.phone,
        "service": appt.service, "notes": appt.notes, "status": appt.status,
    }


# ── Admin-side listing ──────────────────────────────────────────────

def list_appointments(db: Session, *, date_from: str | None = None, date_to: str | None = None,
                       status: str | None = None) -> list[dict]:
    stmt = select(Appointment).order_by(Appointment.date, Appointment.time)
    if date_from:
        stmt = stmt.where(Appointment.date >= date_from)
    if date_to:
        stmt = stmt.where(Appointment.date <= date_to)
    if status:
        stmt = stmt.where(Appointment.status == status)
    return [_serialize(a) for a in db.scalars(stmt)]


def admin_cancel_appointment(db: Session, appt_id: str) -> dict:
    """Admin override - no notice-window restriction, since the whole
    point of an admin cancelling is often exactly a late-notice change
    the visitor themselves can no longer self-serve."""
    appt = db.get(Appointment, appt_id)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    appt.status = "cancelled"
    return {"ok": True}
