"""
Parses the raw newsletter content into a clean structured form for the personalizer.
Strips HTML tags when plain text isn't available and normalises whitespace.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _normalise(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_newsletter(raw: dict) -> dict:
    """
    Takes the output of gmail_client.extract_raw_content() and returns a
    cleaned dict ready for the personalizer.

    Returns:
        {
            "subject": str,
            "sender": str,
            "date": str,
            "body": str,       # clean plain text, best available
            "message_id": str,
        }
    """
    body = raw.get("plain_text") or ""
    if not body and raw.get("html"):
        body = _clean_html(raw["html"])

    return {
        "subject": raw.get("subject", ""),
        "sender": raw.get("sender", ""),
        "date": raw.get("date", ""),
        "body": _normalise(body),
        "message_id": raw.get("message_id", ""),
    }
