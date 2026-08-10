"""
Booking business logic. Every rule about *when the business is open* —
hours, workdays, timezone, notice window, how far ahead you can book —
still comes from the booking.* settings registry (app/settings_registry.py),
read fresh on every call.

Pass 8 (docs/CALENDAR_MODULE_PLAN.md) adds what a *service* contributes
on top of that: its own duration and buffer time. A booking's
service_id is optional — a site that has never defined a Service keeps
behaving exactly as it did before this pass, occupying one
booking.slot_minutes-sized grid slot with no buffer. When a service is
given, slot generation still snaps to the same booking.slot_minutes
grid (so times stay predictable and stable across services) but each
candidate slot's *occupied span* is the service's own duration plus its
buffers, checked for overlap against every other booking that day
(rather than the old exact-time-string match, which only worked because
every booking used to be the same length).
"""
from __future__ import annotations

import datetime as dt
import re
import secrets
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentQuestionAnswer, Service
from app.settings_service import get_setting

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I — avoids lookalike confusion


class InvalidServiceError(Exception):
    """Raised when a service_id is given but doesn't resolve to an
    active Service. Deliberately not a ValueError — available_slots
    already uses ValueError for "the date string was malformed," and
    callers need to tell the two apart to return the right error code."""


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


def _time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _resolve_service(db: Session, service_id: str | None) -> Service | None:
    if service_id is None:
        return None
    service = db.get(Service, service_id)
    if service is None or not service.is_active:
        raise InvalidServiceError(service_id)
    return service


def _duration_and_buffers(cfg: dict, service: Service | None) -> tuple[int, int, int]:
    """(duration_minutes, buffer_before, buffer_after). No service ->
    the pre-Pass-8 default: one grid slot, no buffer."""
    if service is None:
        return cfg["slot_minutes"], 0, 0
    return service.duration_minutes, service.buffer_before_minutes, service.buffer_after_minutes


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


def _booked_intervals(db: Session, cfg: dict, date_str: str, *, exclude_id: str | None = None) -> list[tuple[int, int]]:
    """Each confirmed appointment that day, as a (start, end) range in
    minutes-from-midnight, already expanded by *that appointment's own*
    service buffers (or the legacy single-slot default if it has none).
    A later slot's own buffer is applied separately by the caller, so
    two adjacent bookings each get their own buffer honored rather than
    only one side of the gap being protected."""
    stmt = select(Appointment).where(Appointment.date == date_str, Appointment.status == "confirmed")
    intervals = []
    for appt in db.scalars(stmt):
        if appt.id == exclude_id:
            continue
        service = db.get(Service, appt.service_id) if appt.service_id else None
        duration, buf_before, buf_after = _duration_and_buffers(cfg, service)
        start = _time_to_minutes(appt.time)
        intervals.append((start - buf_before, start + duration + buf_after))
    return intervals


def available_slots(
    db: Session, date_str: str, *, service_id: str | None = None, exclude_id: str | None = None
) -> list[str]:
    """Raises ValueError on a malformed date string, InvalidServiceError
    if service_id doesn't resolve to an active Service. Returns [] (not
    an error) for any date that's simply unbookable - closed day, past,
    too far ahead - since "no slots" is a normal, expected outcome."""
    date = dt.date.fromisoformat(date_str)  # raises ValueError on bad format
    cfg = _booking_config(db)
    service = _resolve_service(db, service_id)  # raises InvalidServiceError
    now = _now(cfg)
    today = now.date()

    if date < today or date > today + dt.timedelta(days=cfg["max_days_ahead"]):
        return []

    all_slots = _all_slots_for_day(cfg, date)
    if not all_slots:
        return []

    duration, buf_before, buf_after = _duration_and_buffers(cfg, service)
    day_end_minutes = cfg["day_end_hour"] * 60
    blocked = _booked_intervals(db, cfg, date_str, exclude_id=exclude_id)
    earliest_bookable = now + dt.timedelta(hours=cfg["min_notice_hours"])

    out = []
    for s in all_slots:
        start_min = _time_to_minutes(s)
        end_min = start_min + duration
        if end_min > day_end_minutes:
            continue  # wouldn't finish before closing

        cand_start, cand_end = start_min - buf_before, end_min + buf_after
        if any(cand_start < b_end and cand_end > b_start for b_start, b_end in blocked):
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
    phone: str = "", service: str = "", notes: str = "", lang: str = "en",
    service_id: str | None = None, answers: list[dict] | None = None,
) -> dict:
    if not name.strip():
        return {"ok": False, "error": "invalid_name"}
    if not EMAIL_RE.match(email):
        return {"ok": False, "error": "invalid_email"}
    try:
        slots = available_slots(db, date_str, service_id=service_id)
    except ValueError:
        return {"ok": False, "error": "invalid_date"}
    except InvalidServiceError:
        return {"ok": False, "error": "invalid_service"}

    if time_str not in slots:
        return {"ok": False, "error": "slot_unavailable"}

    svc = db.get(Service, service_id) if service_id else None
    answer_map: dict[str, str] = {}
    if svc is not None:
        answer_map = {a.get("question_id"): (a.get("answer") or "").strip() for a in (answers or [])}
        known_ids = {q.id for q in svc.questions}
        if set(answer_map) - known_ids:
            return {"ok": False, "error": "invalid_question"}
        if any(q.required and not answer_map.get(q.id) for q in svc.questions):
            return {"ok": False, "error": "missing_required_answer"}

    appt = Appointment(
        id=_generate_code(db), date=date_str, time=time_str, lang=lang or "en",
        name=name.strip(), email=email.strip(), phone=phone.strip(),
        service=service.strip(), service_id=service_id, notes=notes.strip(),
    )
    db.add(appt)
    db.flush()

    if svc is not None:
        for q in svc.questions:
            ans = answer_map.get(q.id, "")
            if ans:
                db.add(AppointmentQuestionAnswer(
                    appointment_id=appt.id, question_id=q.id, question_label=q.label, answer=ans
                ))

    # A booking is a strong, unambiguous signal — always worth a lead
    # record, whether or not this person ever chatted first.
    from app import leads_service
    booked_what = svc.name if svc is not None else (appt.service or "general enquiry")
    leads_service.capture_lead(
        db, email=appt.email, source="booking", name=appt.name, phone=appt.phone,
        transcript_entry={"from": "system", "text": f"Booked {appt.date} {appt.time} ({booked_what})"},
    )
    return {"ok": True, "id": appt.id, "appointment": _serialize(db, appt)}


