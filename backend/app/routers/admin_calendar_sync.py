from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin, require_csrf
from app.google_calendar_client import GoogleCalendarError
from app.models import AdminUser
from app.settings_service import get_setting

router = APIRouter(prefix="/admin/api/calendar-sync", tags=["admin-calendar-sync"], dependencies=[Depends(require_csrf)])


class StatusOut(BaseModel):
    connected: bool
    provider: str | None = None
    calendar_id: str | None = None
    connected_at: str | None = None


class SelectCalendarIn(BaseModel):
    credential_id: str
    calendar_id: str = Field(min_length=1, max_length=512)


class CalendarChoiceOut(BaseModel):
    id: str
    summary: str
    primary: bool


class CallbackOut(BaseModel):
    credential_id: str
    calendars: list[CalendarChoiceOut]


def _redirect_uri(db: Session) -> str:
    redirect_uri = get_setting(db, "calendar_sync.google_redirect_uri")
    if not redirect_uri:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "calendar_sync.google_redirect_uri must be configured first")
    return redirect_uri


@router.get("/status", response_model=StatusOut)
def sync_status(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app import calendar_sync_service
    credential = calendar_sync_service.get_active_credential(db)
    if credential is None:
        return StatusOut(connected=False)
    return StatusOut(
        connected=True, provider=credential.provider, calendar_id=credential.calendar_id,
        connected_at=credential.connected_at.isoformat(),
    )


@router.get("/connect")
def connect(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """A real browser navigation (the admin clicks a "Connect" link/
    button), not a fetch() call — relies on the session cookie for
    auth exactly as any top-level GET navigation would, and on the
    signed `state` round-tripped through Google for CSRF protection
    across the redirect (see app/security.py's oauth-state signing)."""
    from app import calendar_sync_service
    try:
        url = calendar_sync_service.build_connect_url(db, redirect_uri=_redirect_uri(db), admin_id=admin.id)
    except calendar_sync_service.CalendarSyncNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return RedirectResponse(url)


@router.get("/callback", response_model=CallbackOut)
def callback(code: str, state: str, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app import calendar_sync_service
    from app.security import unsign_oauth_state

    signed_admin_id = unsign_oauth_state(state)
    if signed_admin_id is None or signed_admin_id != admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired OAuth state")

    try:
        credential, calendars = calendar_sync_service.complete_oauth_callback(
            db, redirect_uri=_redirect_uri(db), code=code
        )
        db.commit()
    except (calendar_sync_service.CalendarSyncNotConfigured, GoogleCalendarError) as e:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return CallbackOut(credential_id=credential.id, calendars=[CalendarChoiceOut(**c) for c in calendars])


@router.post("/select")
def select_calendar(body: SelectCalendarIn, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app import calendar_sync_service
    try:
        calendar_sync_service.select_calendar(
            db, body.credential_id, calendar_id=body.calendar_id, actor_id=admin.id, actor_username=admin.username
        )
        db.commit()
    except KeyError as e:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return {"ok": True}


@router.post("/disconnect")
def disconnect(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Always completes the local disconnect, even if the best-effort
    revoke call to Google fails — see calendar_sync_service.disconnect."""
    from app import calendar_sync_service
    ok = calendar_sync_service.disconnect(db, actor_id=admin.id, actor_username=admin.username)
    db.commit()
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No calendar is currently connected")
    return {"ok": True}
