import hashlib
import ipaddress
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from socket import getaddrinfo
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from flask import (Response, flash, jsonify, redirect, render_template,
                   request, stream_with_context, url_for)
from flask_login import current_user, login_required

from app import csrf, db
from app.admin import bp
from app.admin.ai_service import (discover_documents, discover_documents_deep,
                                  extract_regattas)
from app.admin.email_service import (is_email_configured, load_email_settings,
                                     send_email)
from app.admin.file_utils import extract_text_from_file
from app.models import Document, ImportCache, Regatta, SiteSetting, TaskResult

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 20_000


def _store_task_result(task_id: str, result_type: str, data: dict) -> None:
    """Store task result in DB (replaces in-memory dict write)."""
    row = TaskResult(id=task_id, result_type=result_type, data_json=json.dumps(data))
    db.session.add(row)
    db.session.commit()


def _pop_task_result(task_id: str, result_type: str) -> dict | None:
    """Fetch and delete task result from DB (replaces dict.pop)."""
    row = TaskResult.query.filter_by(id=task_id, result_type=result_type).first()
    if not row:
        return None
    data = json.loads(row.data_json)
    db.session.delete(row)
    db.session.commit()
    return data


def _cleanup_stale_task_results() -> None:
    """Delete task results older than 1 hour."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    TaskResult.query.filter(TaskResult.created_at < cutoff).delete()
    db.session.commit()


def _require_admin():
    """Return a redirect response if the user is not an admin, else None."""
    if not current_user.is_admin:
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))
    return None


def _require_skipper_or_admin():
    """Return a redirect response if the user is not a skipper or admin."""
    if not (current_user.is_admin or current_user.is_skipper):
        flash("Access denied.", "error")
        return redirect(url_for("regattas.index"))
    return None


def _normalize_regatta_name(name: str) -> str:
    """Strip 4-digit year prefixes from each segment of a regatta name.

    Handles compound names like "Bottoms Up Regatta/2025 Carolina Districts"
    by splitting on ``/``, stripping the year from each part, and rejoining.
    """
    parts = name.split("/")
    cleaned = [re.sub(r"^\d{4}\s*[-–—]?\s*", "", p).strip() for p in parts]
    return "/".join(cleaned)


def _find_duplicate(
    name: str, start_date, owner_id: int | None = None
) -> Regatta | None:
    """Find an existing regatta with the same name and start date.

    Compares with leading year prefixes stripped so that
    "2026 Orange Peel Regatta" matches "Orange Peel Regatta".
    When *owner_id* is given, only check that owner's regattas.
    """
    normalized = _normalize_regatta_name(name).lower()
    query = Regatta.query.filter(Regatta.start_date == start_date)
    if owner_id is not None:
        query = query.filter(Regatta.created_by == owner_id)
    candidates = query.all()
    for r in candidates:
        if _normalize_regatta_name(r.name).lower() == normalized:
            return r
    return None


def _cache_age_days(extracted_at: datetime) -> int:
    """Return the number of days since extraction, handling naive/aware datetimes."""
    now = datetime.now(timezone.utc)
    if extracted_at.tzinfo is None:
        extracted_at = extracted_at.replace(tzinfo=timezone.utc)
    return (now - extracted_at).days


def _upsert_import_cache(url: str, year: int, regattas: list[dict]) -> None:
    """Insert or update an ImportCache entry for the given URL."""
    cached = ImportCache.query.filter_by(url=url).first()
    now = datetime.now(timezone.utc)
    results_json = json.dumps(regattas)
    if cached:
        cached.year = year
        cached.results_json = results_json
        cached.regatta_count = len(regattas)
        cached.extracted_at = now
    else:
        cached = ImportCache(
            url=url,
            year=year,
            results_json=results_json,
            regatta_count=len(regattas),
            extracted_at=now,
        )
        db.session.add(cached)
    db.session.commit()


def _upsert_site_setting(key: str, value: str) -> None:
    """Insert or update a site setting key-value pair."""
    setting = SiteSetting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = SiteSetting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()


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


CLUBSPOT_PARSE_APP_ID = "myclubspot2017"
CLUBSPOT_PARSE_URL = "https://theclubspot.com/parse/classes/documents"

# Map clubspot document types to our doc_type codes
_CLUBSPOT_DOC_TYPES = {
    "nor": ("NOR", "Notice of Race"),
    "si": ("SI", "Sailing Instructions"),
}


def _fetch_clubspot_documents(regatta_id: str) -> list[dict]:
    """Query the clubspot Parse API for NOR/SI documents."""
    where = json.dumps(
        {
            "regattaObject": {
                "__type": "Pointer",
                "className": "regattas",
                "objectId": regatta_id,
            },
            "archived": False,
            "active": True,
        }
    )
    try:
        resp = requests.get(
            CLUBSPOT_PARSE_URL,
            params={"where": where},
            headers={
                "X-Parse-Application-Id": CLUBSPOT_PARSE_APP_ID,
                "User-Agent": "RaceCrewNetwork/1.0",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("Clubspot API request failed: %s", e)
        return []

    docs = []
    for item in data.get("results", []):
        doc_type_key = (item.get("type") or "").lower()
        url = item.get("URL", "")
        if doc_type_key in _CLUBSPOT_DOC_TYPES and url:
            code, label = _CLUBSPOT_DOC_TYPES[doc_type_key]
            docs.append({"doc_type": code, "url": url, "label": label})
    return docs


def _parse_clubspot_regatta_id(url: str) -> str | None:
    """Extract the regatta ID from a clubspot URL, or None."""
    parsed = urlparse(url)
    if "theclubspot.com" not in (parsed.hostname or ""):
        return None
    # URL pattern: /regatta/<id> or /regatta/<id>/...
    match = re.match(r"^/regatta/([A-Za-z0-9]+)", parsed.path)
    return match.group(1) if match else None


def _extract_data_attributes(soup: BeautifulSoup) -> str:
    """Extract JSON data from data-* attributes on key elements (body, main divs).

    Many JS frameworks (Vue, React) embed initial state as JSON in data
    attributes. This captures that data so the AI can see dates, names,
    etc. that would otherwise only appear after JavaScript execution.
    """
    results = []
    # Check body and top-level containers for data attributes with JSON
    candidates = [soup.body] if soup.body else []
    candidates.extend(soup.find_all("div", attrs={"data-regatta": True}))

    for tag in candidates:
        if tag is None:
            continue
        for attr_name, attr_value in tag.attrs.items():
            if not attr_name.startswith("data-"):
                continue
            # Only process attributes that look like JSON objects/arrays
            val = attr_value if isinstance(attr_value, str) else str(attr_value)
            val = val.strip()
            if not (val.startswith("{") or val.startswith("[")):
                continue
            try:
                data = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                continue
            # Flatten to a readable summary for the AI
            results.append(f"Embedded data ({attr_name}): {json.dumps(data)}")

    if not results:
        return ""
    return "Structured data from page attributes:\n" + "\n".join(results)


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

        # Extract JSON from data attributes (Vue/React hydration data)
        data_attr_text = _extract_data_attributes(soup)

        # Remove scripts and styles for plain text extraction
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Preserve link URLs so AI can see them in plain text
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Resolve relative URLs to absolute
            abs_url = urljoin(url, href)
            link_text = a_tag.get_text(strip=True)
            if link_text:
                a_tag.replace_with(f"{link_text} [{abs_url}]")
            else:
                a_tag.replace_with(f"[{abs_url}]")

        text = soup.get_text(separator="\n", strip=True)

        # Prepend structured data so the AI sees it
        prefix_parts = []
        if jsonld_events:
            prefix_parts.append(jsonld_events)
        if data_attr_text:
            prefix_parts.append(data_attr_text)
        if prefix_parts:
            text = "\n\n".join(prefix_parts) + "\n\n" + text
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
        loc_addr = ""
        if isinstance(loc, dict):
            loc_addr = loc.get("address", "")
            if isinstance(loc_addr, dict):
                loc_addr = loc_addr.get("streetAddress", "")

        parts = [
            f"- {ev.get('name', 'Unknown')}",
            f"  Dates: {ev.get('startDate', '')} - {ev.get('endDate', '')}",
            f"  Location: {loc_name}",
        ]
        if loc_addr:
            parts.append(f"  Address: {loc_addr}")

        organizer = ev.get("organizer", {})
        if isinstance(organizer, dict) and organizer.get("name"):
            parts.append(f"  Organizer: {organizer['name']}")

        offers = ev.get("offers", {})
        if isinstance(offers, dict) and offers.get("url"):
            parts.append(f"  URL: {offers['url']}")

        url = ev.get("url", "")
        if url and url != (offers.get("url") if isinstance(offers, dict) else ""):
            parts.append(f"  URL: {url}")

        desc = ev.get("description", "")
        if desc:
            # Clean up HTML entities and excessive whitespace
            desc = re.sub(r"&nbsp;", " ", desc)
            desc = re.sub(r"&amp;", "&", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) > 500:
                desc = desc[:500] + "..."
            parts.append(f"  Details: {desc}")

        lines.append("\n".join(parts))
    return "\n".join(lines)


@bp.route("/admin/import-url")
@login_required
def import_url():
    denied = _require_skipper_or_admin()
    if denied:
        return denied
    prefill_url = request.args.get("url", "")
    prefill_force = request.args.get("force", "")
    return render_template(
        "admin/import_url.html",
        prefill_url=prefill_url,
        prefill_force=prefill_force,
    )


@bp.route("/admin/import-file")
@login_required
def import_file():
    denied = _require_skipper_or_admin()
    if denied:
        return denied
    return render_template("admin/import_file.html", current_year=date.today().year)


@bp.route("/admin/import-schedule")
@login_required
def import_schedule():
    """Legacy URL — redirect to import-url."""
    return redirect(url_for("admin.import_url"))


@bp.route("/admin/import-single")
@login_required
def import_single():
    """Legacy URL — redirect to import-url."""
    return redirect(url_for("admin.import_url"))


@bp.route("/admin/import-multiple")
@login_required
def import_multiple():
    """Legacy URL — redirect to import-url."""
    return redirect(url_for("admin.import_url"))


@bp.route("/admin/import-paste")
@login_required
def import_paste():
    denied = _require_skipper_or_admin()
    if denied:
        return denied
    return render_template("admin/import_paste.html")


@bp.route("/admin/settings/analytics", methods=["GET", "POST"])
@login_required
def analytics_settings():
    denied = _require_admin()
    if denied:
        return denied

    if request.method == "POST":
        ga_measurement_id = request.form.get("ga_measurement_id", "").strip().upper()
        _upsert_site_setting("ga_measurement_id", ga_measurement_id)

        if ga_measurement_id and not re.match(r"^(G|GT)-[A-Z0-9]+$", ga_measurement_id):
            flash(
                "Measurement ID saved, but format looks unusual. Expected examples: G-XXXXXXX or GT-XXXXXXX.",
                "warning",
            )

        flash("Google Analytics settings updated.", "success")
        return redirect(url_for("admin.analytics_settings"))

    ga_measurement_id = ""
    setting = SiteSetting.query.filter_by(key="ga_measurement_id").first()
    if setting and setting.value:
        ga_measurement_id = setting.value

    return render_template(
        "admin/analytics_settings.html",
        ga_measurement_id=ga_measurement_id,
    )


@bp.route("/admin/settings/email", methods=["GET", "POST"])
@login_required
def email_settings():
    denied = _require_admin()
    if denied:
        return denied

    if request.method == "POST":
        ses_sender = request.form.get("ses_sender", "").strip()
        ses_sender_to = request.form.get("ses_sender_to", "").strip()
        ses_region = request.form.get("ses_region", "").strip()

        _upsert_site_setting("ses_sender", ses_sender)
        _upsert_site_setting("ses_sender_to", ses_sender_to)
        if ses_region:
            _upsert_site_setting("ses_region", ses_region)

        # Reminder settings
        rsvp_days = request.form.get("reminder_rsvp_days_before", "").strip()
        upcoming_days = request.form.get("reminder_upcoming_days_before", "").strip()
        api_token = request.form.get("reminder_api_token", "").strip()

        if rsvp_days:
            _upsert_site_setting("reminder_rsvp_days_before", rsvp_days)
        if upcoming_days:
            _upsert_site_setting("reminder_upcoming_days_before", upcoming_days)
        _upsert_site_setting("reminder_api_token", api_token)

        flash("Email settings updated.", "success")
        return redirect(url_for("admin.email_settings"))

    settings = load_email_settings()

    # Load reminder settings
    rsvp_days_setting = SiteSetting.query.filter_by(
        key="reminder_rsvp_days_before"
    ).first()
    upcoming_days_setting = SiteSetting.query.filter_by(
        key="reminder_upcoming_days_before"
    ).first()
    api_token_setting = SiteSetting.query.filter_by(key="reminder_api_token").first()

    return render_template(
        "admin/email_settings.html",
        ses_sender=settings["ses_sender"],
        ses_sender_to=settings["ses_sender_to"],
        ses_region=settings["ses_region"],
        email_configured=is_email_configured(),
        reminder_rsvp_days=rsvp_days_setting.value if rsvp_days_setting else "14",
        reminder_upcoming_days=(
            upcoming_days_setting.value if upcoming_days_setting else "3"
        ),
        reminder_api_token=(api_token_setting.value if api_token_setting else ""),
    )


@bp.route("/admin/settings/email/test", methods=["POST"])
@login_required
def email_test():
    if not current_user.is_admin:
        return jsonify({"success": False, "error": "Access denied."}), 403

    try:
        settings = load_email_settings()
        recipient = settings["ses_sender_to"] or current_user.email
        send_email(
            to=recipient,
            subject="Race Crew Network — Test Email",
            body_text="This is a test email from Race Crew Network. "
            "If you received this, your email settings are working correctly.",
            body_html="<p>This is a test email from <strong>Race Crew Network</strong>.</p>"
            "<p>If you received this, your email settings are working correctly.</p>",
        )
        return jsonify({"success": True, "message": f"Test email sent to {recipient}."})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except ClientError as exc:
        error_msg = exc.response["Error"].get("Message", str(exc))
        return jsonify({"success": False, "error": error_msg}), 500


@bp.route("/admin/api/send-reminders", methods=["GET"])
@csrf.exempt
def send_reminders_api():
    """Token-authenticated endpoint to trigger all scheduled reminders.

    Called by AWS EventBridge or manually from admin UI.
    No login required — uses token-based auth only.
    """
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "Missing token"}), 403

    stored_token = SiteSetting.query.filter_by(key="reminder_api_token").first()
    if not stored_token or not stored_token.value or stored_token.value != token:
        return jsonify({"error": "Invalid token"}), 403

    from app.notifications.service import send_all_reminders

    summary = send_all_reminders()
    return jsonify(summary)


@bp.route("/admin/import-schedule/extract", methods=["POST"])
@login_required
def import_schedule_extract():
    """SSE endpoint that streams extraction progress."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    schedule_text = request.form.get("schedule_text", "").strip()
    schedule_url = request.form.get("schedule_url", "").strip()
    force_extract = request.form.get("force_extract") == "1"
    current_year = date.today().year
    year = int(request.form.get("year", current_year))
    task_id = str(uuid.uuid4())
    user_id = current_user.id

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        _cleanup_stale_task_results()
        content = schedule_text
        from_cache = False

        # Check cache for URL-based imports (not pasted text)
        if schedule_url and not force_extract:
            cached = ImportCache.query.filter_by(url=schedule_url).first()
            if cached:
                try:
                    regattas = json.loads(cached.results_json)
                except (json.JSONDecodeError, ValueError):
                    regattas = None

                if regattas is not None:
                    from_cache = True
                    days = _cache_age_days(cached.extracted_at)
                    if days == 0:
                        age_str = "today"
                    elif days == 1:
                        age_str = "1 day ago"
                    else:
                        age_str = f"{days} days ago"

                    yield _sse(
                        {
                            "type": "progress",
                            "message": (
                                f"Using cached results from {age_str}"
                                f" ({cached.regatta_count} regattas)"
                            ),
                        }
                    )

        if not from_cache:
            if schedule_url:
                if force_extract:
                    yield _sse(
                        {
                            "type": "progress",
                            "message": "Force re-extract requested...",
                        }
                    )
                yield _sse(
                    {"type": "progress", "message": f"Fetching {schedule_url}..."}
                )
                try:
                    content = _fetch_url_content(schedule_url)
                except (ValueError, requests.RequestException) as e:
                    yield _sse(
                        {"type": "error", "message": f"Could not fetch URL: {e}"}
                    )
                    yield _sse({"type": "failed"})
                    return
            elif content:
                yield _sse({"type": "progress", "message": "Processing pasted text..."})

            if not content:
                yield _sse({"type": "error", "message": "No content to process."})
                yield _sse({"type": "failed"})
                return

            yield _sse(
                {"type": "progress", "message": "Sending to AI for extraction..."}
            )

            try:
                regattas = extract_regattas(content, year)
            except (ValueError, ConnectionError) as e:
                yield _sse({"type": "error", "message": str(e)})
                yield _sse({"type": "failed"})
                return

            yield _sse(
                {
                    "type": "result",
                    "message": f"AI returned {len(regattas)} event(s)",
                }
            )

            # Cache results for URL-based imports
            if schedule_url and regattas:
                _upsert_import_cache(schedule_url, year, regattas)

        # If source was a URL, use it as fallback detail_url for any regatta
        # the AI didn't provide an individual page URL for.
        if schedule_url:
            for r in regattas:
                if not r.get("detail_url"):
                    r["detail_url"] = schedule_url

        # Mark past events
        today = date.today().isoformat()
        past_count = 0
        for r in regattas:
            if (r.get("start_date") or "") < today:
                r["is_past"] = True
                past_count += 1

        if past_count:
            yield _sse(
                {
                    "type": "progress",
                    "message": f"Flagged {past_count} past event(s)",
                }
            )

        if not regattas:
            yield _sse({"type": "error", "message": "No regattas found."})
            yield _sse({"type": "failed"})
            return

        # Check for duplicates
        dup_count = 0
        for r in regattas:
            start = r.get("start_date")
            name = r.get("name")
            if name and start:
                existing = _find_duplicate(
                    name, date.fromisoformat(start), owner_id=user_id
                )
                if existing:
                    dup_count += 1
                    r["duplicate_of"] = {
                        "id": existing.id,
                        "name": existing.name,
                        "location": existing.location,
                        "start_date": existing.start_date.isoformat(),
                    }

        if dup_count:
            yield _sse(
                {
                    "type": "progress",
                    "message": f"Found {dup_count} possible duplicate(s)",
                }
            )

        _store_task_result(
            task_id,
            "extraction",
            {
                "regattas": regattas,
                "year": year,
                "from_cache": from_cache,
                "source_url": schedule_url,
            },
        )

        upcoming = len(regattas) - past_count
        summary = f"Found {len(regattas)} regatta(s)"
        if past_count:
            summary += f" ({upcoming} upcoming, {past_count} past)"
        if from_cache:
            summary += " (cached)"
        yield _sse({"type": "done", "task_id": task_id, "summary": summary})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/admin/import-schedule/extract-file", methods=["POST"])