def _find_by_id_and_email(db: Session, appt_id: str, email: str) -> Appointment | None:
    appt = db.get(Appointment, appt_id)
    if appt is None or appt.email.lower() != email.strip().lower():
        return None
    return appt


def lookup_appointment(db: Session, appt_id: str, email: str) -> dict:
    appt = _find_by_id_and_email(db, appt_id, email)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "appointment": _serialize(db, appt)}


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
        return {"ok": True, "appointment": _serialize(db, appt), "already_cancelled": True}  # idempotent
    if not _has_enough_notice(db, appt):
        return {"ok": False, "error": "notice_window_passed"}
    appt.status = "cancelled"
    return {"ok": True, "appointment": _serialize(db, appt), "already_cancelled": False}


def reschedule_appointment(db: Session, appt_id: str, email: str, new_date_str: str, new_time_str: str) -> dict:
    appt = _find_by_id_and_email(db, appt_id, email)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    if appt.status == "cancelled":
        return {"ok": False, "error": "already_cancelled"}
    if not _has_enough_notice(db, appt):
        return {"ok": False, "error": "notice_window_passed"}

    try:
        # Reschedule keeps whatever service the booking was originally
        # made under (it isn't something the visitor picks again here)
        # — if that service was deactivated since, this fails cleanly
        # rather than silently re-slotting the appointment as generic.
        slots = available_slots(db, new_date_str, service_id=appt.service_id, exclude_id=appt.id)
    except ValueError:
        return {"ok": False, "error": "invalid_date"}
    except InvalidServiceError:
        return {"ok": False, "error": "invalid_service"}
    if new_time_str not in slots:
        return {"ok": False, "error": "slot_unavailable"}

    appt.date = new_date_str
    appt.time = new_time_str
    return {"ok": True, "appointment": _serialize(db, appt)}


def _serialize(db: Session, appt: Appointment) -> dict:
    service_name = None
    if appt.service_id:
        svc = db.get(Service, appt.service_id)
        service_name = svc.name if svc is not None else None
    answers = [
        {"question_id": a.question_id, "label": a.question_label, "answer": a.answer}
        for a in db.scalars(
            select(AppointmentQuestionAnswer).where(AppointmentQuestionAnswer.appointment_id == appt.id)
        )
    ]
    return {
        "id": appt.id, "date": appt.date, "time": appt.time, "slot": appt.time,
        "name": appt.name, "email": appt.email, "phone": appt.phone,
        "service": appt.service, "service_id": appt.service_id, "service_name": service_name,
        "notes": appt.notes, "status": appt.status, "answers": answers,
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
    return [_serialize(db, a) for a in db.scalars(stmt)]


def admin_cancel_appointment(db: Session, appt_id: str) -> dict:
    """Admin override - no notice-window restriction, since the whole
    point of an admin cancelling is often exactly a late-notice change
    the visitor themselves can no longer self-serve."""
    appt = db.get(Appointment, appt_id)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    appt.status = "cancelled"
    return {"ok": True}
