"""AI usage statistics helpers — cost tracking, budget monitoring, and alerts."""

import logging
from datetime import datetime, timezone

from sqlalchemy import func

from app import db
from app.models import AIUsageLog, SiteSetting

logger = logging.getLogger(__name__)

DEFAULT_MONTHLY_COST_LIMIT = 20.00


def get_monthly_cost_limit() -> float:
    """Read the monthly AI cost limit from SiteSetting (default $20)."""
    setting = SiteSetting.query.filter_by(key="ai_monthly_cost_limit").first()
    if setting and setting.value:
        try:
            return float(setting.value)
        except (ValueError, TypeError):
            pass
    return DEFAULT_MONTHLY_COST_LIMIT


def get_ai_usage_stats() -> dict:
    """Query AIUsageLog for usage statistics."""
    # Use naive UTC datetimes for MySQL DATETIME column compatibility
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    # Last month range
    if month_start.month == 1:
        last_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        last_month_start = month_start.replace(month=month_start.month - 1)
    last_month_end = month_start

    # Cost aggregations
    today_cost = (
        db.session.query(func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0))
        .filter(AIUsageLog.created_at >= today_start)
        .scalar()
    )
    month_cost = (
        db.session.query(func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0))
        .filter(AIUsageLog.created_at >= month_start)
        .scalar()
    )
    last_month_cost = (
        db.session.query(func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0))
        .filter(
            AIUsageLog.created_at >= last_month_start,
            AIUsageLog.created_at < last_month_end,
        )
        .scalar()
    )
    all_time_cost = db.session.query(
        func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0)
    ).scalar()

    # Call counts
    today_calls = AIUsageLog.query.filter(AIUsageLog.created_at >= today_start).count()
    month_calls = AIUsageLog.query.filter(AIUsageLog.created_at >= month_start).count()
    all_time_calls = AIUsageLog.query.count()

    # Token counts (this month)
    month_input_tokens = (
        db.session.query(func.coalesce(func.sum(AIUsageLog.input_tokens), 0))
        .filter(AIUsageLog.created_at >= month_start)
        .scalar()
    )
    month_output_tokens = (
        db.session.query(func.coalesce(func.sum(AIUsageLog.output_tokens), 0))
        .filter(AIUsageLog.created_at >= month_start)
        .scalar()
    )

    # Per-function breakdown (this month)
    function_breakdown = (
        db.session.query(
            AIUsageLog.function_name,
            func.count(AIUsageLog.id),
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0),
        )
        .filter(AIUsageLog.created_at >= month_start)
        .group_by(AIUsageLog.function_name)
        .all()
    )
    by_function = [
        {"name": name, "calls": calls, "cost": cost}
        for name, calls, cost in function_breakdown
    ]

    # Budget percentage
    limit = get_monthly_cost_limit()
    budget_pct = (month_cost / limit * 100) if limit > 0 else 0.0

    return {
        "today_cost": float(today_cost),
        "month_cost": float(month_cost),
        "last_month_cost": float(last_month_cost),
        "all_time_cost": float(all_time_cost),
        "today_calls": today_calls,
        "month_calls": month_calls,
        "all_time_calls": all_time_calls,
        "month_input_tokens": int(month_input_tokens),
        "month_output_tokens": int(month_output_tokens),
        "by_function": by_function,
        "budget_limit": limit,
        "budget_pct": budget_pct,
    }


def check_cost_threshold() -> bool:
    """Return True if monthly cost >= 80% of limit AND alert not yet sent this month."""
    # Use naive UTC datetimes for MySQL DATETIME column compatibility
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).replace(
        tzinfo=None
    )

    month_cost = (
        db.session.query(func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0))
        .filter(AIUsageLog.created_at >= month_start)
        .scalar()
    )

    limit = get_monthly_cost_limit()
    if limit <= 0 or float(month_cost) < limit * 0.8:
        return False

    # Check if alert already sent this month
    current_month = now.strftime("%Y-%m")
    setting = SiteSetting.query.filter_by(key="ai_cost_alert_sent_month").first()
    if setting and setting.value == current_month:
        return False

    return True
