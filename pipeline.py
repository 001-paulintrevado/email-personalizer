"""
LangGraph pipeline: fetch → parse → personalise → save for review.

Graph nodes:
  fetch_email       Pull the latest newsletter from Gmail.
  parse_email       Clean and structure the raw content.
  personalise       Claude generates one tailored email per recipient.
  save_for_review   Write output to disk; nothing is sent yet.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from email_parser import parse_newsletter
from gmail_client import extract_raw_content, fetch_latest_newsletter, get_gmail_service

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"
RECIPIENTS_FILE = Path(__file__).parent / "config" / "recipients.json"

SYSTEM_PROMPT = """You are an expert email writer helping a college counselor personalise a
newsletter for individual families.

You will receive:
1. The original newsletter content.
2. A recipient profile with their name, child's name, and specific characteristics.

Your task:
- Rewrite the newsletter as a warm, personalised email addressed directly to this recipient.
- Reference their specific characteristics naturally where relevant.
- Keep the core information from the newsletter intact.
- Open with a personalised greeting using the recipient's name.
- Close with a warm sign-off from the college counselor.
- Tone: warm, professional, supportive.
- Length: similar to the original newsletter (do not pad or cut excessively).

Return ONLY the email body text — no subject line, no metadata."""


class PipelineState(TypedDict):
    raw_email: dict
    parsed_email: dict
    recipients: list[dict]
    personalised_emails: list[dict]
    output_path: str
    error: str


def fetch_email(state: PipelineState) -> PipelineState:
    service = get_gmail_service()
    message = fetch_latest_newsletter(service)
    if message is None:
        return {**state, "error": "No matching newsletter found in Gmail."}
    raw = extract_raw_content(message)
    return {**state, "raw_email": raw}


def parse_email(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    parsed = parse_newsletter(state["raw_email"])
    return {**state, "parsed_email": parsed}


def personalise(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=2048,
    )

    newsletter = state["parsed_email"]
    recipients = state["recipients"]
    results = []

    for recipient in recipients:
        profile_text = "\n".join(
            f"  {k}: {v}" for k, v in recipient.items() if k != "email"
        )
        user_msg = (
            f"ORIGINAL NEWSLETTER:\n\n{newsletter['body']}\n\n"
            f"RECIPIENT PROFILE:\n{profile_text}"
        )
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        results.append({
            "recipient_name": recipient.get("name", ""),
            "recipient_email": recipient.get("email", ""),
            "subject": f"Re: {newsletter['subject']}",
            "body": response.content,
        })

    return {**state, "personalised_emails": results}


def save_for_review(state: PipelineState) -> PipelineState:
    if state.get("error"):
        print(f"Pipeline error: {state['error']}")
        return state

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUTPUT_DIR / f"review_{timestamp}.json"

    payload = {
        "generated_at": timestamp,
        "source_subject": state["parsed_email"]["subject"],
        "source_date": state["parsed_email"]["date"],
        "emails": state["personalised_emails"],
    }
    out_file.write_text(json.dumps(payload, indent=2))

    readable = out_file.with_suffix(".txt")
    lines = [
        f"Generated: {timestamp}",
        f"Source: {payload['source_subject']} ({payload['source_date']})",
        f"{'='*70}\n",
    ]
    for i, email in enumerate(state["personalised_emails"], 1):
        lines += [
            f"[{i}] TO: {email['recipient_name']} <{email['recipient_email']}>",
            f"SUBJECT: {email['subject']}",
            f"{'-'*70}",
            email["body"],
            f"\n{'='*70}\n",
        ]
    readable.write_text("\n".join(lines))

    print(f"\nReview files saved:\n  {out_file}\n  {readable}")
    return {**state, "output_path": str(out_file)}


def load_recipients() -> list[dict]:
    if not RECIPIENTS_FILE.exists():
        raise FileNotFoundError(f"Recipients file not found: {RECIPIENTS_FILE}")
    return json.loads(RECIPIENTS_FILE.read_text())


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("fetch_email", fetch_email)
    graph.add_node("parse_email", parse_email)
    graph.add_node("personalise", personalise)
    graph.add_node("save_for_review", save_for_review)

    graph.set_entry_point("fetch_email")
    graph.add_edge("fetch_email", "parse_email")
    graph.add_edge("parse_email", "personalise")
    graph.add_edge("personalise", "save_for_review")
    graph.add_edge("save_for_review", END)

    return graph.compile()


def run():
    recipients = load_recipients()
    pipeline = build_pipeline()
    initial_state: PipelineState = {
        "raw_email": {},
        "parsed_email": {},
        "recipients": recipients,
        "personalised_emails": [],
        "output_path": "",
        "error": "",
    }
    final = pipeline.invoke(initial_state)
    return final


if __name__ == "__main__":
    run()