@login_required
def import_schedule_extract_file():
    """SSE endpoint that streams extraction progress for an uploaded file."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    uploaded = request.files.get("schedule_file")
    force_extract = request.form.get("force_extract") == "1"
    current_year = date.today().year
    year = int(request.form.get("year", current_year))
    task_id = str(uuid.uuid4())
    user_id = current_user.id

    # Read upload data eagerly — the stream may be closed before the
    # SSE generator runs (SpooledTemporaryFile lifecycle).
    if uploaded and uploaded.filename:
        file_bytes = uploaded.stream.read()
        file_name = uploaded.filename
    else:
        file_bytes = None
        file_name = None

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        _cleanup_stale_task_results()
        if file_bytes is None or not file_name:
            yield _sse({"type": "error", "message": "No file uploaded."})
            yield _sse({"type": "failed"})
            return

        filename = file_name
        yield _sse({"type": "progress", "message": f"Reading file: {filename}..."})

        raw_bytes = file_bytes
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        cache_key = f"file-sha256:{content_hash}"

        # Wrap bytes in a FileStorage so extract_text_from_file can read it
        from io import BytesIO

        from werkzeug.datastructures import FileStorage

        file_obj = FileStorage(
            stream=BytesIO(raw_bytes), filename=filename
        )

        try:
            content = extract_text_from_file(file_obj, filename)
        except ValueError as e:
            yield _sse({"type": "error", "message": str(e)})
            yield _sse({"type": "failed"})
            return

        content = content[:MAX_CONTENT_LENGTH]

        from_cache = False

        # Check cache by content hash
        if not force_extract:
            cached = ImportCache.query.filter_by(url=cache_key).first()
            if cached:
                try:
                    regattas = json.loads(cached.results_json)
                except (json.JSONDecodeError, ValueError):
                    regattas = None

                if regattas is not None:
                    from_cache = True
                    days = _cache_age_days(cached.extracted_at)
                    if days == 0:
                        age_str = "today"
                    elif days == 1:
                        age_str = "1 day ago"
                    else:
                        age_str = f"{days} days ago"

                    yield _sse(
                        {
                            "type": "progress",
                            "message": (
                                f"Using cached results from {age_str}"
                                f" ({cached.regatta_count} regattas)"
                            ),
                        }
                    )

        if not from_cache:
            if force_extract:
                yield _sse(
                    {
                        "type": "progress",
                        "message": "Force re-extract requested...",
                    }
                )

            yield _sse(
                {"type": "progress", "message": "Sending to AI for extraction..."}
            )

            try:
                regattas = extract_regattas(content, year)
            except (ValueError, ConnectionError) as e:
                yield _sse({"type": "error", "message": str(e)})
                yield _sse({"type": "failed"})
                return

            yield _sse(
                {
                    "type": "result",
                    "message": f"AI returned {len(regattas)} event(s)",
                }
            )

            # Cache results by content hash
            if regattas:
                _upsert_import_cache(cache_key, year, regattas)

        # Mark past events
        today = date.today().isoformat()
        past_count = 0
        for r in regattas:
            if (r.get("start_date") or "") < today:
                r["is_past"] = True
                past_count += 1

        if past_count:
            yield _sse(
                {
                    "type": "progress",
                    "message": f"Flagged {past_count} past event(s)",
                }
            )

        if not regattas:
            yield _sse({"type": "error", "message": "No regattas found."})
            yield _sse({"type": "failed"})
            return

        # Check for duplicates
        dup_count = 0
        for r in regattas:
            start = r.get("start_date")
            name = r.get("name")
            if name and start:
                existing = _find_duplicate(
                    name, date.fromisoformat(start), owner_id=user_id
                )
                if existing:
                    dup_count += 1
                    r["duplicate_of"] = {
                        "id": existing.id,
                        "name": existing.name,
                        "location": existing.location,
                        "start_date": existing.start_date.isoformat(),
                    }

        if dup_count:
            yield _sse(
                {
                    "type": "progress",
                    "message": f"Found {dup_count} possible duplicate(s)",
                }
            )

        _store_task_result(
            task_id,
            "extraction",
            {
                "regattas": regattas,
                "year": year,
                "from_cache": from_cache,
                "source_url": "",
            },
        )

        upcoming = len(regattas) - past_count
        summary = f"Found {len(regattas)} regatta(s)"
        if past_count:
            summary += f" ({upcoming} upcoming, {past_count} past)"
        yield _sse({"type": "done", "task_id": task_id, "summary": summary})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/admin/import-schedule/extract-single", methods=["POST"])
@login_required
def import_schedule_extract_single():
    """SSE endpoint: extract a single regatta (no document discovery)."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    schedule_url = request.form.get("schedule_url", "").strip()
    force_extract = request.form.get("force_extract") == "1"
    current_year = date.today().year
    year = int(request.form.get("year", current_year))
    task_id = str(uuid.uuid4())
    user_id = current_user.id

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        _cleanup_stale_task_results()
        if not schedule_url:
            yield _sse({"type": "error", "message": "Provide a regatta URL."})
            yield _sse({"type": "failed"})
            return

        from_cache = False
        regattas = None

        # Check cache unless force re-extract
        if not force_extract:
            cached = ImportCache.query.filter_by(url=schedule_url).first()
            if cached:
                try:
                    regattas = json.loads(cached.results_json)
                except (json.JSONDecodeError, ValueError):
                    regattas = None

                if regattas is not None:
                    from_cache = True
                    days = _cache_age_days(cached.extracted_at)
                    if days == 0:
                        age_str = "today"
                    elif days == 1:
                        age_str = "1 day ago"
                    else:
                        age_str = f"{days} days ago"

                    yield _sse(
                        {
                            "type": "progress",
                            "message": (
                                f"Using cached results from {age_str}"
                                f" ({cached.regatta_count} regattas)"
                            ),
                        }
                    )

        if not from_cache:
            if force_extract:
                yield _sse(
                    {
                        "type": "progress",
                        "message": "Force re-extract requested...",
                    }
                )
            yield _sse({"type": "progress", "message": f"Fetching {schedule_url}..."})

            try:
                content = _fetch_url_content(schedule_url)
            except (ValueError, requests.RequestException) as e:
                yield _sse({"type": "error", "message": f"Could not fetch URL: {e}"})
                yield _sse({"type": "failed"})
                return

            yield _sse(
                {"type": "progress", "message": "Sending to AI for extraction..."}
            )

            try:
                regattas = extract_regattas(content, year)
            except (ValueError, ConnectionError) as e:
                yield _sse({"type": "error", "message": str(e)})
                yield _sse({"type": "failed"})
                return

            if not regattas:
                yield _sse({"type": "error", "message": "No regatta found on page."})
                yield _sse({"type": "failed"})
                return

            # Cache results
            _upsert_import_cache(schedule_url, year, regattas)

        if not regattas:
            yield _sse({"type": "error", "message": "No regatta found on page."})
            yield _sse({"type": "failed"})
            return

        # Take only the first regatta for single-import mode
        r = regattas[0]
        r["detail_url"] = r.get("detail_url") or schedule_url

        yield _sse({"type": "result", "message": f"Extracted: {r.get('name', '?')}"})

        # Check for duplicate
        start = r.get("start_date")
        name = r.get("name")
        if name and start:
            existing = _find_duplicate(
                name, date.fromisoformat(start), owner_id=user_id
            )
            if existing:
                r["duplicate_of"] = {
                    "id": existing.id,
                    "name": existing.name,
                    "location": existing.location,
                    "start_date": existing.start_date.isoformat(),
                }
                yield _sse(
                    {
                        "type": "progress",
                        "message": "Possible duplicate found",
                    }
                )

        _store_task_result(
            task_id,
            "extraction",
            {
                "regatta": r,
                "year": year,
                "from_cache": from_cache,
                "source_url": schedule_url,
            },
        )

        summary = r.get("name", "Regatta")
        if from_cache:
            summary += " (cached)"
        yield _sse({"type": "done", "task_id": task_id, "summary": summary})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/admin/import-single/preview")
