import ipaddress
import json
import logging
import re
import uuid
from datetime import date
from socket import getaddrinfo
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import (
    Response,
    flash,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.admin import bp
from app.admin.ai_service import (
    discover_documents,
    discover_documents_deep,
    extract_regattas,
)
from app.models import Document, Regatta

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 20_000

# Temporary storage keyed by UUID task ID, cleaned up when consumed.
_extraction_results: dict[str, dict] = {}
_discovery_results: dict[str, dict] = {}


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

    # If source was a URL and only one regatta extracted, use it as
    # detail_url when the AI didn't provide one (e.g. clubspot pages).
    if schedule_url and len(regattas) == 1 and not regattas[0].get("detail_url"):
        regattas[0]["detail_url"] = schedule_url

    # Mark past events (keep them but flag for the preview)
    today = date.today().isoformat()
    for r in regattas:
        if (r.get("start_date") or "") < today:
            r["is_past"] = True

    if not regattas:
        flash("No regattas found in the provided content.", "warning")

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


@bp.route("/admin/import-schedule/extract", methods=["POST"])
@login_required
def import_schedule_extract():
    """SSE endpoint that streams extraction progress."""
    denied = _require_admin()
    if denied:
        return denied

    schedule_text = request.form.get("schedule_text", "").strip()
    schedule_url = request.form.get("schedule_url", "").strip()
    current_year = date.today().year
    year = int(request.form.get("year", current_year))
    task_id = str(uuid.uuid4())

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        content = schedule_text

        if schedule_url:
            yield _sse({"type": "progress", "message": f"Fetching {schedule_url}..."})
            try:
                content = _fetch_url_content(schedule_url)
            except (ValueError, requests.RequestException) as e:
                yield _sse({"type": "error", "message": f"Could not fetch URL: {e}"})
                yield _sse({"type": "failed"})
                return
        elif content:
            yield _sse({"type": "progress", "message": "Processing pasted text..."})

        if not content:
            yield _sse({"type": "error", "message": "No content to process."})
            yield _sse({"type": "failed"})
            return

        yield _sse({"type": "progress", "message": "Sending to AI for extraction..."})

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

        # If source was a URL and only one regatta extracted, use it as
        # detail_url when the AI didn't provide one (e.g. clubspot pages).
        if schedule_url and len(regattas) == 1 and not regattas[0].get("detail_url"):
            regattas[0]["detail_url"] = schedule_url

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
                existing = _find_duplicate(name, date.fromisoformat(start))
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

        _extraction_results[task_id] = {
            "regattas": regattas,
            "year": year,
        }

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
    """SSE endpoint: extract a single regatta + discover documents in one pass."""
    denied = _require_admin()
    if denied:
        return denied

    schedule_url = request.form.get("schedule_url", "").strip()
    current_year = date.today().year
    year = int(request.form.get("year", current_year))
    task_id = str(uuid.uuid4())

    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        if not schedule_url:
            yield _sse({"type": "error", "message": "Provide a regatta URL."})
            yield _sse({"type": "failed"})
            return

        yield _sse({"type": "progress", "message": f"Fetching {schedule_url}..."})

        try:
            content = _fetch_url_content(schedule_url)
        except (ValueError, requests.RequestException) as e:
            yield _sse({"type": "error", "message": f"Could not fetch URL: {e}"})
            yield _sse({"type": "failed"})
            return

        yield _sse({"type": "progress", "message": "Sending to AI for extraction..."})

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

        # Take only the first regatta for single-import mode
        r = regattas[0]
        r["detail_url"] = r.get("detail_url") or schedule_url

        yield _sse({"type": "result", "message": f"Extracted: {r.get('name', '?')}"})

        # Check for duplicate
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
                yield _sse(
                    {
                        "type": "progress",
                        "message": "Possible duplicate found",
                    }
                )

        # Discover documents
        detail_url = r["detail_url"]
        docs = []
        cs_id = _parse_clubspot_regatta_id(detail_url)

        if cs_id:
            yield _sse(
                {
                    "type": "progress",
                    "message": "Checking clubspot for documents...",
                }
            )
            docs = _fetch_clubspot_documents(cs_id)
            docs.append(
                {
                    "doc_type": "WWW",
                    "url": detail_url,
                    "label": "Regatta website",
                }
            )
        else:
            yield _sse(
                {
                    "type": "progress",
                    "message": "Searching for documents...",
                }
            )
            try:
                docs = discover_documents(content, name or "", detail_url)
            except Exception as e:
                logger.warning("Document discovery failed: %s", e)

            # Level 2: check WWW links for NOR/SI
            www_docs = [d for d in docs if d["doc_type"] == "WWW"]
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
                    wcs_id = _parse_clubspot_regatta_id(www_url)
                    if wcs_id:
                        deep_docs = _fetch_clubspot_documents(wcs_id)
                    else:
                        www_content = _fetch_url_content(www_url)
                        deep_docs = discover_documents_deep(
                            www_content, name or "", www_url
                        )
                    new_docs = [
                        d for d in deep_docs if d["doc_type"] not in existing_types
                    ]
                    docs.extend(new_docs)
                    existing_types.update(d["doc_type"] for d in new_docs)
                except Exception as e:
                    logger.warning("Level-2 crawl failed for %s: %s", www_url, e)

        if docs:
            doc_types = ", ".join(d["doc_type"] for d in docs)
            yield _sse({"type": "result", "message": f"Found: {doc_types}"})
        else:
            yield _sse({"type": "result", "message": "No documents found"})

        # Build regatta_data in the format the document review page expects
        docs.sort(key=lambda d: d["doc_type"])
        regatta_entry = {
            "idx": "0",
            "name": r.get("name", ""),
            "location": r.get("location", ""),
            "location_url": r.get("location_url", ""),
            "start_date": r.get("start_date", ""),
            "end_date": r.get("end_date", ""),
            "notes": r.get("notes", ""),
            "detail_url": detail_url,
            "documents": docs,
            "error": None,
        }
        _discovery_results[task_id] = [regatta_entry]

        summary = f"{r.get('name', 'Regatta')} — {len(docs)} document(s)"
        yield _sse({"type": "done", "task_id": task_id, "summary": summary})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/admin/import-schedule/preview")
@login_required
def import_schedule_preview():
    """Render extraction results from SSE extraction."""
    denied = _require_admin()
    if denied:
        return denied

    task_id = request.args.get("task_id", "")
    if not task_id or task_id not in _extraction_results:
        flash("Extraction results not found or expired.", "error")
        return redirect(url_for("admin.import_schedule"))

    data = _extraction_results.pop(task_id)
    current_year = date.today().year
    years = list(range(current_year, current_year + 3))

    return render_template(
        "admin/import_schedule.html",
        years=years,
        selected_year=data["year"],
        regattas=data["regattas"],
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
    docs_created = 0

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
    denied = _require_admin()
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

        _discovery_results[task_id] = regatta_data

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
    denied = _require_admin()
    if denied:
        return denied

    task_id = request.args.get("task_id", "")
    if not task_id or task_id not in _discovery_results:
        flash("Document discovery results not found or expired.", "error")
        return redirect(url_for("admin.import_schedule"))

    regatta_data = _discovery_results.pop(task_id)

    return render_template(
        "admin/import_schedule_documents.html",
        regattas=regatta_data,
    )
