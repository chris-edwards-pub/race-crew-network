"""Email rate limiting, queue management, and admin alerts."""

import logging
from datetime import datetime, timedelta, timezone

from app import db
from app.models import EmailQueue, NotificationLog, SiteSetting, User

logger = logging.getLogger(__name__)


def _get_setting(key: str, default: str = "") -> str:
    """Load a SiteSetting value, returning default if not found."""
    setting = SiteSetting.query.filter_by(key=key).first()
    return setting.value if setting and setting.value else default


def get_hourly_email_limit() -> int:
    """Return the configured hourly email rate limit (default 50)."""
    value = _get_setting("rate_limit_emails_per_hour", "50")
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        return 50


def get_emails_sent_this_hour() -> int:
    """Count emails sent in the last hour (NotificationLog + sent queue entries)."""
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(
        tzinfo=None
    )
    log_count = NotificationLog.query.filter(
        NotificationLog.sent_at >= one_hour_ago
    ).count()
    queue_sent_count = EmailQueue.query.filter(
        EmailQueue.status == "sent",
        EmailQueue.sent_at >= one_hour_ago,
    ).count()
    return log_count + queue_sent_count


def is_within_email_rate_limit() -> bool:
    """Return True if we can still send emails this hour."""
    return get_emails_sent_this_hour() < get_hourly_email_limit()


def queue_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> EmailQueue:
    """Add an email to the queue for later delivery."""
    entry = EmailQueue(
        to_email=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        status="pending",
    )
    db.session.add(entry)
    db.session.commit()
    logger.info("Email to %s queued (rate limit reached)", to)
    return entry


def send_rate_limit_alert() -> None:
    """Send an alert to admins that the rate limit was hit.

    Bypasses the rate limit by calling _send_via_ses() directly.
    Deduped to at most one alert per hour via NotificationLog.
    """
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(
        tzinfo=None
    )
    recent_alert = NotificationLog.query.filter(
        NotificationLog.notification_type == "rate_limit_alert",
        NotificationLog.sent_at >= one_hour_ago,
    ).first()
    if recent_alert:
        return

    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        return

    from app.admin.email_service import _send_via_ses

    limit = get_hourly_email_limit()
    subject = "Race Crew Network — Email Rate Limit Reached"
    body_text = (
        f"The email rate limit of {limit} emails per hour has been reached.\n\n"
        "Excess emails have been queued and will be sent when capacity is available.\n\n"
        "You can adjust this limit in Email Settings or process the queue manually."
    )
    body_html = (
        f"<p>The email rate limit of <strong>{limit} emails per hour</strong> "
        "has been reached.</p>"
        "<p>Excess emails have been queued and will be sent when capacity "
        "is available.</p>"
        "<p>You can adjust this limit in Email Settings or process the queue "
        "manually.</p>"
    )

    try:
        _send_via_ses(admin.email, subject, body_text, body_html)
        log_entry = NotificationLog(
            notification_type="rate_limit_alert",
            user_id=admin.id,
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        logger.exception("Failed to send rate limit alert to admin")


def process_email_queue() -> dict:
    """Send pending queued emails, respecting the hourly rate limit.

    Returns dict with 'sent' and 'remaining' counts.
    """
    from app.admin.email_service import _send_via_ses

    pending = (
        EmailQueue.query.filter_by(status="pending")
        .order_by(EmailQueue.queued_at)
        .all()
    )

    sent = 0
    for entry in pending:
        if not is_within_email_rate_limit():
            break

        try:
            _send_via_ses(
                entry.to_email, entry.subject, entry.body_text, entry.body_html
            )
            entry.status = "sent"
            entry.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        except Exception as exc:
            entry.status = "failed"
            entry.error_message = str(exc)[:500]
            logger.exception("Failed to send queued email #%d", entry.id)

        db.session.commit()
        if entry.status == "sent":
            sent += 1

    remaining = EmailQueue.query.filter_by(status="pending").count()
    return {"sent": sent, "remaining": remaining}


def clear_email_queue() -> int:
    """Delete all pending emails from the queue. Returns count deleted."""
    count = EmailQueue.query.filter_by(status="pending").delete()
    db.session.commit()
    return count
