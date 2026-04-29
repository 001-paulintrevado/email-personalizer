"""
Step 1: Parse the newsletter for events, dates, and links.
For each link found, fetch the page and use Claude to deeply research
the opportunity (eligibility, dates, summary). For entries without links,
Claude infers what the event is likely about.
"""
from __future__ import annotations

import os
import re
import urllib.request
from urllib.error import URLError

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=os.environ["ANTHROPIC_API_KEY"],
            max_tokens=4096,
        )
    return _llm


def _fetch_url(url: str, timeout: int = 10) -> str:
    """Fetch a URL and return cleaned text. Returns empty string on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:8000]
    except (URLError, Exception):
        return ""


def _extract_events_from_newsletter(body: str) -> list[dict]:
    """
    Use Claude to extract all event/date/link triples from the newsletter body.
    Returns a list of dicts with keys: title, date, url (may be empty string).
    """
    llm = _get_llm()
    prompt = (
        "You are parsing a college counseling newsletter. "
        "Extract every event, deadline, opportunity, or date mentioned. "
        "For each one return a JSON array where each element has:\n"
        '  "title": the event or opportunity name\n'
        '  "date": the date or deadline mentioned (empty string if none)\n'
        '  "url": the URL/link associated with it (empty string if none)\n'
        '  "raw_context": a brief quote of the surrounding text from the newsletter\n\n'
        "Return ONLY a valid JSON array, no other text.\n\n"
        f"NEWSLETTER:\n{body}"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    # Strip markdown code fences if present
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    import json
    try:
        events = json.loads(content)
    except json.JSONDecodeError:
        # Response may be truncated — recover complete objects only
        try:
            last_bracket = content.rfind("},")
            if last_bracket > 0:
                content = content[: last_bracket + 1] + "\n]"
            events = json.loads(content)
        except Exception:
            return []
    # Normalise null URLs to empty string
    for e in events:
        if e.get("url") is None:
            e["url"] = ""
    return events


def _research_event(event: dict) -> dict:
    """
    For a single event dict, fetch the URL (if any) and use Claude to
    produce a deep research summary: what it is, eligibility, key dates,
    and a 2-sentence summary.
    """
    llm = _get_llm()
    url = event.get("url", "").strip()
    page_content = ""

    if url:
        print(f"  Fetching: {url}")
        page_content = _fetch_url(url)

    if page_content:
        research_input = (
            f"EVENT TITLE: {event.get('title', '')}\n"
            f"DATE MENTIONED IN NEWSLETTER: {event.get('date', 'not specified')}\n"
            f"NEWSLETTER CONTEXT: {event.get('raw_context', '')}\n\n"
            f"PAGE CONTENT FROM LINKED URL:\n{page_content}"
        )
        system = (
            "You are a college counseling researcher. Based on the event title, "
            "newsletter context, and the linked page content, provide a structured "
            "research summary with the following fields:\n"
            "- what_it_is: clear description of the opportunity\n"
            "- eligibility: who can apply (grade level, GPA, nationality, interests, etc.)\n"
            "- key_dates: all important deadlines and dates\n"
            "- summary: exactly 2 sentences summarising the opportunity\n\n"
            "Return as a JSON object with those four keys only. No other text."
        )
    else:
        research_input = (
            f"EVENT TITLE: {event.get('title', '')}\n"
            f"DATE MENTIONED: {event.get('date', 'not specified')}\n"
            f"NEWSLETTER CONTEXT: {event.get('raw_context', '')}\n\n"
            "No URL was available for this event."
        )
        system = (
            "You are a college counseling researcher. Based only on the event title "
            "and newsletter context (no URL available), infer what this event is likely "
            "about and provide:\n"
            "- what_it_is: your best inference of what this opportunity is\n"
            "- eligibility: likely eligibility based on context\n"
            "- key_dates: any dates mentioned\n"
            "- summary: exactly 1 sentence noting this is inferred from limited info\n\n"
            "Return as a JSON object with those four keys only. No other text."
        )

    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=research_input),
    ])
    content = response.content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    import json
    try:
        research = json.loads(content)
    except Exception:
        research = {
            "what_it_is": content[:300],
            "eligibility": "See original link",
            "key_dates": event.get("date", ""),
            "summary": "Research could not be fully parsed.",
        }

    return {
        "title": event.get("title", ""),
        "date": event.get("date", ""),
        "url": url,
        "what_it_is": research.get("what_it_is", ""),
        "eligibility": research.get("eligibility", ""),
        "key_dates": research.get("key_dates", ""),
        "summary": research.get("summary", ""),
    }


def research_all_events(newsletter_body: str) -> list[dict]:
    """
    Full Step 1 pipeline: extract events from newsletter, research each one.
    Returns list of fully-researched event dicts.
    """
    print("Extracting events from newsletter...")
    events = _extract_events_from_newsletter(newsletter_body)
    print(f"Found {len(events)} events. Researching each...")

    researched = []
    for i, event in enumerate(events, 1):
        print(f"  [{i}/{len(events)}] {event.get('title', 'Unknown')[:60]}")
        researched.append(_research_event(event))

    return researched
