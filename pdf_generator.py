"""
Step 3: Generate a slick branded PDF email for each student.

Visual identity based on Le Lycée Français de San Francisco:
  Primary:    #002855  (deep navy)
  Accent:     #C8102E  (French red)
  Gold:       #B8962E  (warm gold for dividers)
  Light bg:   #F4F6F9
  Body text:  #2C2C2C
"""
from __future__ import annotations

import os
import textwrap
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

load_dotenv()

# ── Brand colours ────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#002855")
RED    = colors.HexColor("#C8102E")
GOLD   = colors.HexColor("#B8962E")
LIGHT  = colors.HexColor("#F4F6F9")
DARK   = colors.HexColor("#2C2C2C")
WHITE  = colors.white
GRAY   = colors.HexColor("#6B7280")

OUTPUT_DIR = Path(__file__).parent / "output"

COMPOSE_SYSTEM = """You are writing on behalf of the College Counseling Team at
Le Lycée Français de San Francisco.

Write a warm, professional, personalised email to the student's family.
The email must:
- Open with a personalised greeting using the student's first name.
- Reference 1-2 specific details from the student profile naturally in the opening.
- Present each matched opportunity clearly: name, brief description, why it suits
  this student specifically, and key dates.
- Close warmly, encouraging the student and offering the counseling team's support.
- Tone: warm, encouraging, professional. Not generic.
- Do NOT include a subject line or "To:"/"From:" headers — just the email body text.
- Use line breaks between sections for readability.
"""


def _compose_email_body(student: dict, matched_events: list[dict]) -> str:
    """Ask Claude to write the personalised email body."""
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=2048,
    )
    profile = "\n".join(f"  {k}: {v}" for k, v in student.items() if k != "email")
    import json
    events_text = json.dumps(matched_events, indent=2)
    user_msg = (
        f"STUDENT PROFILE:\n{profile}\n\n"
        f"MATCHED OPPORTUNITIES:\n{events_text}"
    )
    response = llm.invoke([
        SystemMessage(content=COMPOSE_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    return response.content.strip()


def _make_styles():
    base = getSampleStyleSheet()
    return {
        "school_name": ParagraphStyle(
            "school_name",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=WHITE,
            leading=16,
        ),
        "school_sub": ParagraphStyle(
            "school_sub",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#B0C4DE"),
            leading=12,
        ),
        "meta_label": ParagraphStyle(
            "meta_label",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=GRAY,
            leading=11,
        ),
        "meta_value": ParagraphStyle(
            "meta_value",
            fontName="Helvetica",
            fontSize=9,
            textColor=DARK,
            leading=12,
        ),
        "subject_line": ParagraphStyle(
            "subject_line",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=NAVY,
            leading=18,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=10,
            textColor=DARK,
            leading=15,
            spaceAfter=6,
        ),
        "event_title": ParagraphStyle(
            "event_title",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=NAVY,
            leading=14,
        ),
        "event_detail": ParagraphStyle(
            "event_detail",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRAY,
            leading=12,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=GRAY,
            leading=11,
            alignment=TA_CENTER,
        ),
        "signature": ParagraphStyle(
            "signature",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=NAVY,
            leading=14,
        ),
    }


def _build_header(styles, student: dict, newsletter_date: str) -> list:
    """Navy header band with school name + email metadata table."""
    elements = []

    # ── Top navy banner ───────────────────────────────────────────────────────
    header_data = [[
        Paragraph("Le Lycée Français<br/>de San Francisco", styles["school_name"]),
        Paragraph("College Counseling<br/>Newsletter", styles["school_sub"]),
    ]]
    header_table = Table(header_data, colWidths=[3.5 * inch, 3.5 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (0, 0),   16),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 16),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("ALIGN",         (1, 0), (1, 0),   "RIGHT"),
    ]))
    elements.append(header_table)

    # ── Red accent bar ────────────────────────────────────────────────────────
    elements.append(HRFlowable(
        width="100%", thickness=4, color=RED, spaceAfter=0, spaceBefore=0
    ))

    # ── Email metadata band ───────────────────────────────────────────────────
    today = datetime.now().strftime("%B %d, %Y")
    first_name = student["name"].split()[0]
    meta_data = [
        [
            Paragraph("TO", styles["meta_label"]),
            Paragraph(f"{student['name']}  &lt;{student['email']}&gt;", styles["meta_value"]),
            Paragraph("DATE", styles["meta_label"]),
            Paragraph(today, styles["meta_value"]),
        ],
        [
            Paragraph("FROM", styles["meta_label"]),
            Paragraph("College Counseling Team &lt;collegecounseling@lelycee.org&gt;", styles["meta_value"]),
            Paragraph("RE", styles["meta_label"]),
            Paragraph(f"Personalised Opportunities for {first_name}", styles["meta_value"]),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[0.6*inch, 3.1*inch, 0.6*inch, 2.7*inch])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, colors.HexColor("#D1D5DB")),
    ]))
    elements.append(meta_table)
    elements.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=14))

    return elements


