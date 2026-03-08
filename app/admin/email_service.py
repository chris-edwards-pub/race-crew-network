import hashlib
import hmac
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from flask import current_app, url_for

from app.models import SiteSetting, User

logger = logging.getLogger(__name__)


def _get_ses_client(region: str | None = None):
    """Return a boto3 SES client for the given (or default) region."""
    if not region:
        region = current_app.config["AWS_REGION"]
    return boto3.client("ses", region_name=region)


def load_email_settings() -> dict:
    """Load email settings from SiteSetting table."""
    sender = ""
    region = current_app.config["AWS_REGION"]

    sender_to = ""

    setting = SiteSetting.query.filter_by(key="ses_sender").first()
    if setting and setting.value:
        sender = setting.value

    to_setting = SiteSetting.query.filter_by(key="ses_sender_to").first()
    if to_setting and to_setting.value:
        sender_to = to_setting.value

    region_setting = SiteSetting.query.filter_by(key="ses_region").first()
    if region_setting and region_setting.value:
        region = region_setting.value

    return {"ses_sender": sender, "ses_sender_to": sender_to, "ses_region": region}


def is_email_configured() -> bool:
    """Return True if a SES sender email is configured."""
    setting = SiteSetting.query.filter_by(key="ses_sender").first()
    return bool(setting and setting.value and setting.value.strip())


def generate_unsubscribe_token(email: str) -> str:
    """Generate an HMAC-SHA256 token for unsubscribe verification."""
    secret = current_app.config["SECRET_KEY"]
    return hmac.new(
        secret.encode("utf-8"),
        email.lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_unsubscribe_token(email: str, token: str) -> bool:
    """Verify an unsubscribe HMAC token."""
    expected = generate_unsubscribe_token(email)
    return hmac.compare_digest(expected, token)


def generate_unsubscribe_url(email: str) -> str:
    """Generate a full unsubscribe URL with HMAC token."""
    token = generate_unsubscribe_token(email)
    return url_for("email.unsubscribe", email=email, token=token, _external=True)


def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    """Send an email via AWS SES with unsubscribe headers.

    Raises ValueError if email is not configured.
    Raises botocore.exceptions.ClientError on SES failures.
    Skips sending if the recipient has opted out.
    """
    # Check opt-in status
    user = User.query.filter_by(email=to).first()
    if user and not user.email_opt_in:
        logger.info("Skipping email to %s: user has opted out", to)
        return

    settings = load_email_settings()
    sender = settings["ses_sender"]
    if not sender:
        raise ValueError("Email not configured: no SES sender address set.")

    region = settings["ses_region"]
    client = _get_ses_client(region)

    # Build MIME message for custom headers
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    # Add unsubscribe headers (RFC 8058)
    unsubscribe_url = generate_unsubscribe_url(to)
    msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # Attach text part
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # Attach HTML part with unsubscribe footer
    if body_html:
        footer = (
            '<hr style="margin-top:20px;border:none;border-top:1px solid #ddd;">'
            '<p style="font-size:12px;color:#888;">'
            f'<a href="{unsubscribe_url}">Unsubscribe</a> from Race Crew Network emails.'
            "</p>"
        )
        body_html_with_footer = body_html + footer
        msg.attach(MIMEText(body_html_with_footer, "html", "utf-8"))

    client.send_raw_email(
        Source=sender,
        Destinations=[to],
        RawMessage={"Data": msg.as_string()},
    )
