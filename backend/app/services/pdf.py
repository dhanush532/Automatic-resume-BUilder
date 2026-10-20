from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("ResumeSans", str(FONT_DIRECTORY / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ResumeSansBold", str(FONT_DIRECTORY / "VeraBd.ttf")))


def _display(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def resume_lines(snapshot: dict[str, Any], template_key: str) -> list[str]:
    if snapshot.get("source") == "document_import":
        return str(snapshot.get("imported_text", "")).splitlines()
    hidden = set(snapshot.get("resume_meta", {}).get("hidden_sections", []))
    lines = [f"Template: {template_key}"]
    profile = snapshot.get("profile", {})
    if "profile" not in hidden:
        lines.extend([_display(profile.get("full_name")) or "Career Passport", _display(profile.get("headline"))])
        contact = " · ".join(filter(None, [_display(profile.get("email")), _display(profile.get("location")), _display(profile.get("linkedin_url")), _display(profile.get("github_url")), _display(profile.get("portfolio_url"))]))
        if contact:
            lines.append(contact)
        if profile.get("bio"):
            lines.extend(["Summary", _display(profile["bio"])])

    section_labels = {
        "professional_links": "Links",
        "experience": "Experience",
        "projects": "Projects",
        "education": "Education",
        "skills": "Skills",
        "certifications": "Certifications",
        "courses": "Courses & training",
        "achievements": "Achievements",
        "languages": "Languages",
        "open_source_contributions": "Open-source contributions",
    }
    order = snapshot.get("resume_meta", {}).get("section_order") or list(section_labels)
    for section in order:
        if section in hidden or section not in section_labels:
            continue
        records = snapshot.get(section)
        if not records:
            continue
        lines.append(section_labels[section])
        if section == "skills":
            lines.extend(f"{_display(item.get('name'))} — {_display(item.get('proficiency'))}" for item in records)
        elif section == "experience":
            for item in records:
                dates = " – ".join(filter(None, [_display(item.get("start_date")), _display(item.get("end_date"))])) or ""
                lines.append(f"{_display(item.get('title'))} · {_display(item.get('company'))} {dates}".strip())
                for field in ("description", "achievements", "technology_notes"):
                    if item.get(field):
                        lines.append(_display(item[field]))
        elif section == "projects":
            for item in records:
                lines.append(_display(item.get("name")))
                for field in ("description", "results", "technology_notes", "github_url", "live_url"):
                    if item.get(field):
                        lines.append(_display(item[field]))
        elif section == "education":
            lines.extend(f"{_display(item.get('degree'))} · {_display(item.get('institution'))}" for item in records)
        elif section == "professional_links":
            lines.extend(f"{_display(item.get('label'))}: {_display(item.get('url'))}" for item in records)
        elif section == "certifications":
            lines.extend(f"{_display(item.get('name'))} · {_display(item.get('issuer'))}" for item in records)
        elif section == "courses":
            lines.extend(f"{_display(item.get('name'))} · {_display(item.get('provider'))}" for item in records)
        elif section == "achievements":
            lines.extend(f"{_display(item.get('title'))} · {_display(item.get('organization'))}" for item in records)
        elif section == "languages":
            lines.extend(f"{_display(item.get('language'))} — {_display(item.get('proficiency'))}" for item in records)
        elif section == "open_source_contributions":
            lines.extend(f"{_display(item.get('repository'))} · {_display(item.get('contribution'))}" for item in records)
        lines.append("")
    return [line for line in lines if line is not None]


def render_preview_html(snapshot: dict[str, Any], template_key: str) -> str:
    lines = resume_lines(snapshot, template_key)
    title = escape(_display(snapshot.get("profile", {}).get("full_name")) or "Resume")
    themes = {
        "modern": ("Arial, sans-serif", "#3456c4", "#f4f6ff"),
        "professional": ("Georgia, serif", "#243247", "#f7f7f5"),
        "minimal": ("Arial, sans-serif", "#202020", "#ffffff"),
        "student": ("Arial, sans-serif", "#13795b", "#f2fbf7"),
        "developer": ("ui-monospace, SFMono-Regular, monospace", "#155e75", "#f0f9ff"),
        "creative": ("Trebuchet MS, sans-serif", "#8b3d77", "#fff5fb"),
        "ats_readable": ("Arial, sans-serif", "#111827", "#ffffff"),
    }
    font, accent, background = themes.get(template_key, themes["ats_readable"])
    section_names = {"Links", "Experience", "Projects", "Education", "Skills", "Certifications", "Courses & training", "Achievements", "Languages", "Open-source contributions"}
    if snapshot.get("source") == "document_import":
        body = f'<pre style="white-space:pre-wrap;overflow-wrap:anywhere;font:inherit">{escape(str(snapshot.get("imported_text", "")))}</pre>'
    else:
        body = "\n".join(
            f"<p class=\"{'title' if index == 1 else 'subtitle' if index == 2 else 'section' if line in section_names else 'body'}\">{escape(line)}</p>" if line else "<div class=\"spacer\"></div>"
            for index, line in enumerate(lines)
        )
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>{title}</title><style>
    @page {{ size: A4; margin: 18mm; }} body {{ font-family: {font}; color: #16213e; background: {background}; max-width: 800px; margin: 0 auto; line-height: 1.45; }}
    p {{ margin: 0 0 7px; }} .title {{ font-size: 28px; font-weight: 700; }} .subtitle {{ font-size: 17px; color: {accent}; }} .section {{ margin-top: 18px; border-bottom: 2px solid {accent}; color: {accent}; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }} .body {{ font-size: 11px; }}
    .spacer {{ height: 8px; }}
    </style></head><body data-template=\"{escape(template_key)}\">{body}</body></html>"""


def render_pdf(snapshot: dict[str, Any], template_key: str) -> bytes:
    """Create searchable, paginated PDFs with embedded fonts and real text wrapping."""
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=(595, 842), leftMargin=50, rightMargin=50,
                                 topMargin=48, bottomMargin=48, pageCompression=0, invariant=1,
                                 title="Resume", author="", creator="CareerPilot")
    accent = {"modern": "#3456c4", "student": "#13795b", "developer": "#155e75", "creative": "#8b3d77"}.get(template_key, "#243247")
    body = ParagraphStyle("body", fontName="ResumeSans", fontSize=10, leading=15, spaceAfter=5, alignment=TA_LEFT, splitLongWords=True)
    title = ParagraphStyle("title", parent=body, fontName="ResumeSansBold", fontSize=22, leading=29, spaceAfter=12)
    heading = ParagraphStyle("heading", parent=body, fontName="ResumeSansBold", fontSize=11, textColor=HexColor(accent), spaceBefore=14, spaceAfter=7, keepWithNext=True)
    section_names = {"links", "summary", "profile", "objective", "experience", "work experience", "professional experience", "projects", "education", "skills", "technical skills", "certifications", "courses & training", "achievements", "languages", "open-source contributions"}
    lines = resume_lines(snapshot, template_key)
    if snapshot.get("source") != "document_import":
        lines = lines[1:]  # Internal template identifiers do not belong in an application.
    story = []
    for index, line in enumerate(lines):
        style = title if index == 0 else heading if line.strip().lower() in section_names else body
        if not line.strip():
            story.append(Spacer(1, 5))
            continue
        story.append(Paragraph(escape(line), style))
    document.build(story or [Paragraph("Resume", title)])
    return output.getvalue()
