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

Rules:
- The year is {year} unless the text explicitly states otherwise.
- If a date says only "Mar 15", interpret as {year}-03-15.
- If a date range says "Mar 15-16", set start_date to the 15th and end_date \
to the 16th.
- If only one date is given, set end_date to null.
- Return ONLY the JSON array, no markdown fences, no explanation.
- If no events are found, return an empty array: []

Text to extract from:
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
