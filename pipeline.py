"""
LangGraph pipeline — full 3-step workflow:
  1. fetch_email      Pull latest newsletter from Gmail.
  2. parse_email      Clean and structure raw content.
  3. research_events  Extract events/links, fetch pages, Claude researches each.
  4. match_students   Claude matches each student to relevant opportunities.
  5. generate_pdfs    Produce one branded PDF email per student.
  6. save_summary     Write JSON summary of the run to output/.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from email_parser import parse_newsletter
from event_researcher import research_all_events
from gmail_client import extract_raw_content, fetch_latest_newsletter, get_gmail_service
from pdf_generator import generate_all_pdfs
from student_matcher import match_all_students

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"
RECIPIENTS_FILE = Path(__file__).parent / "config" / "recipients.json"


class PipelineState(TypedDict):
    raw_email: dict
    parsed_email: dict
    researched_events: list
    student_matches: list
    pdf_paths: list
    run_dir: str
    error: str


# ── Node 1 ────────────────────────────────────────────────────────────────────
def fetch_email(state: PipelineState) -> PipelineState:
    print("\n[1/5] Fetching newsletter from Gmail...")
    service = get_gmail_service()
    message = fetch_latest_newsletter(service)
    if message is None:
        return {**state, "error": "No matching newsletter found in Gmail."}
    raw = extract_raw_content(message)
    print(f"  Found: '{raw['subject']}' ({raw['date']})")
    return {**state, "raw_email": raw}


# ── Node 2 ────────────────────────────────────────────────────────────────────
def parse_email(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    print("\n[2/5] Parsing newsletter content...")
    parsed = parse_newsletter(state["raw_email"])
    print(f"  Body length: {len(parsed['body'])} characters")
    return {**state, "parsed_email": parsed}


# ── Node 3 ────────────────────────────────────────────────────────────────────
def research_events(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    print("\n[3/5] Researching events and opportunities...")
    events = research_all_events(state["parsed_email"]["body"])
    print(f"  Researched {len(events)} events.")
    return {**state, "researched_events": events}


# ── Node 4 ────────────────────────────────────────────────────────────────────
def match_students(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    print("\n[4/5] Matching students to opportunities...")
    students = json.loads(RECIPIENTS_FILE.read_text())
    matches = match_all_students(students, state["researched_events"])
    for m in matches:
        n = len(m["matched_events"])
        print(f"  {m['student']['name']}: {n} matched event(s)")
    return {**state, "student_matches": matches}


# ── Node 5 ────────────────────────────────────────────────────────────────────
def generate_pdfs(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    print("\n[5/5] Generating PDF emails...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    newsletter_date = state["parsed_email"].get("date", "")
    paths = generate_all_pdfs(state["student_matches"], newsletter_date, run_dir)
    return {**state, "pdf_paths": [str(p) for p in paths], "run_dir": str(run_dir)}


# ── Node 6 ────────────────────────────────────────────────────────────────────
def save_summary(state: PipelineState) -> PipelineState:
    if state.get("error"):
        print(f"\nPipeline error: {state['error']}")
        return state

    run_dir = Path(state["run_dir"])

    # Save full pipeline state for later preview/reuse
    state_data = {
        "parsed_email": state["parsed_email"],
        "researched_events": state["researched_events"],
        "student_matches": state["student_matches"],
    }
    (run_dir / "state.json").write_text(json.dumps(state_data, indent=2))

    summary = {
        "run_at": run_dir.name,
        "newsletter_subject": state["parsed_email"].get("subject", ""),
        "newsletter_date": state["parsed_email"].get("date", ""),
        "events_researched": len(state["researched_events"]),
        "students_processed": len(state["student_matches"]),
        "pdfs_generated": state["pdf_paths"],
        "student_event_counts": {
            m["student"]["name"]: len(m["matched_events"])
            for m in state["student_matches"]
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*60}")
    print(f"Run complete.")
    print(f"  Newsletter : {summary['newsletter_subject']}")
    print(f"  Events     : {summary['events_researched']} researched")
    print(f"  Students   : {summary['students_processed']} processed")
    print(f"  PDFs       : {len(summary['pdfs_generated'])} generated")
    print(f"  Run dir    : {run_dir}")
    print(f"{'='*60}\n")

    return state


# ── Graph ─────────────────────────────────────────────────────────────────────
def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("fetch_email",     fetch_email)
    graph.add_node("parse_email",     parse_email)
    graph.add_node("research_events", research_events)
    graph.add_node("match_students",  match_students)
    graph.add_node("generate_pdfs",   generate_pdfs)
    graph.add_node("save_summary",    save_summary)

    graph.set_entry_point("fetch_email")
    graph.add_edge("fetch_email",     "parse_email")
    graph.add_edge("parse_email",     "research_events")
    graph.add_edge("research_events", "match_students")
    graph.add_edge("match_students",  "generate_pdfs")
    graph.add_edge("generate_pdfs",   "save_summary")
    graph.add_edge("save_summary",    END)

    return graph.compile()


def run():
    pipeline = build_pipeline()
    initial: PipelineState = {
        "raw_email": {},
        "parsed_email": {},
        "researched_events": [],
        "student_matches": [],
        "pdf_paths": [],
        "run_dir": "",
        "error": "",
    }
    return pipeline.invoke(initial)


if __name__ == "__main__":
    run()
