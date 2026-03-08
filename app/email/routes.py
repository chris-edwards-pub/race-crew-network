import json
import logging

import requests
from flask import abort, render_template, request

from app import csrf, db
from app.admin.email_service import verify_unsubscribe_token
from app.email import bp
from app.models import User

logger = logging.getLogger(__name__)


@bp.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    """Handle email unsubscribe requests.

    GET:  Show confirmation page.
    POST: Process one-click unsubscribe (RFC 8058) — returns 204.
    """
    email = request.args.get("email", "").strip().lower()
    token = request.args.get("token", "")

    if not email or not token or not verify_unsubscribe_token(email, token):
        abort(400)

    user = User.query.filter_by(email=email).first()
    if not user:
        abort(404)

    if request.method == "POST":
        user.email_opt_in = False
        db.session.commit()
        logger.info("One-click unsubscribe processed for %s", email)
        return "", 204

    # GET — show confirmation page (user already unsubscribed)
    user.email_opt_in = False
    db.session.commit()
    logger.info("Unsubscribe via link for %s", email)
    return render_template("unsubscribe.html")


@bp.route("/webhooks/ses", methods=["POST"])
@csrf.exempt
def ses_webhook():
    """Process AWS SNS notifications for SES bounces and complaints."""
    try:
        payload = json.loads(request.get_data(as_text=True))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid JSON in SNS webhook")
        abort(400)

    msg_type = payload.get("Type")

    # Handle subscription confirmation
    if msg_type == "SubscriptionConfirmation":
        subscribe_url = payload.get("SubscribeURL")
        if subscribe_url:
            try:
                requests.get(subscribe_url, timeout=10)
                logger.info("SNS subscription confirmed")
            except requests.RequestException:
                logger.error("Failed to confirm SNS subscription")
        return "", 200

    # Handle notifications
    if msg_type == "Notification":
        try:
            message = json.loads(payload.get("Message", "{}"))
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid JSON in SNS notification message")
            return "", 200

        notification_type = message.get("notificationType")

        if notification_type == "Bounce":
            _handle_bounce(message)
        elif notification_type == "Complaint":
            _handle_complaint(message)

        return "", 200

    return "", 200


def _handle_bounce(message: dict) -> None:
    """Process SES bounce notification."""
    bounce = message.get("bounce", {})
    bounce_type = bounce.get("bounceType")
    recipients = bounce.get("bouncedRecipients", [])

    for recipient in recipients:
        email = recipient.get("emailAddress", "").lower()
        if not email:
            continue

        if bounce_type == "Permanent":
            user = User.query.filter_by(email=email).first()
            if user:
                user.email_opt_in = False
                db.session.commit()
                logger.warning("Hard bounce for %s — opted out", email)
        else:
            logger.info("Soft bounce for %s (type: %s) — no action", email, bounce_type)


def _handle_complaint(message: dict) -> None:
    """Process SES complaint notification."""
    complaint = message.get("complaint", {})
    recipients = complaint.get("complainedRecipients", [])

    for recipient in recipients:
        email = recipient.get("emailAddress", "").lower()
        if not email:
            continue

        user = User.query.filter_by(email=email).first()
        if user:
            user.email_opt_in = False
            db.session.commit()
            logger.error("Complaint received for %s — opted out", email)