@login_required
def import_single_preview():
    """Render single regatta editable preview from extraction results."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    task_id = request.args.get("task_id", "")
    data = _pop_task_result(task_id, "extraction") if task_id else None
    if not data:
        flash("Extraction results not found or expired.", "error")
        return redirect(url_for("admin.import_single"))

    return render_template(
        "admin/import_single_preview.html",
        regatta=data["regatta"],
    )


@bp.route("/admin/import-schedule/preview")
@login_required
def import_schedule_preview():
    """Render extraction results from SSE extraction."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    task_id = request.args.get("task_id", "")
    data = _pop_task_result(task_id, "extraction") if task_id else None
    if not data:
        flash("Extraction results not found or expired.", "error")
        return redirect(url_for("admin.import_url"))

    # Determine start_over_url from source (default to import_url)
    start_over_url = request.args.get("start_over_url", url_for("admin.import_url"))

    # Build cache info for the template
    from_cache = data.get("from_cache", False)
    source_url = data.get("source_url", "")
    cache_info = None
    if from_cache and source_url:
        cached = ImportCache.query.filter_by(url=source_url).first()
        if cached:
            cache_info = {
                "extracted_at": cached.extracted_at,
                "regatta_count": cached.regatta_count,
                "source_url": source_url,
            }

    return render_template(
        "admin/import_preview.html",
        regattas=data["regattas"],
        confirm_url=url_for("admin.import_schedule_confirm"),
        start_over_url=start_over_url,
        show_discover_btn=True,
        cache_info=cache_info,
    )


