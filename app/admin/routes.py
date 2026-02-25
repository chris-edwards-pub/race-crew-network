import ipaddress
import json
import logging
import re
from datetime import date
from socket import getaddrinfo
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.admin import bp
from app.admin.ai_service import extract_regattas
from app.models import Regatta

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 15_000


def _require_admin():
    """Return a redirect response if the user is not an admin, else None."""
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))
    return None


def _find_duplicate(name: str, start_date) -> Regatta | None:
    """Find an existing regatta with the same name (case-insensitive) and start date."""
    return Regatta.query.filter(
        func.lower(Regatta.name) == name.lower(),
        Regatta.start_date == start_date,
    ).first()


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/loopback IP (SSRF guard)."""
    try:
        results = getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in results:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                return True
    except Exception:
        return True
    return False


def _fetch_url_content(url: str) -> str:
    """Fetch a URL and return plain text content."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("Invalid URL.")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are supported.")
    if _is_private_ip(parsed.hostname):
        raise ValueError("URLs pointing to private networks are not allowed.")

    resp = requests.get(url, timeout=15, headers={"User-Agent": "RaceCrewNetwork/1.0"})
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "html" in content_type:
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract JSON-LD structured data (schema.org Events)
        jsonld_events = _extract_jsonld_events(resp.text)

        # Remove scripts and styles for plain text extraction
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        # Prepend JSON-LD events so the AI sees structured data
        if jsonld_events:
            text = jsonld_events + "\n\n" + text
    else:
        text = resp.text

    return text[:MAX_CONTENT_LENGTH]


def _extract_jsonld_events(html: str) -> str:
    """Extract schema.org Event data from JSON-LD script tags."""
    blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    events = []
    for block in blocks:
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "Event":
                events.append(item)
            # Handle @graph wrapper
            if "@graph" in item:
                for node in item["@graph"]:
                    if node.get("@type") == "Event":
                        events.append(node)

    if not events:
        return ""

    lines = ["Structured event data found on page:"]
    for ev in events:
        loc = ev.get("location", {})
        loc_name = loc.get("name", "") if isinstance(loc, dict) else ""
        lines.append(
            f"- {ev.get('name', 'Unknown')}"
            f" | {ev.get('startDate', '')}"
            f" - {ev.get('endDate', '')}"
            f" | {loc_name}"
        )
    return "\n".join(lines)


@bp.route("/admin/import-schedule", methods=["GET", "POST"])
@login_required
def import_schedule():
    denied = _require_admin()
    if denied:
        return denied

    current_year = date.today().year
    years = list(range(current_year, current_year + 3))

    if request.method == "GET":
        return render_template(
            "admin/import_schedule.html",
            years=years,
            selected_year=current_year,
            regattas=None,
        )

    # POST — extract regattas from input
    schedule_text = request.form.get("schedule_text", "").strip()
    schedule_url = request.form.get("schedule_url", "").strip()
    year = int(request.form.get("year", current_year))

    if not schedule_text and not schedule_url:
        flash("Provide either schedule text or a URL.", "error")
        return render_template(
            "admin/import_schedule.html",
            years=years,
            selected_year=year,
            regattas=None,
        )

    # Get content from URL if provided
    content = schedule_text
    if schedule_url:
        try:
            content = _fetch_url_content(schedule_url)
        except (ValueError, requests.RequestException) as e:
            flash(f"Could not fetch URL: {e}", "error")
            return render_template(
                "admin/import_schedule.html",
                years=years,
                selected_year=year,
                regattas=None,
            )

    if not content:
        flash("No content to process.", "error")
        return render_template(
            "admin/import_schedule.html",
            years=years,
            selected_year=year,
            regattas=None,
        )

    # Send to Claude API
    try:
        regattas = extract_regattas(content, year)
    except (ValueError, ConnectionError) as e:
        flash(str(e), "error")
        return render_template(
            "admin/import_schedule.html",
            years=years,
            selected_year=year,
            regattas=None,
        )

    # Filter out past events
    today = date.today().isoformat()
    past_count = len(regattas)
    regattas = [r for r in regattas if (r.get("start_date") or "") >= today]
    past_count -= len(regattas)

    if not regattas:
        msg = "No upcoming regattas found in the provided content."
        if past_count:
            msg += f" ({past_count} past event(s) excluded.)"
        flash(msg, "warning")

    # Check for duplicates against existing regattas
    for r in regattas:
        start = r.get("start_date")
        name = r.get("name")
        if name and start:
            existing = _find_duplicate(name, date.fromisoformat(start))
            if existing:
                r["duplicate_of"] = {
                    "id": existing.id,
                    "name": existing.name,
                    "location": existing.location,
                    "start_date": existing.start_date.isoformat(),
                }

    return render_template(
        "admin/import_schedule.html",
        years=years,
        selected_year=year,
        regattas=regattas,
    )


@bp.route("/admin/import-schedule/confirm", methods=["POST"])
@login_required
def import_schedule_confirm():
    denied = _require_admin()
    if denied:
        return denied

    selected = request.form.getlist("selected")
    if not selected:
        flash("No regattas selected for import.", "warning")
        return redirect(url_for("admin.import_schedule"))

    created = 0
    skipped = 0

    for idx in selected:
        name = request.form.get(f"name_{idx}", "").strip()
        location = request.form.get(f"location_{idx}", "").strip()
        location_url = request.form.get(f"location_url_{idx}", "").strip()
        start_date_str = request.form.get(f"start_date_{idx}", "").strip()
        end_date_str = request.form.get(f"end_date_{idx}", "").strip()
        notes = request.form.get(f"notes_{idx}", "").strip()

        if not name or not start_date_str:
            skipped += 1
            continue

        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str) if end_date_str else None
        except ValueError:
            skipped += 1
            continue

        if end_date and end_date < start_date:
            skipped += 1
            continue

        # Duplicate check: case-insensitive name + start_date
        existing = _find_duplicate(name, start_date)
        if existing:
            skipped += 1
            continue

        # Auto-generate Google Maps link if no location_url
        if not location_url and location:
            location_url = f"https://www.google.com/maps/search/{quote_plus(location)}"

        regatta = Regatta(
            name=name,
            location=location or "TBD",
            location_url=location_url or None,
            start_date=start_date,
            end_date=end_date,
            notes=notes or None,
            created_by=current_user.id,
        )
        db.session.add(regatta)
        created += 1

    db.session.commit()

    if created:
        flash(f"Successfully imported {created} regatta(s).", "success")
    if skipped:
        flash(f"Skipped {skipped} regatta(s) (invalid or duplicate).", "warning")

    return redirect(url_for("regattas.index"))
