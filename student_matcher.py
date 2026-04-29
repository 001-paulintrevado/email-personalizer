"""
Step 2: For each student, use Claude to identify which researched events
are genuinely relevant — filtering out events they're ineligible for or
unlikely to engage with based on their profile.
"""
from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

SYSTEM_PROMPT = """You are a college counselor at Le Lycée Français de San Francisco.
You have a list of researched opportunities from the latest newsletter and a student profile.

Your task: identify which opportunities are genuinely worth sending to this student.

Inclusion rules:
- Include only events the student is ELIGIBLE for (grade, GPA, nationality, interests).
- Include only events that match the student's academic strength or stated interests.
- Exclude events that are clearly for a different grade level or eligibility bracket.
- Exclude events the student is very unlikely to engage with given their profile.
- Be thoughtful: a student interested in volunteer work should see service opportunities;
  a science-focused student should see STEM programs, etc.

Return a JSON array of matched opportunities. Each element must have:
  "title": the event title
  "why_relevant": one sentence explaining why this is a good match for this student
  "key_dates": the key dates to highlight
  "summary": the 2-sentence summary of the opportunity
  "url": the URL (empty string if none)

Return ONLY the JSON array, no other text."""


def match_student_to_events(student: dict, events: list[dict]) -> list[dict]:
    """
    Returns the subset of events relevant to this student, with a relevance note.
    """
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4096,
    )

    profile_text = "\n".join(f"  {k}: {v}" for k, v in student.items() if k != "email")
    events_text = json.dumps(events, indent=2)

    user_msg = (
        f"STUDENT PROFILE:\n{profile_text}\n\n"
        f"RESEARCHED OPPORTUNITIES:\n{events_text}"
    )

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])

    content = response.content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            last_bracket = content.rfind("},")
            if last_bracket > 0:
                content = content[: last_bracket + 1] + "\n]"
            return json.loads(content)
        except Exception:
            return []


def match_all_students(students: list[dict], events: list[dict]) -> list[dict]:
    """
    Returns a list of dicts: one per student, containing the student profile
    and their matched opportunities.
    """
    results = []
    for i, student in enumerate(students, 1):
        print(f"  [{i}/{len(students)}] Matching: {student['name']}")
        matched = match_student_to_events(student, events)
        results.append({
            "student": student,
            "matched_events": matched,
        })
    return results
