"""Notification service for crew notifications and RSVP alerts."""

import logging
from datetime import date, datetime, timedelta, timezone

from flask import render_template, url_for

from app import db
from app.admin.email_service import is_email_configured, send_email
from app.models import RSVP, NotificationLog, Regatta, SiteSetting, User

logger = logging.getLogger(__name__)


def get_eligible_crew(skipper: User) -> list[dict]:
    """Return crew members with eligibility info for the notify modal.

    Each entry: {"user": User, "eligible": bool, "reason": str | None}
    """
    result = []
    for crew in skipper.crew_members.all():
        if crew.invite_token is not None:
            result.append(
                {"user": crew, "eligible": False, "reason": "Registration pending"}
            )
        elif not crew.email_opt_in:
            result.append(
                {"user": crew, "eligible": False, "reason": "Opted out of emails"}
            )
        else:
            result.append({"user": crew, "eligible": True, "reason": None})
    return result


def notify_crew(
    regattas: list[Regatta],
    crew_members: list[User],
    message: str | None,
    skipper: User,
) -> int:
    """Send bulk notification email to selected crew about selected regattas.

    Returns the number of crew members successfully notified.
    """
    if not is_email_configured():
        logger.info("Email not configured — skipping notify_crew")
        return 0

    if not regattas or not crew_members:
        return 0

    schedule_url = url_for("regattas.index", _external=True)
    profile_url = url_for("auth.profile", _external=True)
    sent_count = 0

    for crew in crew_members:
        # Skip ineligible crew
        if crew.invite_token is not None or not crew.email_opt_in:
            continue

        subject = f"Race Schedule Update from {skipper.display_name}"

        body_html = render_template(
            "email/notify_crew.html",
            crew_name=crew.display_name,
            skipper_name=skipper.display_name,
            regattas=regattas,
            custom_message=message,
            schedule_url=schedule_url,
            profile_url=profile_url,
        )
        body_text = render_template(
            "email/notify_crew.txt",
            crew_name=crew.display_name,
            skipper_name=skipper.display_name,
            regattas=regattas,
            custom_message=message,
            schedule_url=schedule_url,
            profile_url=profile_url,
        )

        try:
            send_email(
                to=crew.email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            # Log one row per (crew_member, regatta) pair
            for regatta in regattas:
                db.session.add(
                    NotificationLog(
                        notification_type="notify_crew",
                        regatta_id=regatta.id,
                        user_id=crew.id,
                        trigger_date=date.today(),
                    )
                )
            sent_count += 1
        except Exception:
            logger.exception("Failed to send crew notification to %s", crew.email)

    if sent_count:
        db.session.commit()

    return sent_count


def notify_rsvp_to_skipper(rsvp) -> None:
    """Send RSVP notification to the skipper who created the regatta."""
    if not is_email_configured():
        return

    skipper = rsvp.regatta.creator
    if not skipper:
        return

    if not skipper.email_opt_in:
        return

    prefs = skipper.notification_preferences
    if not prefs.get("rsvp_notification", True):
        return

    # Phase 2: digest mode
    if prefs.get("rsvp_delivery") == "digest":
        return

    schedule_url = url_for("regattas.index", _external=True)
    profile_url = url_for("auth.profile", _external=True)

    subject = f"RSVP Update: {rsvp.user.display_name} — {rsvp.regatta.name}"

    body_html = render_template(
        "email/rsvp_notification.html",
        crew_member=rsvp.user.display_name,
        status=rsvp.status,
        regatta_name=rsvp.regatta.name,
        regatta_date=rsvp.regatta.start_date,
        regatta_end_date=rsvp.regatta.end_date,
        regatta_location=rsvp.regatta.location,
        schedule_url=schedule_url,
        profile_url=profile_url,
    )
    body_text = render_template(
        "email/rsvp_notification.txt",
        crew_member=rsvp.user.display_name,
        status=rsvp.status,
        regatta_name=rsvp.regatta.name,
        regatta_date=rsvp.regatta.start_date,
        regatta_end_date=rsvp.regatta.end_date,
        regatta_location=rsvp.regatta.location,
        schedule_url=schedule_url,
        profile_url=profile_url,
    )

    send_email(
        to=skipper.email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )

    db.session.add(
        NotificationLog(
            notification_type="rsvp_notification",
            regatta_id=rsvp.regatta.id,
            user_id=skipper.id,
            trigger_date=date.today(),
        )
    )
    db.session.commit()


def notify_crew_joined(crew_member: User, skipper: User) -> None:
    """Notify skipper that a crew member has completed registration."""
    if not is_email_configured():
        return

    if not skipper.email_opt_in:
        return

    schedule_url = url_for("regattas.index", _external=True)
    crew_url = url_for("auth.view_profile", user_id=crew_member.id, _external=True)

    subject = f"{crew_member.display_name} has joined your crew!"

    body_html = (
        f"<h2>New Crew Member</h2>"
        f"<p><strong>{crew_member.display_name}</strong> has accepted your "
        f"invitation and joined your crew on Race Crew Network.</p>"
        f'<p><a href="{crew_url}">View their profile</a> | '
        f'<a href="{schedule_url}">View your schedule</a></p>'
    )
    body_text = (
        f"{crew_member.display_name} has accepted your invitation and joined "
        f"your crew on Race Crew Network.\n\n"
        f"View their profile: {crew_url}\n"
        f"View your schedule: {schedule_url}\n"
    )

    send_email(
        to=skipper.email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )

    db.session.add(
        NotificationLog(
            notification_type="crew_joined",
            user_id=skipper.id,
            trigger_date=date.today(),
        )
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Phase 2: Scheduled reminders
# ---------------------------------------------------------------------------


def _was_crew_notified(user_id: int, regatta_id: int) -> bool:
    """Check if a notify_crew log exists for this user+regatta pair."""
    return (
        NotificationLog.query.filter_by(
            notification_type="notify_crew",
            user_id=user_id,
            regatta_id=regatta_id,
        ).first()
        is not None
    )


def _get_setting(key: str, default: str = "") -> str:
    """Load a SiteSetting value, returning default if not found."""
    setting = SiteSetting.query.filter_by(key=key).first()
    return setting.value if setting and setting.value else default


def send_rsvp_digests() -> int:
    """Send daily RSVP digest to skippers who chose digest delivery.

    Returns the number of digest emails sent.
    """
    if not is_email_configured():
        return 0

    today = date.today()
    sent_count = 0

    # Find skippers with digest mode enabled
    skippers = User.query.filter_by(is_skipper=True).all()

    for skipper in skippers:
        if not skipper.email_opt_in:
            continue

        prefs = skipper.notification_preferences
        if not prefs.get("rsvp_notification", True):
            continue
        if prefs.get("rsvp_delivery") != "digest":
            continue

        # Find the last digest sent to this skipper
        last_digest = (
            NotificationLog.query.filter_by(
                notification_type="rsvp_digest",
                user_id=skipper.id,
            )
            .order_by(NotificationLog.sent_at.desc())
            .first()
        )
        since = (
            last_digest.sent_at
            if last_digest
            else (datetime.now(timezone.utc) - timedelta(days=1))
        )

        # Find RSVPs on this skipper's regattas since the cutoff
        skipper_regatta_ids = [
            r.id for r in Regatta.query.filter_by(created_by=skipper.id).all()
        ]
        if not skipper_regatta_ids:
            continue

        recent_rsvps = RSVP.query.filter(
            RSVP.regatta_id.in_(skipper_regatta_ids),
            RSVP.updated_at > since,
        ).all()

        if not recent_rsvps:
            continue

        # Group by regatta
        rsvps_by_regatta: dict[int, list] = {}
        for rsvp in recent_rsvps:
            rsvps_by_regatta.setdefault(rsvp.regatta_id, []).append(rsvp)

        # Build grouped data for template
        regatta_summaries = []
        for regatta_id, rsvps in rsvps_by_regatta.items():
            regatta = db.session.get(Regatta, regatta_id)
            if regatta:
                regatta_summaries.append(
                    {
                        "regatta": regatta,
                        "rsvps": rsvps,
                    }
                )

        if not regatta_summaries:
            continue

        count = sum(len(s["rsvps"]) for s in regatta_summaries)
        schedule_url = url_for("regattas.index", _external=True)
        profile_url = url_for("auth.profile", _external=True)
        subject = f"Daily RSVP Summary — {count} update(s)"

        body_html = render_template(
            "email/rsvp_digest.html",
            skipper_name=skipper.display_name,
            regatta_summaries=regatta_summaries,
            schedule_url=schedule_url,
            profile_url=profile_url,
        )
        body_text = render_template(
            "email/rsvp_digest.txt",
            skipper_name=skipper.display_name,
            regatta_summaries=regatta_summaries,
            schedule_url=schedule_url,
            profile_url=profile_url,
        )

        try:
            send_email(
                to=skipper.email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            db.session.add(
                NotificationLog(
                    notification_type="rsvp_digest",
                    user_id=skipper.id,
                    trigger_date=today,
                )
            )
            sent_count += 1
        except Exception:
            logger.exception("Failed to send RSVP digest to %s", skipper.email)

    if sent_count:
        db.session.commit()

    return sent_count


def send_crew_digests() -> int:
    """Send daily digest to crew members who chose digest delivery.

    Batches RSVP reminders and coming-up reminders into one email.
    Returns the number of digest emails sent.
    """
    if not is_email_configured():
        return 0

    today = date.today()
    rsvp_days = int(_get_setting("reminder_rsvp_days_before", "14"))
    upcoming_days = int(_get_setting("reminder_upcoming_days_before", "3"))
    rsvp_target = today + timedelta(days=rsvp_days)
    upcoming_target = today + timedelta(days=upcoming_days)

    sent_count = 0

    # Find crew with digest mode
    all_users = User.query.filter(
        User.email_opt_in.is_(True),
        User.invite_token.is_(None),
    ).all()

    for user in all_users:
        prefs = user.notification_preferences
        if prefs.get("rsvp_delivery") != "digest":
            continue

        rsvp_needed = []
        coming_up = []

        # RSVP reminders: regattas starting on rsvp_target date
        rsvp_regattas = Regatta.query.filter(Regatta.start_date == rsvp_target).all()
        for regatta in rsvp_regattas:
            if not _was_crew_notified(user.id, regatta.id):
                continue
            # Check not already RSVPed
            existing_rsvp = RSVP.query.filter_by(
                regatta_id=regatta.id, user_id=user.id
            ).first()
            if existing_rsvp:
                continue
            # Check not already reminded
            already = NotificationLog.query.filter_by(
                notification_type="rsvp_reminder",
                regatta_id=regatta.id,
                user_id=user.id,
            ).first()
            if already:
                continue
            rsvp_needed.append(regatta)

        # Coming up reminders: regattas starting on upcoming_target date
        upcoming_regattas = Regatta.query.filter(
            Regatta.start_date == upcoming_target
        ).all()
        for regatta in upcoming_regattas:
            if not _was_crew_notified(user.id, regatta.id):
                continue
            existing_rsvp = RSVP.query.filter_by(
                regatta_id=regatta.id, user_id=user.id
            ).first()
            if not existing_rsvp or existing_rsvp.status not in ("yes", "maybe"):
                continue
            already = NotificationLog.query.filter_by(
                notification_type="coming_up_reminder",
                regatta_id=regatta.id,
                user_id=user.id,
            ).first()
            if already:
                continue
            coming_up.append(regatta)

        if not rsvp_needed and not coming_up:
            continue

        schedule_url = url_for("regattas.index", _external=True)
        profile_url = url_for("auth.profile", _external=True)
        subject = "Race Crew Network — Daily Update"

        body_html = render_template(
            "email/crew_digest.html",
            crew_name=user.display_name,
            rsvp_needed=rsvp_needed,
            coming_up=coming_up,
            schedule_url=schedule_url,
            profile_url=profile_url,
        )
        body_text = render_template(
            "email/crew_digest.txt",
            crew_name=user.display_name,
            rsvp_needed=rsvp_needed,
            coming_up=coming_up,
            schedule_url=schedule_url,
            profile_url=profile_url,
        )

        try:
            send_email(
                to=user.email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            # Log entries for dedup
            for regatta in rsvp_needed:
                db.session.add(
                    NotificationLog(
                        notification_type="rsvp_reminder",
                        regatta_id=regatta.id,
                        user_id=user.id,
                        trigger_date=today,
                    )
                )
            for regatta in coming_up:
                db.session.add(
                    NotificationLog(
                        notification_type="coming_up_reminder",
                        regatta_id=regatta.id,
                        user_id=user.id,
                        trigger_date=today,
                    )
                )
            sent_count += 1
        except Exception:
            logger.exception("Failed to send crew digest to %s", user.email)

    if sent_count:
        db.session.commit()

    return sent_count


def send_rsvp_reminders(days_before: int | None = None) -> int:
    """Send RSVP reminder to crew who haven't RSVPed (14 days before).

    Only sends to crew who were previously notified about the regatta.
    Skips crew with digest delivery mode (they get it in crew digest).
    Returns the number of reminder emails sent.
    """
    if not is_email_configured():
        return 0

    if days_before is None:
        days_before = int(_get_setting("reminder_rsvp_days_before", "14"))

    today = date.today()
    target_date = today + timedelta(days=days_before)
    regattas = Regatta.query.filter(Regatta.start_date == target_date).all()

    if not regattas:
        return 0

    sent_count = 0

    for regatta in regattas:
        # Get crew who were notified about this regatta
        notified_logs = NotificationLog.query.filter_by(
            notification_type="notify_crew",
            regatta_id=regatta.id,
        ).all()
        notified_user_ids = {log.user_id for log in notified_logs}

        # Already reminded
        reminded_logs = NotificationLog.query.filter_by(
            notification_type="rsvp_reminder",
            regatta_id=regatta.id,
        ).all()
        reminded_user_ids = {log.user_id for log in reminded_logs}

        # Already RSVPed
        rsvped = RSVP.query.filter_by(regatta_id=regatta.id).all()
        rsvped_user_ids = {r.user_id for r in rsvped}

        eligible_ids = notified_user_ids - rsvped_user_ids - reminded_user_ids

        for user_id in eligible_ids:
            user = db.session.get(User, user_id)
            if not user or not user.email_opt_in or user.invite_token is not None:
                continue

            # Skip digest-mode crew (they get it in crew digest)
            prefs = user.notification_preferences
            if prefs.get("rsvp_delivery") == "digest":
                continue

            schedule_url = url_for("regattas.index", _external=True)
            profile_url = url_for("auth.profile", _external=True)
            skipper = regatta.creator

            subject = (
                f"RSVP Reminder: {regatta.name} — "
                f"{regatta.start_date.strftime('%b %d, %Y')}"
            )

            body_html = render_template(
                "email/rsvp_reminder.html",
                crew_name=user.display_name,
                regatta=regatta,
                skipper_name=skipper.display_name if skipper else "Your skipper",
                schedule_url=schedule_url,
                profile_url=profile_url,
            )
            body_text = render_template(
                "email/rsvp_reminder.txt",
                crew_name=user.display_name,
                regatta=regatta,
                skipper_name=skipper.display_name if skipper else "Your skipper",
                schedule_url=schedule_url,
                profile_url=profile_url,
            )

            try:
                send_email(
                    to=user.email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                )
                db.session.add(
                    NotificationLog(
                        notification_type="rsvp_reminder",
                        regatta_id=regatta.id,
                        user_id=user.id,
                        trigger_date=today,
                    )
                )
                sent_count += 1
            except Exception:
                logger.exception("Failed to send RSVP reminder to %s", user.email)

    if sent_count:
        db.session.commit()

    return sent_count


def send_coming_up_reminders(days_before: int | None = None) -> int:
    """Send 'coming up' reminder to crew who RSVPed yes/maybe (3 days before).

    Only sends to crew who were previously notified about the regatta.
    Skips crew with digest delivery mode (they get it in crew digest).
    Returns the number of reminder emails sent.
    """
    if not is_email_configured():
        return 0

    if days_before is None:
        days_before = int(_get_setting("reminder_upcoming_days_before", "3"))

    today = date.today()
    target_date = today + timedelta(days=days_before)
    regattas = Regatta.query.filter(Regatta.start_date == target_date).all()

    if not regattas:
        return 0

    sent_count = 0

    for regatta in regattas:
        # Get crew who were notified
        notified_logs = NotificationLog.query.filter_by(
            notification_type="notify_crew",
            regatta_id=regatta.id,
        ).all()
        notified_user_ids = {log.user_id for log in notified_logs}

        # Already reminded
        reminded_logs = NotificationLog.query.filter_by(
            notification_type="coming_up_reminder",
            regatta_id=regatta.id,
        ).all()
        reminded_user_ids = {log.user_id for log in reminded_logs}

        # RSVPed yes or maybe
        yes_maybe = RSVP.query.filter(
            RSVP.regatta_id == regatta.id,
            RSVP.status.in_(["yes", "maybe"]),
        ).all()
        yes_maybe_user_ids = {r.user_id for r in yes_maybe}

        eligible_ids = (notified_user_ids & yes_maybe_user_ids) - reminded_user_ids

        for user_id in eligible_ids:
            user = db.session.get(User, user_id)
            if not user or not user.email_opt_in:
                continue

            # Skip digest-mode crew
            prefs = user.notification_preferences
            if prefs.get("rsvp_delivery") == "digest":
                continue

            schedule_url = url_for("regattas.index", _external=True)
            profile_url = url_for("auth.profile", _external=True)

            subject = (
                f"Coming Up: {regatta.name} — "
                f"{regatta.start_date.strftime('%b %d, %Y')}"
            )

            body_html = render_template(
                "email/coming_up_reminder.html",
                crew_name=user.display_name,
                regatta=regatta,
                days=days_before,
                schedule_url=schedule_url,
                profile_url=profile_url,
            )
            body_text = render_template(
                "email/coming_up_reminder.txt",
                crew_name=user.display_name,
                regatta=regatta,
                days=days_before,
                schedule_url=schedule_url,
                profile_url=profile_url,
            )

            try:
                send_email(
                    to=user.email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                )
                db.session.add(
                    NotificationLog(
                        notification_type="coming_up_reminder",
                        regatta_id=regatta.id,
                        user_id=user.id,
                        trigger_date=today,
                    )
                )
                sent_count += 1
            except Exception:
                logger.exception("Failed to send coming-up reminder to %s", user.email)

    if sent_count:
        db.session.commit()

    return sent_count


def send_all_reminders() -> dict:
    """Run all scheduled reminder functions. Returns summary dict."""
    digests = send_rsvp_digests()
    crew_digests = send_crew_digests()
    rsvp_reminders = send_rsvp_reminders()
    coming_up_reminders = send_coming_up_reminders()
    return {
        "digests": digests,
        "crew_digests": crew_digests,
        "rsvp_reminders": rsvp_reminders,
        "coming_up_reminders": coming_up_reminders,
    }


# ---------------------------------------------------------------------------
# Digest flush: send pending items when switching from digest → instant
# ---------------------------------------------------------------------------


def flush_skipper_digest(skipper: User) -> bool:
    """Send a final catch-up RSVP digest for a skipper switching to instant.

    Covers RSVPs that arrived while in digest mode but before a digest was sent.
    Returns True if an email was sent.
    """
    if not is_email_configured():
        return False

    if not skipper.email_opt_in:
        return False

    prefs = skipper.notification_preferences
    if not prefs.get("rsvp_notification", True):
        return False

    # Find RSVPs since last digest
    last_digest = (
        NotificationLog.query.filter_by(
            notification_type="rsvp_digest",
            user_id=skipper.id,
        )
        .order_by(NotificationLog.sent_at.desc())
        .first()
    )
    since = (
        last_digest.sent_at
        if last_digest
        else (datetime.now(timezone.utc) - timedelta(days=1))
    )

    skipper_regatta_ids = [
        r.id for r in Regatta.query.filter_by(created_by=skipper.id).all()
    ]
    if not skipper_regatta_ids:
        return False

    recent_rsvps = RSVP.query.filter(
        RSVP.regatta_id.in_(skipper_regatta_ids),
        RSVP.updated_at > since,
    ).all()

    if not recent_rsvps:
        return False

    # Group by regatta
    rsvps_by_regatta: dict[int, list] = {}
    for rsvp in recent_rsvps:
        rsvps_by_regatta.setdefault(rsvp.regatta_id, []).append(rsvp)

    regatta_summaries = []
    for regatta_id, rsvps in rsvps_by_regatta.items():
        regatta = db.session.get(Regatta, regatta_id)
        if regatta:
            regatta_summaries.append({"regatta": regatta, "rsvps": rsvps})

    if not regatta_summaries:
        return False

    count = sum(len(s["rsvps"]) for s in regatta_summaries)
    schedule_url = url_for("regattas.index", _external=True)
    profile_url = url_for("auth.profile", _external=True)
    subject = f"Daily RSVP Summary — {count} update(s)"

    body_html = render_template(
        "email/rsvp_digest.html",
        skipper_name=skipper.display_name,
        regatta_summaries=regatta_summaries,
        schedule_url=schedule_url,
        profile_url=profile_url,
    )
    body_text = render_template(
        "email/rsvp_digest.txt",
        skipper_name=skipper.display_name,
        regatta_summaries=regatta_summaries,
        schedule_url=schedule_url,
        profile_url=profile_url,
    )

    try:
        send_email(
            to=skipper.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
        db.session.add(
            NotificationLog(
                notification_type="rsvp_digest",
                user_id=skipper.id,
                trigger_date=date.today(),
            )
        )
        db.session.commit()
        return True
    except Exception:
        logger.exception("Failed to send flush digest to %s", skipper.email)
        return False


def flush_crew_digest(user: User) -> bool:
    """Send a final catch-up crew digest when switching to instant.

    Sends any pending RSVP reminders and coming-up reminders that would
    have been included in the next crew digest.
    Returns True if an email was sent.
    """
    if not is_email_configured():
        return False

    if not user.email_opt_in:
        return False

    today = date.today()
    rsvp_days = int(_get_setting("reminder_rsvp_days_before", "14"))
    upcoming_days = int(_get_setting("reminder_upcoming_days_before", "3"))
    rsvp_target = today + timedelta(days=rsvp_days)
    upcoming_target = today + timedelta(days=upcoming_days)

    rsvp_needed = []
    coming_up = []

    # RSVP reminders: regattas starting on rsvp_target date
    for regatta in Regatta.query.filter(Regatta.start_date == rsvp_target).all():
        if not _was_crew_notified(user.id, regatta.id):
            continue
        if RSVP.query.filter_by(regatta_id=regatta.id, user_id=user.id).first():
            continue
        if NotificationLog.query.filter_by(
            notification_type="rsvp_reminder",
            regatta_id=regatta.id,
            user_id=user.id,
        ).first():
            continue
        rsvp_needed.append(regatta)

    # Coming up reminders: regattas starting on upcoming_target date
    for regatta in Regatta.query.filter(Regatta.start_date == upcoming_target).all():
        if not _was_crew_notified(user.id, regatta.id):
            continue
        existing_rsvp = RSVP.query.filter_by(
            regatta_id=regatta.id, user_id=user.id
        ).first()
        if not existing_rsvp or existing_rsvp.status not in ("yes", "maybe"):
            continue
        if NotificationLog.query.filter_by(
            notification_type="coming_up_reminder",
            regatta_id=regatta.id,
            user_id=user.id,
        ).first():
            continue
        coming_up.append(regatta)

    if not rsvp_needed and not coming_up:
        return False

    schedule_url = url_for("regattas.index", _external=True)
    profile_url = url_for("auth.profile", _external=True)
    subject = "Race Crew Network — Daily Update"

    body_html = render_template(
        "email/crew_digest.html",
        crew_name=user.display_name,
        rsvp_needed=rsvp_needed,
        coming_up=coming_up,
        schedule_url=schedule_url,
        profile_url=profile_url,
    )
    body_text = render_template(
        "email/crew_digest.txt",
        crew_name=user.display_name,
        rsvp_needed=rsvp_needed,
        coming_up=coming_up,
        schedule_url=schedule_url,
        profile_url=profile_url,
    )

    try:
        send_email(
            to=user.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
        for regatta in rsvp_needed:
            db.session.add(
                NotificationLog(
                    notification_type="rsvp_reminder",
                    regatta_id=regatta.id,
                    user_id=user.id,
                    trigger_date=today,
                )
            )
        for regatta in coming_up:
            db.session.add(
                NotificationLog(
                    notification_type="coming_up_reminder",
                    regatta_id=regatta.id,
                    user_id=user.id,
                    trigger_date=today,
                )
            )
        db.session.commit()
        return True
    except Exception:
        logger.exception("Failed to send flush crew digest to %s", user.email)
        return False
