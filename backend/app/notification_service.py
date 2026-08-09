"""
Sends the actual notifications: booking confirmations/cancellations/
reschedules (email + WhatsApp) and internal staff alerts for new
bookings and new chat leads. Every function here is best-effort by
design — a notification failure (bad SMTP creds, WhatsApp provider
down, nothing configured at all) is logged and swallowed, never raised
up to break the booking/chat request that triggered it. The person who
just booked an appointment gets their confirmation code back
regardless of whether the confirmation email actually sent.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app import whatsapp_client
from app.settings_service import get_setting

logger = logging.getLogger("perennia.notifications")


def _lang_value(value, lang: str):
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or next(iter(value.values()), "")
    return value


def render(template: dict, lang: str, **kwargs) -> dict:
    """template is a JSON setting value shaped {subject, body} (per
    language if i18n). Returns {subject, body} with placeholders filled."""
    picked = _lang_value(template, lang)
    return {k: v.format(**kwargs) for k, v in picked.items()}


def render_text(template, lang: str, **kwargs) -> str:
    return _lang_value(template, lang).format(**kwargs)


# ── Low-level senders ──────────────────────────────────────────────

def send_email(db: Session, *, to_email: str, subject: str, body_text: str) -> bool:
    if not get_setting(db, "notifications.email_enabled"):
        return False
    host = get_setting(db, "notifications.smtp_host")
    from_email = get_setting(db, "notifications.from_email")
    if not host or not from_email:
        logger.info("Email notification skipped: SMTP not fully configured")
        return False

    from_name = get_setting(db, "notifications.from_name") or _lang_value(get_setting(db, "branding.site_name"), "en")
    port = get_setting(db, "notifications.smtp_port")
    use_tls = get_setting(db, "notifications.smtp_use_tls")
    username = get_setting(db, "notifications.smtp_username")
    password = get_setting(db, "notifications.smtp_password")

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        logger.warning("Email notification failed to %s: %s", to_email, e)
        return False


def send_whatsapp(db: Session, *, to_number: str, message: str) -> bool:
    if not get_setting(db, "notifications.whatsapp_enabled") or not to_number:
        return False
    provider = get_setting(db, "notifications.whatsapp_provider")
    if provider == "none":
        return False
    try:
        whatsapp_client.send_message(
            provider=provider,
            account_id=get_setting(db, "notifications.whatsapp_account_id"),
            api_key=get_setting(db, "notifications.whatsapp_api_key"),
            from_number=get_setting(db, "notifications.whatsapp_from_number"),
            to_number=to_number,
            message=message,
        )
        return True
    except whatsapp_client.WhatsAppError as e:
        logger.warning("WhatsApp notification failed to %s: %s", to_number, e)
        return False


# ── Booking notifications ────────────────────────────────────────────

def _notify_booking(db: Session, appt: dict, *, email_template_key: str, whatsapp_template_key: str) -> None:
    try:
        ctx = {
            "name": appt["name"], "date": appt["date"], "time": appt["time"],
            "id": appt["id"], "service": appt.get("service") or "your enquiry",
        }
        lang = appt.get("lang", "en")

        email_tpl = get_setting(db, email_template_key)
        rendered = render(email_tpl, lang, **ctx)
        send_email(db, to_email=appt["email"], subject=rendered["subject"], body_text=rendered["body"])

        if appt.get("phone"):
            wa_tpl = get_setting(db, whatsapp_template_key)
            send_whatsapp(db, to_number=appt["phone"], message=render_text(wa_tpl, lang, **ctx))
    except Exception:
        # Malformed template (bad {placeholder} syntax from an admin
        # edit) or any other unexpected error must never break the
        # booking action that triggered this — the booking already
        # succeeded and its response has already been decided.
        logger.exception("Booking notification failed for appointment %s", appt.get("id"))


def notify_booking_confirmed(db: Session, appt: dict) -> None:
    _notify_booking(db, appt, email_template_key="templates.booking_confirmed_email",
                     whatsapp_template_key="templates.booking_confirmed_whatsapp")
    _notify_admin_new_booking(db, appt)


def notify_booking_cancelled(db: Session, appt: dict) -> None:
    _notify_booking(db, appt, email_template_key="templates.booking_cancelled_email",
                     whatsapp_template_key="templates.booking_cancelled_whatsapp")


def notify_booking_rescheduled(db: Session, appt: dict) -> None:
    _notify_booking(db, appt, email_template_key="templates.booking_rescheduled_email",
                     whatsapp_template_key="templates.booking_rescheduled_whatsapp")


# ── Internal staff alerts ────────────────────────────────────────────

def _admin_email(db: Session) -> str:
    return get_setting(db, "notifications.admin_alert_email")


def _notify_admin_new_booking(db: Session, appt: dict) -> None:
    to = _admin_email(db)
    if not to:
        return
    try:
        rendered = render(get_setting(db, "templates.new_booking_admin_alert"), "en", **{
            "name": appt["name"], "email": appt["email"], "date": appt["date"], "time": appt["time"],
            "id": appt["id"], "service": appt.get("service") or "general enquiry",
        })
        send_email(db, to_email=to, subject=rendered["subject"], body_text=rendered["body"])
    except Exception:
        logger.exception("New-booking admin alert failed for appointment %s", appt.get("id"))


def notify_admin_new_lead(db: Session, *, email: str, message: str) -> None:
    to = _admin_email(db)
    if not to:
        return
    try:
        rendered = render(get_setting(db, "templates.new_lead_admin_alert"), "en", email=email, message=message)
        send_email(db, to_email=to, subject=rendered["subject"], body_text=rendered["body"])
    except Exception:
        logger.exception("New-lead admin alert failed for %s", email)