@bp.route("/admin/import-schedule/confirm", methods=["POST"])
@login_required
def import_schedule_confirm():
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    selected = request.form.getlist("selected")
    if not selected:
        flash("No regattas selected for import.", "warning")
        return redirect(url_for("admin.import_url"))

    created = 0
    skipped = 0
    docs_created = 0

    for idx in selected:
        name = request.form.get(f"name_{idx}", "").strip()
        boat_class = request.form.get(f"boat_class_{idx}", "").strip()
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

        # Duplicate check: case-insensitive name + start_date (scoped to user)
        existing = _find_duplicate(name, start_date, owner_id=current_user.id)
        if existing:
            skipped += 1
            continue

        # Auto-generate Google Maps link if no location_url
        if not location_url and location:
            location_url = f"https://www.google.com/maps/search/{quote_plus(location)}"

        detail_url = request.form.get(f"detail_url_{idx}", "").strip()

        regatta = Regatta(
            name=name,
            boat_class=boat_class,
            location=location or "TBD",
            location_url=location_url or None,
            start_date=start_date,
            end_date=end_date,
            notes=notes or None,
            source_url=detail_url or None,
            created_by=current_user.id,
        )
        db.session.add(regatta)
        created += 1

        # Create associated documents if present
        doc_count_str = request.form.get(f"doc_count_{idx}", "0")
        try:
            doc_count = int(doc_count_str)
        except ValueError:
            doc_count = 0

        if doc_count > 0:
            db.session.flush()  # Get regatta.id
            for d_idx in range(doc_count):
                checkbox = request.form.get(f"doc_{idx}_{d_idx}")
                if not checkbox:
                    continue
                doc_type = request.form.get(f"doc_type_{idx}_{d_idx}", "").strip()
                doc_url = request.form.get(f"doc_url_{idx}_{d_idx}", "").strip()
                if doc_type and doc_url:
                    doc = Document(
                        regatta_id=regatta.id,
                        doc_type=doc_type,
                        url=doc_url,
                        uploaded_by=current_user.id,
                    )
                    db.session.add(doc)
                    docs_created += 1

    db.session.commit()

    msg = f"Successfully imported {created} regatta(s)."
    if docs_created:
        msg += f" {docs_created} document(s) attached."
    if created:
        flash(msg, "success")
    if skipped:
        flash(f"Skipped {skipped} regatta(s) (invalid or duplicate).", "warning")

    return redirect(url_for("regattas.index"))


