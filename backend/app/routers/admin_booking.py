from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import booking_service
from app.db import get_db
from app.deps import get_current_admin, require_csrf
from app.models import AdminUser

router = APIRouter(prefix="/admin/api/booking", tags=["admin-booking"], dependencies=[Depends(require_csrf)])


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
