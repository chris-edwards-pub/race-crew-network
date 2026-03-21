"""Email statistics helpers — SES quota, Cost Explorer, and app-level stats."""

import logging
from datetime import date, datetime, timedelta, timezone

import boto3
from flask import current_app

from app.models import EmailQueue, NotificationLog
from app.notifications.rate_limits import (get_emails_sent_this_hour,
                                           get_hourly_email_limit)

logger = logging.getLogger(__name__)


def _get_ce_client():
    """Return a boto3 Cost Explorer client.

    Uses SES credentials if configured, otherwise default chain.
    Cost Explorer is always us-east-1.
    """
    ses_key = current_app.config.get("SES_ACCESS_KEY_ID")
    ses_secret = current_app.config.get("SES_SECRET_ACCESS_KEY")
    if ses_key and ses_secret:
        return boto3.client(
            "ce",
            region_name="us-east-1",
            aws_access_key_id=ses_key,
            aws_secret_access_key=ses_secret,
        )
    return boto3.client("ce", region_name="us-east-1")


def get_ses_quota() -> dict | None:
    """Fetch SES send quota. Returns None if SES is not configured."""
    from app.admin.email_service import _get_ses_client, load_email_settings

    try:
        settings = load_email_settings()
        client = _get_ses_client(settings["ses_region"])
        resp = client.get_send_quota()
        return {
            "max_24hr_send": resp.get("Max24HourSend", 0),
            "max_send_rate": resp.get("MaxSendRate", 0),
            "sent_last_24hrs": resp.get("SentLast24Hours", 0),
        }
    except Exception:
        logger.exception("Failed to fetch SES quota")
        return None


def get_ses_statistics() -> list[dict] | None:
    """Fetch SES send statistics (last 2 weeks of 15-min data points)."""
    from app.admin.email_service import _get_ses_client, load_email_settings

    try:
        settings = load_email_settings()
        client = _get_ses_client(settings["ses_region"])
        resp = client.get_send_statistics()
        points = resp.get("SendDataPoints", [])
        return [
            {
                "timestamp": (
                    p["Timestamp"].isoformat()
                    if hasattr(p["Timestamp"], "isoformat")
                    else str(p["Timestamp"])
                ),
                "delivery_attempts": p.get("DeliveryAttempts", 0),
                "bounces": p.get("Bounces", 0),
                "complaints": p.get("Complaints", 0),
                "rejects": p.get("Rejects", 0),
            }
            for p in points
        ]
    except Exception:
        logger.exception("Failed to fetch SES statistics")
        return None


def get_ses_cost(months: int = 1) -> dict | None:
    """Fetch SES costs from AWS Cost Explorer.

    Returns {'current_month': '$X.XX', 'last_month': '$X.XX'}.
    Returns None if ce:GetCostAndUsage permission is not available.
    """
    try:
        client = _get_ce_client()
    except Exception:
        logger.exception("Failed to create Cost Explorer client")
        return None

    try:
        today = date.today()
        current_start = today.replace(day=1)
        # Cost Explorer requires Start < End; on the 1st, use tomorrow
        current_end = today if today > current_start else today + timedelta(days=1)

        # Last month
        last_month_end = current_start
        if last_month_end.month == 1:
            last_month_start = last_month_end.replace(
                year=last_month_end.year - 1, month=12
            )
        else:
            last_month_start = last_month_end.replace(month=last_month_end.month - 1)

        result = {}

        # Current month
        resp = client.get_cost_and_usage(
            TimePeriod={
                "Start": current_start.isoformat(),
                "End": current_end.isoformat(),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Simple Email Service"],
                }
            },
        )
        groups = resp.get("ResultsByTime", [])
        if groups:
            amount = (
                groups[0].get("Total", {}).get("UnblendedCost", {}).get("Amount", "0")
            )
            result["current_month"] = f"${float(amount):.2f}"
        else:
            result["current_month"] = "$0.00"

        # Last month
        resp = client.get_cost_and_usage(
            TimePeriod={
                "Start": last_month_start.isoformat(),
                "End": last_month_end.isoformat(),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Simple Email Service"],
                }
            },
        )
        groups = resp.get("ResultsByTime", [])
        if groups:
            amount = (
                groups[0].get("Total", {}).get("UnblendedCost", {}).get("Amount", "0")
            )
            result["last_month"] = f"${float(amount):.2f}"
        else:
            result["last_month"] = "$0.00"

        return result
    except client.exceptions.BillingViewNotFoundException:
        logger.info("Cost Explorer billing view not found")
        return None
    except Exception as exc:
        if "AccessDenied" in str(type(exc).__name__) or "AccessDenied" in str(exc):
            logger.info("Cost Explorer access denied — ce:GetCostAndUsage not granted")
            return None
        logger.exception("Failed to fetch SES cost data")
        return None


def get_app_email_stats() -> dict:
    """Query NotificationLog and EmailQueue for app-level statistics."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    today_count = NotificationLog.query.filter(
        NotificationLog.sent_at >= today_start
    ).count()
    week_count = NotificationLog.query.filter(
        NotificationLog.sent_at >= week_start
    ).count()
    month_count = NotificationLog.query.filter(
        NotificationLog.sent_at >= month_start
    ).count()
    total_count = NotificationLog.query.count()

    queue_pending = EmailQueue.query.filter_by(status="pending").count()
    queue_sent = EmailQueue.query.filter_by(status="sent").count()
    queue_failed = EmailQueue.query.filter_by(status="failed").count()

    limit = get_hourly_email_limit()
    sent_this_hour = get_emails_sent_this_hour()

    return {
        "today": today_count,
        "this_week": week_count,
        "this_month": month_count,
        "all_time": total_count,
        "queue_pending": queue_pending,
        "queue_sent": queue_sent,
        "queue_failed": queue_failed,
        "rate_limit": limit,
        "sent_this_hour": sent_this_hour,
        "rate_remaining": max(0, limit - sent_this_hour),
    }