@bp.route("/admin/import-schedule/discover", methods=["POST"])
@login_required
def import_schedule_discover():
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    selected = request.form.getlist("selected")
    task_id = str(uuid.uuid4())

    # Collect regatta data from the form
    regatta_data = []
    for idx in selected:
        regatta_data.append(
            {
                "idx": idx,
                "name": request.form.get(f"name_{idx}", "").strip(),
                "boat_class": request.form.get(f"boat_class_{idx}", "").strip(),
                "location": request.form.get(f"location_{idx}", "").strip(),
                "location_url": request.form.get(f"location_url_{idx}", "").strip(),
                "start_date": request.form.get(f"start_date_{idx}", "").strip(),
                "end_date": request.form.get(f"end_date_{idx}", "").strip(),
                "notes": request.form.get(f"notes_{idx}", "").strip(),
                "detail_url": request.form.get(f"detail_url_{idx}", "").strip(),
                "documents": [],
                "error": None,
            }
        )

    if not regatta_data:
        msg = json.dumps({"type": "error", "message": "No regattas selected."})
        return Response(
            f"data: {msg}\n\n",
            content_type="text/event-stream",
        )

    # Check if any regattas have detail URLs
    has_detail_urls = any(r["detail_url"] for r in regatta_data)

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        _cleanup_stale_task_results()
        total_docs = 0

        if not has_detail_urls:
            yield _sse(
                {
                    "type": "progress",
                    "message": "No detail URLs found — skipping document discovery.",
                }
            )
        else:
            for r in regatta_data:
                name = r["name"]
                if not r["detail_url"]:
                    yield _sse(
                        {
                            "type": "progress",
                            "message": f"Skipping {name} — no detail URL",
                        }
                    )
                    continue

                yield _sse({"type": "progress", "message": f"Fetching: {name}..."})

                try:
                    # Clubspot detail URL: query Parse API directly
                    cs_id = _parse_clubspot_regatta_id(r["detail_url"])
                    if cs_id:
                        docs = _fetch_clubspot_documents(cs_id)
                        # Add the clubspot page itself as WWW
                        docs.append(
                            {
                                "doc_type": "WWW",
                                "url": r["detail_url"],
                                "label": "Regatta website",
                            }
                        )
                    else:
                        content = _fetch_url_content(r["detail_url"])
                        docs = discover_documents(content, name, r["detail_url"])

                    r["documents"] = docs
                    total_docs += len(docs)

                    if docs:
                        doc_types = ", ".join(d["doc_type"] for d in docs)
                        yield _sse(
                            {
                                "type": "result",
                                "message": f"Found: {doc_types}",
                            }
                        )
                    else:
                        yield _sse(
                            {
                                "type": "result",
                                "message": "No documents found",
                            }
                        )

                    # Level 2: check WWW links for NOR/SI (skip if
                    # we already used a direct API like clubspot)
                    www_docs = [d for d in docs if d["doc_type"] == "WWW" and not cs_id]
                    existing_types = {d["doc_type"] for d in docs}
                    for www_doc in www_docs:
                        # Skip if we already found both NOR and SI
                        if "NOR" in existing_types and "SI" in existing_types:
                            break

                        www_url = www_doc["url"]
                        yield _sse(
                            {
                                "type": "progress",
                                "message": (
                                    "Checking regatta website for documents..."
                                ),
                            }
                        )

                        try:
                            # Clubspot: query Parse API directly
                            cs_id = _parse_clubspot_regatta_id(www_url)
                            if cs_id:
                                deep_docs = _fetch_clubspot_documents(cs_id)
                            else:
                                www_content = _fetch_url_content(www_url)
                                deep_docs = discover_documents_deep(
                                    www_content, name, www_url
                                )

                            # Only add doc types we don't already have
                            new_docs = [
                                d
                                for d in deep_docs
                                if d["doc_type"] not in existing_types
                            ]
                            if new_docs:
                                r["documents"].extend(new_docs)
                                total_docs += len(new_docs)
                                existing_types.update(d["doc_type"] for d in new_docs)
                                deep_types = ", ".join(d["doc_type"] for d in new_docs)
                                yield _sse(
                                    {
                                        "type": "result",
                                        "message": (
                                            "Found on regatta website:" f" {deep_types}"
                                        ),
                                    }
                                )
                            else:
                                yield _sse(
                                    {
                                        "type": "result",
                                        "message": ("No additional documents found"),
                                    }
                                )
                        except Exception as e:
                            logger.warning(
                                "Level-2 crawl failed for %s: %s",
                                www_url,
                                e,
                            )
                            yield _sse(
                                {
                                    "type": "result",
                                    "message": ("Could not check regatta website"),
                                }
                            )

                except (ValueError, requests.RequestException) as e:
                    r["error"] = str(e)
                    yield _sse(
                        {
                            "type": "error",
                            "message": f"Could not fetch page: {e}",
                        }
                    )
                except (ConnectionError, Exception) as e:
                    r["error"] = str(e)
                    yield _sse({"type": "error", "message": f"Error: {e}"})

        for r in regatta_data:
            r["documents"].sort(key=lambda d: d["doc_type"])

        _store_task_result(task_id, "discovery", regatta_data)

        regattas_with_docs = sum(1 for r in regatta_data if r["documents"])
        summary = (
            f"Found {total_docs} document(s) " f"for {regattas_with_docs} regatta(s)"
        )
        yield _sse({"type": "done", "task_id": task_id, "summary": summary})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/admin/import-schedule/documents")
