"""
Step 3: Generate a slick branded PDF email for each student.

Visual identity based on Le Lycée Français de San Francisco (softened palette):
  Navy:     #2C5F8F  — medium blue, less aggressive than pure navy
  Burgundy: #A85060  — muted rose-red, replaces harsh bright red
  Gold:     #C4A44A  — warm, lighter gold
  Light bg: #F0F5FA  — very subtle blue-white
  Body text:#3D4A5C  — soft slate, easier on the eye than near-black
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ASSETS_DIR = Path(__file__).parent / "assets"

load_dotenv()

# ── Softened brand palette ────────────────────────────────────────────────────
NAVY      = colors.HexColor("#2C5F8F")   # medium blue
NAVY_DARK = colors.HexColor("#1A3D5C")   # darker navy for banner bg
BURGUNDY  = colors.HexColor("#A85060")   # muted rose-red
GOLD      = colors.HexColor("#C4A44A")   # warm gold
LIGHT     = colors.HexColor("#F0F5FA")   # subtle blue-white
LIGHT2    = colors.HexColor("#E8EFF7")   # slightly deeper for alternating
DARK      = colors.HexColor("#3D4A5C")   # soft slate body text
GRAY      = colors.HexColor("#7B8A9A")   # medium grey for labels
SILVER    = colors.HexColor("#CBD5E0")   # light divider lines
WHITE     = colors.white

OUTPUT_DIR = Path(__file__).parent / "output"

COMPOSE_SYSTEM = """You are writing on behalf of the College Counseling Team at
Le Lycée Français de San Francisco.

Write a warm, professional, personalised email to the student's family.
The email must:
- Open with a personalised greeting using the student's first name.
- Reference 1-2 specific details from the student profile naturally in the opening paragraph.
- Write 2-3 short paragraphs of flowing prose — do NOT list the opportunities here,
  they will be displayed in a separate formatted section below.
