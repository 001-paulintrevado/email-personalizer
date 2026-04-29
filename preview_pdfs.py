"""
Generate PDFs for a subset of students using saved state from a previous run.

Usage:
  python preview_pdfs.py                   # 2 students, most recent run's state
  python preview_pdfs.py 3                 # 3 students, most recent run's state
  python preview_pdfs.py 2 --demo          # 2 students, built-in demo data (no prior run needed)
  python preview_pdfs.py 2 output/run_X/   # 2 students, specific run directory

When a run_dir/state.json exists, students are taken from the beginning of the
matched list in that file. Use --demo to quickly preview the PDF layout without
a prior pipeline run.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from pdf_generator import generate_student_pdf

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"
RECIPIENTS_FILE = Path(__file__).parent / "config" / "recipients.json"


# ── Demo data ─────────────────────────────────────────────────────────────────

DEMO_EVENTS = [
    {
        "title": "Stanford Summer Research Program in Biomedical Sciences",
        "key_dates": "Application deadline: April 15, 2026; Program: June 22 – August 2, 2026",
        "summary": (
            "Stanford's eight-week immersive research program pairs high-school juniors "
            "and seniors with faculty mentors in biomedical labs. Students complete an "
            "independent project, present findings at a symposium, and receive a certificate "
            "of completion from the School of Medicine."
        ),
        "why_relevant": (
            "Strong match for your Pure Sciences focus and GPA; the biomedical track aligns "
            "directly with your stated interest in life sciences."
        ),
        "url": "https://med.stanford.edu/surbp",
    },
    {
        "title": "Bay Area Science Fair – Senior Division",
        "key_dates": "Registration: March 28; Project submission: April 18; Fair: May 3, 2026",
        "summary": (
            "The regional qualifier for the International Science and Engineering Fair welcomes "
            "students in grades 9-12 with original research projects across 22 STEM categories. "
            "Top finishers earn scholarships and automatic ISEF invitations."
        ),
        "why_relevant": (
            "Your academic strength in Pure Sciences and solid GPA make you a competitive "
            "entrant, especially in the Biology or Chemistry categories."
        ),
        "url": "https://www.bayareasciencefair.org",
    },
    {
        "title": "Lycée Alumni Volunteer Mentorship Programme",
        "key_dates": "Rolling applications; next cohort orientation: April 28, 2026",
        "summary": (
            "Current Lycée students are paired with alumni working in STEM, law, and the arts "
            "for a semester-long mentorship. Participants meet bi-weekly and attend two "
            "career-exploration panels hosted on campus."
        ),
        "why_relevant": (
            "Given your strong interest in volunteer and community work, this programme offers "
            "meaningful mentorship while giving back to the Lycée community."
        ),
        "url": "",
    },
]

DEMO_EVENTS_2 = [
    {
        "title": "Harvard Model United Nations (HMUN) 2026",
        "key_dates": "Application deadline: May 10, 2026; Conference: January 22-25, 2027",
        "summary": (
            "HMUN is one of the world's largest MUN conferences, hosted annually in Boston. "
            "Delegates debate international resolutions, draft position papers, and develop "
            "public-speaking and negotiation skills over four days."
        ),
        "why_relevant": (
            "Your Social Sciences academic focus and interest in global affairs make HMUN "
            "an exceptional fit for building the analytical and rhetorical skills top colleges value."
        ),
        "url": "https://www.hmun.org",
    },
    {
        "title": "UC Berkeley Pre-Law Institute",
        "key_dates": "Applications open April 1; Deadline May 30; Program: July 7-18, 2026",
        "summary": (
            "A two-week residential programme exposing high-school students to constitutional "
            "law, moot court, and legal research at Boalt Hall. Alumni have gone on to attend "
            "Yale Law, Harvard Law, and Stanford Law."
        ),
        "why_relevant": (
            "With Social Sciences as your academic core and an interest in pursuing law or "
            "policy, this programme provides a rigorous early introduction to legal thinking."
        ),
        "url": "https://prelaw.berkeley.edu",
    },
    {
        "title": "San Francisco Youth Climate Action Summit",
        "key_dates": "Registration deadline: April 20, 2026; Summit: May 9, 2026",
        "summary": (
            "A one-day city-wide summit where student delegates from SF high schools propose "
            "climate policy recommendations to the Mayor's Office of Sustainability. "
            "Delegates gain hands-on experience in civic advocacy and environmental policy."
        ),
        "why_relevant": (
            "Your Social Sciences focus and GPA reflect the analytical capabilities this "
            "summit demands; participation demonstrates civic engagement for college applications."
        ),
        "url": "https://sfenvironment.org/youth-summit",
    },
]


def _demo_matches() -> list[dict]:
    students = json.loads(RECIPIENTS_FILE.read_text())
    return [
        {"student": students[0], "matched_events": DEMO_EVENTS},   # Emma Thornton
        {"student": students[1], "matched_events": DEMO_EVENTS_2},  # Lucas Beaumont
    ]


# ── Loader ────────────────────────────────────────────────────────────────────

def _find_latest_run_dir() -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    run_dirs = sorted(
        [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")],
        reverse=True,
    )
    for d in run_dirs:
        if (d / "state.json").exists():
            return d
    return None


def _load_matches_from_run(run_dir: Path, n: int) -> list[dict]:
    state = json.loads((run_dir / "state.json").read_text())
    return state["student_matches"][:n]


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    use_demo = "--demo" in args
    args = [a for a in args if a != "--demo"]

    n = int(args[0]) if args else 2
    specified_dir = Path(args[1]) if len(args) >= 2 else None

    newsletter_date = "Preview Run"
    student_matches: list[dict] = []

    if use_demo:
        print("[preview] Using built-in demo data.")
        student_matches = _demo_matches()[:n]
    elif specified_dir:
        state_path = specified_dir / "state.json"
        if not state_path.exists():
            print(f"[preview] ERROR: {state_path} not found.")
            sys.exit(1)
        state = json.loads(state_path.read_text())
        student_matches = state["student_matches"][:n]
        newsletter_date = state.get("parsed_email", {}).get("date", "")
        print(f"[preview] Loaded state from {specified_dir}")
    else:
        run_dir = _find_latest_run_dir()
        if run_dir:
            student_matches = _load_matches_from_run(run_dir, n)
            state = json.loads((run_dir / "state.json").read_text())
            newsletter_date = state.get("parsed_email", {}).get("date", "")
            print(f"[preview] Loaded state from {run_dir}")
        else:
            print("[preview] No saved run state found — falling back to demo data.")
            print("[preview] Run the full pipeline first, or pass --demo to use demo data.")
            student_matches = _demo_matches()[:n]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_dir = OUTPUT_DIR / f"preview_{timestamp}"
    preview_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating {len(student_matches)} preview PDF(s) → {preview_dir}\n")
    for item in student_matches:
        generate_student_pdf(
            student=item["student"],
            matched_events=item["matched_events"],
            newsletter_date=newsletter_date,
            output_dir=preview_dir,
        )

    print(f"\nDone. PDFs are in: {preview_dir}")


if __name__ == "__main__":
    main()