@login_required
def import_schedule_documents():
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    task_id = request.args.get("task_id", "")
    regatta_data = _pop_task_result(task_id, "discovery") if task_id else None
    if not regatta_data:
        flash("Document discovery results not found or expired.", "error")
        return redirect(url_for("admin.import_url"))

    start_over_url = request.args.get("start_over_url", url_for("admin.import_url"))

    return render_template(
        "admin/import_schedule_documents.html",
        regattas=regatta_data,
        start_over_url=start_over_url,
    )


@bp.route("/admin/regattas/<int:regatta_id>/discover-documents", methods=["POST"])
@login_required
def discover_documents_for_regatta(regatta_id: int):
    """SSE endpoint: discover NOR/SI/WWW documents for an existing regatta."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    regatta = db.session.get(Regatta, regatta_id)
    if not regatta or not regatta.source_url:
        msg = json.dumps({"type": "error", "message": "No source URL set."})
        return Response(
            f"data: {msg}\n\ndata: " + json.dumps({"type": "failed"}) + "\n\n",
            content_type="text/event-stream",
        )

    source_url = regatta.source_url
    force_extract = request.form.get("force_extract") == "1"
    task_id = str(uuid.uuid4())

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        _cleanup_stale_task_results()
        total_docs = 0
        documents = []

        if force_extract:
            yield _sse({"type": "progress", "message": "Force re-extract requested..."})

        yield _sse({"type": "progress", "message": f"Fetching {source_url}..."})

        try:
            cs_id = _parse_clubspot_regatta_id(source_url)
            if cs_id:
                docs = _fetch_clubspot_documents(cs_id)
                docs.append(
                    {
                        "doc_type": "WWW",
                        "url": source_url,
                        "label": "Regatta website",
                    }
                )
            else:
                content = _fetch_url_content(source_url)
                docs = discover_documents(content, regatta.name, source_url)

            documents.extend(docs)
            total_docs += len(docs)

            if docs:
                doc_types = ", ".join(d["doc_type"] for d in docs)
                yield _sse({"type": "result", "message": f"Found: {doc_types}"})
            else:
                yield _sse({"type": "result", "message": "No documents found"})

            # Level 2: check WWW links for NOR/SI
            www_docs = [d for d in docs if d["doc_type"] == "WWW" and not cs_id]
            existing_types = {d["doc_type"] for d in docs}
            for www_doc in www_docs:
                if "NOR" in existing_types and "SI" in existing_types:
                    break

                www_url = www_doc["url"]
                yield _sse(
                    {
                        "type": "progress",
                        "message": "Checking regatta website for documents...",
                    }
                )

                try:
                    deep_cs_id = _parse_clubspot_regatta_id(www_url)
                    if deep_cs_id:
                        deep_docs = _fetch_clubspot_documents(deep_cs_id)
                    else:
                        www_content = _fetch_url_content(www_url)
                        deep_docs = discover_documents_deep(
                            www_content, regatta.name, www_url
                        )

                    new_docs = [
                        d for d in deep_docs if d["doc_type"] not in existing_types
                    ]
                    if new_docs:
                        documents.extend(new_docs)
                        total_docs += len(new_docs)
                        existing_types.update(d["doc_type"] for d in new_docs)
                        deep_types = ", ".join(d["doc_type"] for d in new_docs)
                        yield _sse(
                            {
                                "type": "result",
                                "message": f"Found on regatta website: {deep_types}",
                            }
                        )
                    else:
                        yield _sse(
                            {
                                "type": "result",
                                "message": "No additional documents found",
                            }
                        )
                except Exception as e:
                    logger.warning("Level-2 crawl failed for %s: %s", www_url, e)
                    yield _sse(
                        {
                            "type": "result",
                            "message": "Could not check regatta website",
                        }
                    )

        except (ValueError, requests.RequestException) as e:
            yield _sse({"type": "error", "message": f"Could not fetch page: {e}"})
            yield _sse({"type": "failed"})
            return
        except (ConnectionError, Exception) as e:
            yield _sse({"type": "error", "message": f"Error: {e}"})
            yield _sse({"type": "failed"})
            return

        documents.sort(key=lambda d: d["doc_type"])

        _store_task_result(
            task_id,
            "discovery",
            {
                "regatta_id": regatta_id,
                "documents": documents,
            },
        )

        summary = f"Found {total_docs} document(s)"
        yield _sse({"type": "done", "task_id": task_id, "summary": summary})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/admin/regattas/<int:regatta_id>/review-documents")
@login_required
def review_documents_for_regatta(regatta_id: int):
    """Show discovered documents with checkboxes for an existing regatta."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        flash("Regatta not found.", "error")
        return redirect(url_for("regattas.index"))

    task_id = request.args.get("task_id", "")
    data = _pop_task_result(task_id, "discovery") if task_id else None
    if not data:
        flash("Document discovery results not found or expired.", "error")
        return redirect(url_for("regattas.edit", regatta_id=regatta_id))

    # Build a map of existing doc URLs to doc_type for duplicate detection
    existing_docs = {doc.url: doc.doc_type for doc in regatta.documents if doc.url}

    return render_template(
        "admin/regatta_discover_documents.html",
        regatta=regatta,
        documents=data["documents"],
        existing_docs=existing_docs,
    )