def _build_event_cards(styles, matched_events: list[dict]) -> list:
    """Render each matched event as a light-background card."""
    elements = []
    if not matched_events:
        return elements

    elements.append(Paragraph("Highlighted Opportunities For You", styles["subject_line"]))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=10))

    for ev in matched_events:
        title = ev.get("title", "")
        dates = ev.get("key_dates", "")
        summary = ev.get("summary", "")
        why = ev.get("why_relevant", "")
        url = ev.get("url", "")

        card_content = [
            [Paragraph(title, styles["event_title"])],
        ]
        if dates:
            card_content.append([Paragraph(f"📅  {dates}", styles["event_detail"])])
        if summary:
            card_content.append([Paragraph(summary, styles["event_detail"])])
        if why:
            card_content.append([Paragraph(f"<i>Why this matters for you: {why}</i>", styles["event_detail"])])
        if url:
            card_content.append([Paragraph(f"🔗  {url}", styles["event_detail"])])

        card = Table(card_content, colWidths=[6.8 * inch])
        card.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("LINERIGHT",     (0, 0), (0, -1),  3, RED),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT]),
        ]))
        elements.append(card)
        elements.append(Spacer(1, 8))

    return elements


def _build_footer(styles) -> list:
    elements = []
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceBefore=6, spaceAfter=6))
    footer_text = (
        "Le Lycée Français de San Francisco  •  College Counseling Team  •  "
        "collegecounseling@lelycee.org  •  www.lelycee.org"
    )
    elements.append(Paragraph(footer_text, styles["footer"]))
    elements.append(Paragraph(
        "This email was personalised for you. Please reach out if you have any questions.",
        styles["footer"],
    ))
    return elements


def generate_student_pdf(
    student: dict,
    matched_events: list[dict],
    newsletter_date: str,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """Generate a branded PDF email for one student. Returns the PDF path."""
    print(f"  Composing email body for {student['name']}...")
    body_text = _compose_email_body(student, matched_events)
    styles = _make_styles()

    safe_name = student["name"].replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = output_dir / f"{safe_name}_{timestamp}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []
    story += _build_header(styles, student, newsletter_date)
    story.append(Spacer(1, 12))

    # ── Email body ────────────────────────────────────────────────────────────
    for para in body_text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para.replace("\n", "<br/>"), styles["body"]))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 12))

    # ── Event cards ───────────────────────────────────────────────────────────
    story += _build_event_cards(styles, matched_events)

    # ── Signature ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph("Warm regards,", styles["body"]))
    story.append(Paragraph(
        "The College Counseling Team<br/>Le Lycée Français de San Francisco",
        styles["signature"],
    ))

    story += _build_footer(styles)

    doc.build(story)
    print(f"    ✓ PDF saved: {pdf_path.name}")
    return pdf_path


def generate_all_pdfs(
    student_matches: list[dict],
    newsletter_date: str,
    output_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    """Generate one PDF per student. Returns list of PDF paths."""
    paths = []
    for item in student_matches:
        path = generate_student_pdf(
            student=item["student"],
            matched_events=item["matched_events"],
            newsletter_date=newsletter_date,
            output_dir=output_dir,
        )
        paths.append(path)
    return paths