- Close warmly, encouraging the student and offering the counseling team's support.
- Tone: warm, encouraging, professional. Feels handcrafted, not templated.
- Do NOT include a subject line, "To:", "From:", or headers — just the body paragraphs.
- Do NOT list or describe individual opportunities — that is handled separately.
"""


def _compose_email_body(student: dict, matched_events: list[dict]) -> str:
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=1024,
    )
    profile = "\n".join(f"  {k}: {v}" for k, v in student.items() if k != "email")
    event_titles = "\n".join(f"  - {e.get('title', '')}" for e in matched_events)
    user_msg = (
        f"STUDENT PROFILE:\n{profile}\n\n"
        f"OPPORTUNITIES BEING HIGHLIGHTED (titles only — do not describe them):\n{event_titles}"
    )
    response = llm.invoke([
        SystemMessage(content=COMPOSE_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    return response.content.strip()


def _make_styles() -> dict:
    return {
        "banner_school": ParagraphStyle(
            "banner_school",
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=WHITE,
            leading=19,
            spaceAfter=2,
        ),
        "banner_sub": ParagraphStyle(
            "banner_sub",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#A8C4D8"),
            leading=12,
        ),
        "banner_date": ParagraphStyle(
            "banner_date",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#A8C4D8"),
            leading=12,
            alignment=TA_LEFT,
        ),
        "profile_name": ParagraphStyle(
            "profile_name",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=NAVY,
            leading=18,
        ),
        "profile_label": ParagraphStyle(
            "profile_label",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=GRAY,
            leading=10,
        ),
        "profile_value": ParagraphStyle(
            "profile_value",
            fontName="Helvetica",
            fontSize=9,
            textColor=DARK,
            leading=12,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=NAVY,
            leading=15,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=10,
            textColor=DARK,
            leading=15,
            spaceAfter=4,
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
            leading=13,
        ),
        "event_why": ParagraphStyle(
            "event_why",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=colors.HexColor("#5A7090"),
            leading=13,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=GRAY,
            leading=11,
            alignment=TA_CENTER,
        ),
        "signature_name": ParagraphStyle(
            "signature_name",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=NAVY,
            leading=14,
        ),
        "signature_title": ParagraphStyle(
            "signature_title",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRAY,
            leading=13,
        ),
    }


def _build_banner(styles, newsletter_date: str) -> list:
    """Navy banner (school name left, CC+date right) + centered logo strip below."""
    today = datetime.now().strftime("%B %d, %Y")

    right_inner = Table(
        [
            [Paragraph("College Counseling", styles["banner_sub"])],
            [Paragraph(today, styles["banner_date"])],
        ],
        colWidths=[2.5 * inch],
    )
    right_inner.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
    ]))

    data = [[
        Paragraph(
            "Le Lycée Français<br/>de San Francisco",
            styles["banner_school"],
        ),
        right_inner,
    ]]
    banner = Table(data, colWidths=[4.5 * inch, 2.5 * inch])
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY_DARK),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (0, -1),  18),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1),  16),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  16),
        ("ALIGN",         (1, 0), (1, -1),   "LEFT"),
    ]))

    # Logo strip — centered on white background between gold lines
    logo_path = ASSETS_DIR / "lycee_logo.png"
    logo_w = 2.1 * inch
    logo_h = logo_w * (246 / 679)
    logo_img = RLImage(str(logo_path), width=logo_w, height=logo_h)
    logo_row = Table([[logo_img]], colWidths=[7 * inch])
    logo_row.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
    ]))

    return [
        banner,
        HRFlowable(width="100%", thickness=2.5, color=GOLD, spaceBefore=0, spaceAfter=0),
        logo_row,
        HRFlowable(width="100%", thickness=1, color=SILVER, spaceBefore=0, spaceAfter=0),
    ]


def _build_student_card(styles, student: dict) -> list:
    """Structured student profile card below the banner."""
    first_name = student["name"].split()[0]
    gpa_str    = str(student.get("gpa", ""))
    grade_str  = f"Grade {student.get('grade', '')}"
    strength   = student.get("academic_strength", "")
    country    = student.get("country_of_birth", "")
    volunteer  = "Yes" if student.get("interested_in_volunteer_work") else "No"

    # Pill row: label on top, value below — 5 equal columns within card inner width
    def pill(label, value):
        return Table(
            [
                [Paragraph(label, styles["profile_label"])],
                [Paragraph(value, styles["profile_value"])],
            ],
            colWidths=[1.28 * inch],
        )

    pills = Table(
        [[
            pill("GRADE", grade_str),
            pill("GPA", gpa_str),
            pill("ACADEMIC FOCUS", strength),
            pill("COUNTRY OF BIRTH", country),
            pill("VOLUNTEER INTEREST", volunteer),
        ]],
        colWidths=[1.28 * inch] * 5,
    )
    pills.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    card_data = [
        [Paragraph(student["name"], styles["profile_name"])],
        [Spacer(1, 4)],
        [pills],
    ]
    card = Table(card_data, colWidths=[7 * inch])
    card.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("LINEBEFORE",    (0, 0), (0, -1),  3, NAVY),
    ]))
    return [card, Spacer(1, 8)]


def _build_email_from(styles, student: dict) -> list:
    """Slim FROM/TO metadata strip."""
    data = [
        [
            Paragraph("FROM", styles["profile_label"]),
            Paragraph(
                "College Counseling Team  &lt;collegecounseling@lelycee.org&gt;",
                styles["profile_value"],
            ),
        ],
        [
            Paragraph("TO", styles["profile_label"]),
            Paragraph(
                f"{student['name']}  &lt;{student['email']}&gt;",
                styles["profile_value"],
            ),
        ],
    ]
    meta = Table(data, colWidths=[0.55 * inch, 6.45 * inch])
    meta.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, SILVER),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F7FAFD")),
    ]))
    return [meta, HRFlowable(width="100%", thickness=1, color=SILVER, spaceAfter=10)]


def _build_personal_note(styles, body_text: str) -> list:
    """Section header + body text in a styled container matching event cards."""
    elements = [
        Paragraph("Personal Note", styles["section_header"]),
        HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=8),
    ]

    # Wrap prose in a light card with left accent — same visual language as event cards
    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
    rows = [[Paragraph(p.replace("\n", "<br/>"), styles["body"])] for p in paragraphs]
    if rows:
        note_card = Table(rows, colWidths=[6.6 * inch])
        note_card.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("LINEBEFORE",    (0, 0), (0, -1),  3, NAVY),
        ]))
        elements.append(note_card)

    elements.append(Spacer(1, 14))
    return elements


def _build_event_cards(styles, matched_events: list[dict]) -> list:
    """Render each matched event as a styled card."""
    elements = []
    if not matched_events:
        return elements

    elements += [
        Paragraph("Highlighted Opportunities For You", styles["section_header"]),
        HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=8),
    ]

    for ev in matched_events:
        title   = ev.get("title", "")
        dates   = ev.get("key_dates", "")
        summary = ev.get("summary", "")
        why     = ev.get("why_relevant", "")
        url     = ev.get("url", "")

        rows = [[Paragraph(title, styles["event_title"])]]
        if dates:
            rows.append([Paragraph(f"Date:  {dates}", styles["event_detail"])])
        if summary:
            rows.append([Paragraph(summary, styles["event_detail"])])
        if why:
            rows.append([Paragraph(f"Why this suits you:  {why}", styles["event_why"])])
        if url:
            rows.append([Paragraph(f"Learn more:  {url}", styles["event_detail"])])

        card = Table(rows, colWidths=[6.6 * inch])
        card.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("LINEBEFORE",    (0, 0), (0, -1),  3, BURGUNDY),
        ]))
        elements.append(card)
        elements.append(Spacer(1, 7))

    return elements


def _build_signature(styles) -> list:
    sig = Table(
        [
            [Paragraph("Warm regards,", styles["body"])],
            [Paragraph("The College Counseling Team", styles["signature_name"])],
            [Paragraph("Le Lycée Français de San Francisco", styles["signature_title"])],
            [Paragraph("collegecounseling@lelycee.org", styles["signature_title"])],
        ],
        colWidths=[7 * inch],
    )
    sig.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 14), sig]


def _build_footer(styles) -> list:
    return [
        Spacer(1, 0.15 * inch),
        HRFlowable(width="100%", thickness=0.75, color=SILVER, spaceAfter=5),
        Paragraph(
            "Le Lycée Français de San Francisco  •  College Counseling Team  •  "
            "collegecounseling@lelycee.org  •  www.lelycee.org",
            styles["footer"],
        ),
        Paragraph(
            "This communication was personalised for you. "
            "Please contact us if you have any questions.",
            styles["footer"],
        ),
    ]


def generate_student_pdf(
    student: dict,
    matched_events: list[dict],
    newsletter_date: str,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """Generate a branded PDF for one student. Returns the path."""
    print(f"  Composing email for {student['name']}...")
    body_text = _compose_email_body(student, matched_events)
    styles = _make_styles()

    safe_name = student["name"].replace(" ", "_")
    pdf_path = output_dir / f"{safe_name}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.65 * inch,
    )

    story = []
    story += _build_banner(styles, newsletter_date)
    story.append(Spacer(1, 8))
    story += _build_student_card(styles, student)
    story += _build_email_from(styles, student)
    story += _build_personal_note(styles, body_text)
    story += _build_event_cards(styles, matched_events)
    story += _build_signature(styles)
    story += _build_footer(styles)

    doc.build(story)
    print(f"    ✓  {pdf_path.name}")
    return pdf_path


def generate_all_pdfs(
    student_matches: list[dict],
    newsletter_date: str,
    output_dir: Path = OUTPUT_DIR,
) -> list[Path]:
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
