from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import booking_service
from app.config import settings
from app.db import get_db
from app.rate_limit import limiter
from app.settings_service import get_setting

router = APIRouter(prefix="/api/booking", tags=["public-booking"])


class CreateAppointmentRequest(BaseModel):
    date: str
    slot: str
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(default="", max_length=40)
    service: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=1000)


class LookupRequest(BaseModel):
    id: str = Field(max_length=16)
    email: str = Field(max_length=254)


class CancelRequest(BaseModel):
    id: str = Field(max_length=16)
    email: str = Field(max_length=254)


class RescheduleRequest(BaseModel):
    id: str = Field(max_length=16)
    email: str = Field(max_length=254)
    date: str
    time: str


@router.get("/slots")
def get_slots(date: str, db: Session = Depends(get_db)):
    if not get_setting(db, "features.booking_enabled"):
        return {"slots": []}
    try:
        return {"slots": booking_service.available_slots(db, date)}
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid date")


@router.post("/appointments")
@limiter.limit(settings.RATE_LIMIT_APPOINTMENT)
def create_appointment(request: Request, body: CreateAppointmentRequest, db: Session = Depends(get_db)):
    if not get_setting(db, "features.booking_enabled"):
        return {"ok": False, "error": "booking_disabled"}
    result = booking_service.create_appointment(
        db, date_str=body.date, time_str=body.slot, name=body.name, email=body.email,
        phone=body.phone, service=body.service, notes=body.notes,
    )
    db.commit()
    return result


@router.post("/appointments/lookup")
def lookup_appointment(body: LookupRequest, db: Session = Depends(get_db)):
    return booking_service.lookup_appointment(db, body.id, body.email)


@router.post("/appointments/cancel")
@limiter.limit(settings.RATE_LIMIT_APPOINTMENT)
def cancel_appointment(request: Request, body: CancelRequest, db: Session = Depends(get_db)):
    result = booking_service.cancel_appointment(db, body.id, body.email)
    db.commit()
    return result


@router.post("/appointments/reschedule")
@limiter.limit(settings.RATE_LIMIT_APPOINTMENT)
def reschedule_appointment(request: Request, body: RescheduleRequest, db: Session = Depends(get_db)):
    result = booking_service.reschedule_appointment(db, body.id, body.email, body.date, body.time)
    db.commit()
    return result
