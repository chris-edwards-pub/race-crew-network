import json
import logging

import anthropic
from flask import current_app

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a data extraction assistant. Extract regatta/sailing event information \
from the provided text and return a JSON array.

Each object in the array must have these fields:
- "name": string (event name)
- "location": string (city, yacht club, or venue)
- "location_url": string or null (URL for the venue if mentioned)
- "start_date": string in "YYYY-MM-DD" format
- "end_date": string in "YYYY-MM-DD" format or null (if single-day event)
- "notes": string or null (any extra details like classes, contacts, etc.)
- "detail_url": string or null (URL to the regatta's own detail/information page, \
NOT the venue link)

Rules:
- The year is {year} unless the text explicitly states otherwise.
- If a date says only "Mar 15", interpret as {year}-03-15.
- If a date range says "Mar 15-16", set start_date to the 15th and end_date \
to the 16th.
- If only one date is given, set end_date to null.
- If the text contains a link to an individual regatta's event page or \
information page, include it as detail_url. This is NOT the venue/location URL.
- Return ONLY the JSON array, no markdown fences, no explanation.
- If no events are found, return an empty array: []

Text to extract from:
{content}"""

DOCUMENT_DISCOVERY_PROMPT = """\
You are a document link extraction assistant for sailing regattas. \
Given the content of a regatta detail page, find links to official documents.

Look for these document types:
- "NOR": Notice of Race — usually a PDF link (.pdf)
- "SI": Sailing Instructions — usually a PDF link (.pdf)
- "WWW": The regatta's own website or event page. This includes:
  - Registration/entry portals on known regatta platforms \
(theclubspot.com, regattanetwork.com, yachtscoring.com)
  - Links labeled "Register", "Registration", "Entry", "Sign up", or "Event page"
  - Bare URLs to regatta management platforms
  - Any link that leads to a page specifically about THIS regatta \
(not the hosting club's general site)

Return a JSON array of objects with these fields:
- "doc_type": one of "NOR", "SI", "WWW"
- "url": the full URL to the document or website
- "label": a short descriptive label (e.g. "Notice of Race", "Sailing Instructions", \
"Regatta website")

Rules:
- If the page links to theclubspot.com/regatta/*, regattanetwork.com/event/*, or \
yachtscoring.com — that is a WWW link.
- NOR and SI are typically PDF files (.pdf) but may be other document formats.
- Do NOT include: the source page URL itself, calendar export links (.ics), \
social media links, or the hosting club's general website.
- Return ONLY the JSON array, no markdown fences, no explanation.
- If no documents are found, return an empty array: []

Regatta name: {regatta_name}
Source page URL: {source_url}

Page content:
{content}"""


DOCUMENT_DEEP_DISCOVERY_PROMPT = """\
You are a document link extraction assistant for sailing regattas. \
Given the content of a regatta website or event page, find links to official documents.

Look for these document types ONLY:
- "NOR": Notice of Race — usually a PDF link (.pdf)
- "SI": Sailing Instructions — usually a PDF link (.pdf)

Return a JSON array of objects with these fields:
- "doc_type": one of "NOR", "SI"
- "url": the full URL to the document
- "label": a short descriptive label (e.g. "Notice of Race", "Sailing Instructions")

Rules:
- NOR and SI are typically PDF files (.pdf) but may be other document formats.
- Only include links you are confident are NOR or SI.
- Do NOT include website links, registration links, or other document types.
- Return ONLY the JSON array, no markdown fences, no explanation.
- If no documents are found, return an empty array: []

Regatta name: {regatta_name}
Source page URL: {source_url}

Page content:
{content}"""


def extract_regattas(content: str, year: int) -> list[dict]:
    """Send content to Claude API and return extracted regatta data."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = EXTRACTION_PROMPT.format(year=year, content=content)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError:
        raise ConnectionError("Could not connect to the Claude API.")
    except anthropic.RateLimitError:
        raise ConnectionError("Claude API rate limit exceeded. Try again shortly.")
    except anthropic.APIStatusError as e:
        raise ConnectionError(f"Claude API error: {e.message}")

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [ln for ln in lines[1:] if ln.strip() != "```"]
        raw = "\n".join(lines)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON: %s", raw[:500])
        raise ValueError(
            "Could not parse the AI response. Try again with clearer input."
        )

    if not isinstance(data, list):
        raise ValueError("Unexpected AI response format.")

    return data


def _parse_json_response(raw: str) -> list:
    """Parse a JSON array from a Claude response, stripping code fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines[1:] if ln.strip() != "```"]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON: %s", text[:500])
        raise ValueError(
            "Could not parse the AI response. Try again with clearer input."
        )

    if not isinstance(data, list):
        raise ValueError("Unexpected AI response format.")

    return data


def discover_documents(content: str, regatta_name: str, source_url: str) -> list[dict]:
    """Discover NOR/SI/WWW document links from a regatta detail page."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = DOCUMENT_DISCOVERY_PROMPT.format(
        regatta_name=regatta_name,
        source_url=source_url,
        content=content,
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError:
        raise ConnectionError("Could not connect to the Claude API.")
    except anthropic.RateLimitError:
        raise ConnectionError("Claude API rate limit exceeded. Try again shortly.")
    except anthropic.APIStatusError as e:
        raise ConnectionError(f"Claude API error: {e.message}")

    raw = message.content[0].text.strip()
    return _parse_json_response(raw)


def discover_documents_deep(
    content: str, regatta_name: str, source_url: str
) -> list[dict]:
    """Discover NOR/SI document links from a regatta website (level-2 crawl)."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = DOCUMENT_DEEP_DISCOVERY_PROMPT.format(
        regatta_name=regatta_name,
        source_url=source_url,
        content=content,
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError:
        raise ConnectionError("Could not connect to the Claude API.")
    except anthropic.RateLimitError:
        raise ConnectionError("Claude API rate limit exceeded. Try again shortly.")
    except anthropic.APIStatusError as e:
        raise ConnectionError(f"Claude API error: {e.message}")

    raw = message.content[0].text.strip()
    return _parse_json_response(raw)