@bp.route("/admin/regattas/<int:regatta_id>/attach-documents", methods=["POST"])
@login_required
def attach_documents_for_regatta(regatta_id: int):
    """Create Document records for selected discovered documents."""
    denied = _require_skipper_or_admin()
    if denied:
        return denied

    regatta = db.session.get(Regatta, regatta_id)
    if not regatta:
        flash("Regatta not found.", "error")
        return redirect(url_for("regattas.index"))

    doc_count_str = request.form.get("doc_count", "0")
    try:
        doc_count = int(doc_count_str)
    except ValueError:
        doc_count = 0

    # Map existing doc URLs to their Document objects for replacement
    existing_by_url = {doc.url: doc for doc in regatta.documents if doc.url}

    created = 0
    replaced = 0
    for i in range(doc_count):
        checkbox = request.form.get(f"doc_{i}")
        if not checkbox:
            continue
        doc_type = request.form.get(f"doc_type_{i}", "").strip()
        doc_url = request.form.get(f"doc_url_{i}", "").strip()
        if doc_type and doc_url:
            existing = existing_by_url.get(doc_url)
            if existing:
                existing.doc_type = doc_type
                existing.uploaded_by = current_user.id
                replaced += 1
            else:
                doc = Document(
                    regatta_id=regatta_id,
                    doc_type=doc_type,
                    url=doc_url,
                    uploaded_by=current_user.id,
                )
                db.session.add(doc)
                existing_by_url[doc_url] = doc
                created += 1

    db.session.commit()

    parts = []
    if created:
        parts.append(f"{created} document(s) attached")
    if replaced:
        parts.append(f"{replaced} existing document(s) updated")
    if parts:
        flash(". ".join(parts) + ".", "success")
    else:
        flash("No documents selected.", "warning")

    return redirect(url_for("regattas.edit", regatta_id=regatta_id))
