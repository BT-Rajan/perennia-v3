"""
Booking business logic. Timezone, notice window, and how far ahead you
can book still come from the booking.* settings registry
(app/settings_registry.py), read fresh on every call. As of Pass 9
(docs/CALENDAR_MODULE_PLAN.md), *which hours are open* comes from
AvailabilityRule (app/availability_service.py) instead of the old
booking.workdays/day_start_hour/day_end_hour trio — unless no
AvailabilityRule exists anywhere yet, in which case those settings are
still used exactly as before, so an install that predates Pass 9 (or
simply hasn't touched Availability) keeps behaving identically.

Pass 8 adds what a *service* contributes on top of the day's open
hours: its own duration and buffer time. A booking's service_id is
optional — a site that has never defined a Service occupies one
booking.slot_minutes-sized grid slot with no buffer. When a service is
given, slot generation still snaps to the same booking.slot_minutes
grid (so times stay predictable and stable across services) but each
candidate slot's *occupied span* is the service's own duration plus its
buffers, checked for overlap against every other booking that day
(rather than an exact-time-string match, which only ever worked because
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


def _day_ranges(db: Session, cfg: dict, date: dt.date, service_id: str | None) -> list[tuple[int, int]]:
    """Open (start_minutes, end_minutes) ranges for this date, resolved
    through availability_service.effective_ranges. Falls back to the
    legacy single-range booking.workdays/day_start_hour/day_end_hour
    settings when no AvailabilityRule exists anywhere yet — see that
    function's docstring and the module docstring above."""
    from app import availability_service
    ranges = availability_service.effective_ranges(
        db, service_id=service_id, weekday=date.weekday(), date_str=date.isoformat()
    )
    if ranges is not None:
        return ranges
    if date.weekday() not in cfg["workdays"]:
        return []
    if cfg["day_end_hour"] <= cfg["day_start_hour"]:
        return []  # inconsistent hours - treat as closed rather than erroring
    return [(cfg["day_start_hour"] * 60, cfg["day_end_hour"] * 60)]


def _grid_slots_for_ranges(cfg: dict, ranges: list[tuple[int, int]]) -> list[str]:
    """Candidate start times on the booking.slot_minutes grid, across
    every open range for the day (a split day — e.g. 09:00-12:00 and
    13:00-17:00 — just means two ranges, each gridded independently;
    duplicates across overlapping ranges are deduped defensively)."""
    seen: set[str] = set()
    slots: list[str] = []
    for start_min, end_min in ranges:
        t = start_min
        while t < end_min:
            hh, mm = divmod(t, 60)
            s = f"{hh:02d}:{mm:02d}"
            if s not in seen:
                seen.add(s)
                slots.append(s)
            t += cfg["slot_minutes"]
    slots.sort()
    return slots


def _fits_in_ranges(start_min: int, end_min: int, ranges: list[tuple[int, int]]) -> bool:
    return any(r_start <= start_min and end_min <= r_end for r_start, r_end in ranges)


def _booked_intervals(db: Session, cfg: dict, date_str: str, *, exclude_id: str | None = None) -> list[tuple[int, int]]:
    """Each confirmed *or pending* appointment that day, as a
    (start, end) range in minutes-from-midnight, already expanded by
    *that appointment's own* service buffers (or the legacy
    single-slot default if it has none). A later slot's own buffer is
    applied separately by the caller, so two adjacent bookings each get
    their own buffer honored rather than only one side of the gap
    being protected.

    Pending holds the slot on purpose (Pass 10,
    docs/CALENDAR_MODULE_PLAN.md / PASS10_NOTES.md): the alternative —
    a second visitor booking the same slot while the first request
    awaits organizer approval — is a worse failure mode for a small
    business than a slot looking briefly unavailable."""
    stmt = select(Appointment).where(Appointment.date == date_str, Appointment.status.in_(("confirmed", "pending")))
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

    ranges = _day_ranges(db, cfg, date, service_id)
    if not ranges:
        return []

    all_slots = _grid_slots_for_ranges(cfg, ranges)
    if not all_slots:
        return []

    duration, buf_before, buf_after = _duration_and_buffers(cfg, service)
    blocked = _booked_intervals(db, cfg, date_str, exclude_id=exclude_id)
    earliest_bookable = now + dt.timedelta(hours=cfg["min_notice_hours"])

    out = []
    for s in all_slots:
        start_min = _time_to_minutes(s)
        end_min = start_min + duration
        if not _fits_in_ranges(start_min, end_min, ranges):
            continue  # wouldn't finish within an open range (e.g. runs past closing)

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
        status="pending" if (svc is not None and svc.requires_confirmation) else "confirmed",
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
    return {"ok": True, "id": appt.id, "pending": appt.status == "pending", "appointment": _serialize(db, appt)}


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
        "notes": appt.notes, "status": appt.status,
        "confirmed_at": appt.confirmed_at.isoformat() if appt.confirmed_at else None,
        "answers": answers,
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


def admin_accept_appointment(db: Session, appt_id: str) -> dict:
    """Valid only from 'pending' — accepting an already-confirmed or
    cancelled appointment is a state-machine error, not something to
    silently allow or 500 on, so it comes back as a typed 'invalid_state'
    the router can turn into a 409."""
    appt = db.get(Appointment, appt_id)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    if appt.status != "pending":
        return {"ok": False, "error": "invalid_state"}
    appt.status = "confirmed"
    appt.confirmed_at = dt.datetime.now(dt.timezone.utc)
    return {"ok": True, "appointment": _serialize(db, appt)}


def admin_reject_appointment(db: Session, appt_id: str, *, reason: str = "") -> dict:
    """Valid only from 'pending', same as accept. `reason` is folded
    into `notes` with a distinguishable "[declined]" prefix rather than
    a new column, consistent with keeping the schema lean — see
    PASS10_NOTES.md for why a dedicated column wasn't worth it here."""
    appt = db.get(Appointment, appt_id)
    if appt is None:
        return {"ok": False, "error": "not_found"}
    if appt.status != "pending":
        return {"ok": False, "error": "invalid_state"}
    appt.status = "cancelled"
    reason = (reason or "").strip()
    prefix = f"[declined] {reason}" if reason else "[declined]"
    appt.notes = f"{prefix}\n{appt.notes}" if appt.notes else prefix
    return {"ok": True, "appointment": _serialize(db, appt)}
