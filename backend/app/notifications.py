"""Opt-in SMTP/Twilio outbox. Provider acceptance is not delivery confirmation."""
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import smtplib
import ssl
import httpx
from app.config import get_settings
from app.operations import database


def table(db):
    db.execute("CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, city TEXT, channel TEXT, recipient TEXT, body TEXT, expires TEXT, status TEXT, detail TEXT, created_at TEXT)")


def enqueue(snapshot):
    settings = get_settings()
    city = snapshot["location"].id
    if snapshot["mode"] != "live" or city not in settings.alert_cities.split(","):
        return
    peak = max(snapshot["forecast"], key=lambda r:r["aqi"])
    if peak["aqi"] < 101:
        return
    level = "emergency" if peak["aqi"] >= 301 else "warning" if peak["aqi"] >= 151 else "watch"
    body = f"Vayu {city}: {level}; forecast peak screening index {peak['aqi']} at {peak['timestamp'].isoformat()}. Source quality: {snapshot['quality']}. Provisional forecast, not an official advisory. Check the local dashboard and authority guidance."
    expiry = max(r["timestamp"] for r in snapshot["forecast"]).isoformat()
    # Deduplicate by city, local collection UTC day, severity and recipient.
    day = datetime.now(timezone.utc).date().isoformat()
    with database() as db:
        table(db)
        for channel, recipient in [("email", settings.alert_email_to), ("sms", settings.alert_sms_to)]:
            if not recipient.strip():
                continue
            key = hashlib.sha256(f"{city}|{day}|{level}|{channel}|{recipient}".encode()).hexdigest()
            db.execute("INSERT OR IGNORE INTO deliveries VALUES (?,?,?,?,?,?,?,'',?)", (key,city,channel,recipient.strip(),body,expiry,"pending" if settings.notifications_enabled else "dry_run",datetime.now(timezone.utc).isoformat()))


def send(channel, recipient, body, settings):
    if channel == "email":
        if not all([settings.smtp_host,settings.smtp_from,settings.smtp_username,settings.smtp_password]):
            raise ValueError("SMTP credentials are not configured")
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = settings.smtp_from, recipient, "Vayu forecast health watch"
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings.smtp_username, settings.smtp_password)
            refused = smtp.send_message(message)
            if refused:
                raise ValueError("SMTP recipient rejected")
        return "SMTP server accepted; mailbox delivery unconfirmed"
    if not all([settings.twilio_account_sid,settings.twilio_auth_token,settings.twilio_from]):
        raise ValueError("SMS credentials are not configured")
    response = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json", auth=(settings.twilio_account_sid,settings.twilio_auth_token), data={"From":settings.twilio_from,"To":recipient,"Body":body}, timeout=20)
    response.raise_for_status()
    return "SMS provider accepted; handset delivery unconfirmed"


def dispatch():
    settings = get_settings()
    if not settings.notifications_enabled:
        return
    with database() as db:
        table(db)
        rows = [dict(r) for r in db.execute("SELECT * FROM deliveries WHERE status='pending' ORDER BY created_at LIMIT 20")]
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        with database() as db:
            status = "expired" if row["expires"] <= now else "sending"
            changed = db.execute("UPDATE deliveries SET status=? WHERE id=? AND status='pending'", (status,row["id"]))
            if changed.rowcount != 1 or status == "expired":
                continue
        try:
            detail = send(row["channel"], row["recipient"], row["body"], settings)
            status = "accepted"
        except Exception as exc:
            # No raw provider errors, addresses, credentials or URLs in logs.
            detail, status = f"{type(exc).__name__}; check provider configuration. Acceptance may be unknown; do not blindly retry.", "failed"
        with database() as db:
            db.execute("UPDATE deliveries SET status=?,detail=? WHERE id=?", (status,detail,row["id"]))


def delivery_status():
    with database() as db:
        table(db)
        return [dict(r) for r in db.execute("SELECT city,channel,status,detail,created_at FROM deliveries ORDER BY created_at DESC LIMIT 100")]
