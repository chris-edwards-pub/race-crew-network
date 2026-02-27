import secrets
from datetime import timedelta

from flask import Response, flash, redirect, url_for
from flask_login import current_user, login_required
from icalendar import Calendar, Event
from markupsafe import Markup

from app import db
from app.calendar import bp
from app.models import RSVP, Regatta, User


@bp.route("/calendar/subscribe")
@login_required
def subscribe():
    """Generate or show the user's personal iCal subscription URL."""
    if not current_user.calendar_token:
        current_user.calendar_token = secrets.token_urlsafe(32)
        db.session.commit()

    feed_url = url_for(
        "calendar.ical_feed", token=current_user.calendar_token, _external=True
    )
    flash(
        Markup(
            f'Subscribe to this URL in your calendar app: <a href="{feed_url}" class="alert-link">{feed_url}</a>'
        ),
        "success",
    )
    return redirect(url_for("regattas.index"))


@bp.route("/calendar/<token>.ics")
def ical_feed(token: str):
    """Public iCal feed authenticated by secret token."""
    user = User.query.filter_by(calendar_token=token).first_or_404()

    cal = Calendar()
    cal.add("prodid", "-//Race Crew Network//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "Race Crew Network")
    cal.add("method", "PUBLISH")

    regattas = Regatta.query.order_by(Regatta.start_date).all()

    for regatta in regattas:
        event = Event()
        event.add("uid", f"regatta-{regatta.id}@racecrew.net")
        if regatta.boat_class and regatta.boat_class != "TBD":
            event.add("summary", f"{regatta.boat_class} — {regatta.name}")
        else:
            event.add("summary", regatta.name)
        event.add("dtstart", regatta.start_date)
        # End date is exclusive in iCal, so add 1 day
        end = (regatta.end_date or regatta.start_date) + timedelta(days=1)
        event.add("dtend", end)
        event.add("location", regatta.location)

        if regatta.location_url:
            event.add("url", regatta.location_url)

        # Build description with crew RSVP status
        lines = []
        if regatta.notes:
            lines.append(regatta.notes)

        rsvps = regatta.rsvps.all()
        if rsvps:
            status_map = {"yes": "Yes", "no": "No", "maybe": "Maybe"}
            crew_lines = [
                f"  {r.user.initials}: {status_map.get(r.status, r.status)}"
                for r in rsvps
            ]
            lines.append("Crew:\n" + "\n".join(crew_lines))

        # Show user's own RSVP status
        my_rsvp = RSVP.query.filter_by(regatta_id=regatta.id, user_id=user.id).first()
        if my_rsvp:
            lines.append(f"Your RSVP: {my_rsvp.status.capitalize()}")

        if lines:
            event.add("description", "\n\n".join(lines))

        cal.add_component(event)

    response = Response(cal.to_ical(), mimetype="text/calendar")
    response.headers["Content-Disposition"] = (
        "attachment; filename=race-crew-network.ics"
    )
    return response
