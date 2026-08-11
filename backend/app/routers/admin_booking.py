from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import booking_service, notification_service, webhook_service
from app.db import get_db
from app.deps import get_current_admin, require_csrf
from app.models import AdminUser

router = APIRouter(prefix="/admin/api/booking", tags=["admin-booking"], dependencies=[Depends(require_csrf)])


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=500)


@router.get("/appointments")
def list_appointments(
    date_from: str | None = None, date_to: str | None = None, status_filter: str | None = None,
    admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    return booking_service.list_appointments(db, date_from=date_from, date_to=date_to, status=status_filter)


@router.post("/appointments/{appt_id}/cancel")
def admin_cancel(appt_id: str, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    result = booking_service.admin_cancel_appointment(db, appt_id)
    db.commit()
    if not result["ok"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No appointment {appt_id!r}")
    return result


def _raise_for_error(error: str, appt_id: str) -> None:
    if error == "not_found":
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No appointment {appt_id!r}")
    # invalid_state: exists, but not in 'pending' — a conflict with the
    # resource's current state, not a malformed request.
    raise HTTPException(status.HTTP_409_CONFLICT, f"Appointment {appt_id!r} is not pending")


@router.post("/appointments/{appt_id}/accept")
def admin_accept(appt_id: str, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    result = booking_service.admin_accept_appointment(db, appt_id)
    db.commit()
    if not result["ok"]:
        _raise_for_error(result["error"], appt_id)
    notification_service.notify_booking_accepted(db, result["appointment"])
    webhook_service.dispatch_event(db, "booking.accepted", result["appointment"])
    db.commit()
    return result


@router.post("/appointments/{appt_id}/reject")
def admin_reject(
    appt_id: str, body: RejectIn,
    admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    result = booking_service.admin_reject_appointment(db, appt_id, reason=body.reason)
    db.commit()
    if not result["ok"]:
        _raise_for_error(result["error"], appt_id)
    notification_service.notify_booking_declined(db, result["appointment"], reason=body.reason)
    webhook_service.dispatch_event(db, "booking.declined", result["appointment"])
    db.commit()
    return result
