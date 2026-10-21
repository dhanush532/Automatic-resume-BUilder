from __future__ import annotations

import re
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import reportlab
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.resume_themes import theme_for

FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("ResumeSans", str(FONT_DIRECTORY / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ResumeSansBold", str(FONT_DIRECTORY / "VeraBd.ttf")))

PAGE_WIDTH, PAGE_HEIGHT = A4
FAMILIES = {"sans": ("ResumeSans", "ResumeSansBold"), "serif": ("Times-Roman", "Times-Bold"), "mono": ("Courier", "Courier-Bold")}
FONT_STACKS = {"sans": '"Helvetica Neue", Arial, sans-serif', "serif": 'Georgia, "Times New Roman", serif', "mono": 'ui-monospace, SFMono-Regular, Menlo, monospace'}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MUTED = "#4b5563"

SECTION_LABELS = {
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
RAIL_SECTIONS = ("professional_links", "skills", "education", "certifications", "courses", "languages")
BULLET_SECTIONS = frozenset({"experience", "projects", "achievements", "open_source_contributions"})


def _display(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _split_lines(value: Any) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in str(value).splitlines() if part.strip()]


def _dates(item: dict[str, Any]) -> str:
    def formatted(value):
        text = _display(value)
        match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", text)
        if match and 1 <= int(match[2]) <= 12:
            return f"{('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[int(match[2]) - 1]} {match[1]}"
        return text
    return " – ".join(part for part in (formatted(item.get("start_date")), "Present" if item.get("is_current") else formatted(item.get("end_date"))) if part)


def _unique_lines(lines):
    seen = set()
    result = []
    for line in lines:
        line = re.sub(r"^(?:[•▪*]+\s*|-\s+)", "", line.strip()).strip()
        normalized = re.sub(r"\s+", " ", line).casefold()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(line)
    return result


def _section_entries(key: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if key in {"skills", "languages"}:
        name_field, level_field = ("name", "proficiency") if key == "skills" else ("language", "proficiency")
        lines = []
        for item in records:
            name, level = _display(item.get(name_field)), _display(item.get(level_field))
            lines.append(f"{name} — {level}" if name and level else name or level)
        return [{"lead": None, "lines": [" · ".join(_unique_lines(lines))], "dates": "", "details": [], "links": []}] if lines else []
    if key == "professional_links":
        lines = [f"{_display(item.get('label'))}: {_display(item.get('url'))}" for item in records]
        return [{"lead": None, "lines": _unique_lines(lines), "dates": "", "details": [], "links": []}] if lines else []
    for item in records:
        dates = ""
        details = []
        links = []
        if key == "experience":
            lead = " · ".join(part for part in (_display(item.get("title")), _display(item.get("company"))) if part)
            dates = _dates(item)
            lines = [line for field in ("description", "achievements") for line in _split_lines(item.get(field))]
            details = _split_lines(item.get("location"))
        elif key == "projects":
            lead = _display(item.get("name"))
            dates = _dates(item)
            lines = [line for field in ("description", "features", "problem_solved", "results") for line in _split_lines(item.get(field))]
            details = _split_lines(item.get("role"))
            links = [item[field] for field in ("github_url", "live_url") if item.get(field)]
        elif key == "education":
            lead = " · ".join(part for part in (_display(item.get("degree")), _display(item.get("institution"))) if part)
            dates = _dates(item)
            lines = [line for field in ("field_of_study", "description", "achievements") for line in _split_lines(item.get(field))]
            if item.get("grade"):
                lines.append("Grade: " + _display(item["grade"]))
            if item.get("coursework"):
                lines.append("Coursework: " + _display(item["coursework"]))
        elif key == "certifications":
            lead = " · ".join(part for part in (_display(item.get("name")), _display(item.get("issuer"))) if part)
            dates = " · ".join(part for part in (_display(item.get("issue_date")), _display(item.get("expiry_date"))) if part)
            lines = _split_lines(item.get("description"))
            if item.get("credential_id"):
                details.append("Credential: " + _display(item["credential_id"]))
            links = [item["credential_url"]] if item.get("credential_url") else []
        elif key == "courses":
            lead = " · ".join(part for part in (_display(item.get("name")), _display(item.get("provider"))) if part)
            done = _display(item.get("completion_date"))
            dates = done
            lines = _split_lines(item.get("description"))
            links = [item["credential_url"]] if item.get("credential_url") else []
        elif key == "achievements":
            lead = " · ".join(part for part in (_display(item.get("title")), _display(item.get("organization"))) if part)
            when = _display(item.get("achieved_on"))
            dates = when
            lines = _split_lines(item.get("description"))
            links = [item["evidence_url"]] if item.get("evidence_url") else []
        else:  # open_source_contributions
            lead = " · ".join(part for part in (_display(item.get("repository")), _display(item.get("contribution"))) if part)
            dates = _dates(item)
            lines = _split_lines(item.get("description"))
            links = [item["url"]] if item.get("url") else []
        if item.get("technology_notes"):
            details.append("Technologies: " + _display(item["technology_notes"]))
        if lead or lines:
            entries.append({"lead": lead or None, "lines": _unique_lines(lines), "dates": dates, "details": _unique_lines(details), "links": list(dict.fromkeys(links))})
    return entries


def resume_content(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Structured, layout-agnostic resume content shared by previews and PDFs."""
    if snapshot.get("source") == "document_import":
        return {"imported": True, "text": str(snapshot.get("imported_text") or ""), "header": {"name": "", "headline": "", "contact": []}, "sections": []}
    profile = snapshot.get("profile") or {}
    meta = snapshot.get("resume_meta") or {}
    hidden = set(meta.get("hidden_sections") or [])
    visible = "profile" not in hidden
    contact = [_display(profile.get(field)) for field in ("email", "location", "linkedin_url", "github_url", "portfolio_url")] if visible else []
    header = {
        "name": _display(profile.get("full_name") or "Career Passport") if visible else "",
        "headline": _display(profile.get("headline")) if visible else "",
        "contact": [value for value in contact if value],
    }
    sections: list[dict[str, Any]] = []
    bio = _split_lines(profile.get("bio")) if visible else []
    if bio:
        sections.append({"key": "summary", "label": "Summary", "entries": [{"lead": None, "lines": bio}]})
    order = list(dict.fromkeys(meta.get("section_order") or list(SECTION_LABELS)))
    for key in order:
        if key in hidden or key not in SECTION_LABELS:
            continue
        records = snapshot.get(key)
        if not isinstance(records, list) or not records:
            continue
        entries = _section_entries(key, [item for item in records if isinstance(item, dict)])
        if entries:
            sections.append({"key": key, "label": SECTION_LABELS[key], "entries": entries})
    return {"imported": False, "text": "", "header": header, "sections": sections}


def _mix(color: str, amount: float) -> str:
    value = color.lstrip("#")
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))

    def channel(current: int) -> int:
        return round(current + (255 - current) * amount)

    return f"#{channel(red):02x}{channel(green):02x}{channel(blue):02x}"


def design_tokens(snapshot: dict[str, Any], template_key: str) -> dict[str, Any]:
    theme = theme_for(template_key)
    design = ((snapshot.get("resume_meta") or {}).get("design")) or {}
    if not isinstance(design, dict):
        design = {}
    accent = design.get("accent")
    if not isinstance(accent, str) or not HEX.match(accent):
        accent = theme["accent"]
    family = design.get("font")
    if family not in ("sans", "serif", "mono"):
        family = theme["font"]
    spacing = design.get("spacing") if design.get("spacing") in ("compact", "comfortable") else "comfortable"
    try:
        margin = int(design.get("margin_mm") or 17)
    except (TypeError, ValueError):
        margin = 17
    margin = max(12, min(25, margin))
    layout = theme["layout"]
    ink = {"plain": "#111827", "editorial": "#2b2531"}.get(layout, "#16213e")
    return {"key": template_key, "layout": layout, "name": theme["name"], "accent": accent, "tint": _mix(accent, 0.88),
            "hair": _mix(accent, 0.72), "ink": ink, "muted": MUTED, "family": family, "spacing": spacing,
            "compact": spacing == "compact", "margin_mm": margin, "ats_safe": theme["ats_safe"]}


# ---------------------------------------------------------------- HTML preview

def _mast_html(header: dict[str, Any], variant: str) -> str:
    name, headline = header.get("name") or "", header.get("headline") or ""
    contact = " · ".join(header["contact"])
    if not name and not headline:
        return ""
    name_html = f"<h1>{escape(name)}</h1>" if name else ""
    headline_html = f'<p class="headline">{escape(headline)}</p>' if headline else ""
    contact_html = f'<p class="contact">{escape(contact)}</p>' if contact else ""
    if variant == "band":
        return f'<header class="mast"><div class="namebar">{name_html}</div><div class="infobar">{headline_html}{contact_html}</div></header>'
    if variant == "ribbon":
        return f'<header class="mast"><div class="ribbon">{name_html}{headline_html}</div>{contact_html}</header>'
    if variant == "side":
        return f"<header class=\"mast\">{name_html}{headline_html}</header>"
    return f"<header class=\"mast\">{name_html}{headline_html}{contact_html}</header>"


def _section_html(section: dict[str, Any]) -> str:
    bullet = section["key"] in BULLET_SECTIONS
    entries = []
    for entry in section["entries"]:
        parts = []
        if entry["lead"]:
            parts.append(f'<p class="lead">{escape(entry["lead"])}</p>')
        if entry.get("dates"):
            parts.append(f'<p class="metadata">{escape(entry["dates"])}</p>')
        for line in entry["lines"]:
            parts.append(f'<p class="line{" bullet" if bullet else ""}">{escape(line)}</p>')
        for line in entry.get("details", []) + entry.get("links", []):
            parts.append(f'<p class="metadata">{escape(line)}</p>')
        entries.append(f'<div class="entry">{" ".join(parts)}</div>')
    return f'<section class="rsec" data-section="{escape(section["key"])}"><h2>{escape(section["label"])}</h2><div class="entries">{" ".join(entries)}</div></section>'


def _html_body(content: dict[str, Any], tokens: dict[str, Any]) -> str:
    layout = tokens["layout"]
    header, sections = content["header"], content["sections"]
    if layout == "sidebar":
        rail = [s for s in sections if s["key"] in RAIL_SECTIONS]
        main = [s for s in sections if s["key"] not in RAIL_SECTIONS]
        contact = " · ".join(escape(value) for value in header["contact"])
        rail_html = (f'<p class="contact">{contact}</p>' if contact else "") + " ".join(_section_html(s) for s in rail)
        return f'{_mast_html(header, "side")}<div class="cols"><aside class="rail">{rail_html}</aside><div class="main">{" ".join(_section_html(s) for s in main)}</div></div>'
    variant = {"banded": "band", "balanced": "ribbon"}.get(layout)
    return f'{_mast_html(header, variant)}<div class="doc">{" ".join(_section_html(s) for s in sections)}</div>'


CSS_TEMPLATE = """
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:#eceee9;font-family:__FONT__;color:__INK__;font-size:10.5px;line-height:1.5}
.sheet{background:#fff;width:210mm;margin:20px auto;padding:__PAD__mm;box-shadow:0 12px 32px rgba(18,28,24,.14);min-height:297mm}
h1,h2,p{margin:0;font-weight:inherit}h1,.lead,h2,.line.bullet:before{font-weight:700}
.mast{padding-bottom:12px;margin-bottom:__SGAP__px}
.mast h1{font-size:26px;line-height:1.15;letter-spacing:-.01em}
.mast .headline{font-size:13px;color:__ACCENT__;margin-top:5px;font-weight:600}
.mast .contact{font-size:9.5px;color:__MUTED__;margin-top:7px}
.rsec{margin-top:__SGAP__px}
.rsec h2{font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:__ACCENT__;padding-bottom:4px;border-bottom:1px solid __HAIR__}
.entries{margin-top:6px}
.lead{font-size:11px;margin-top:7px}
.metadata{font-size:9.5px;line-height:1.45;color:__MUTED__;margin-top:3px;overflow-wrap:anywhere}
.line{margin-top:3px;font-size:10.3px;overflow-wrap:anywhere}
.line.bullet{padding-left:13px;position:relative}
.line.bullet:before{content:"\2022";position:absolute;left:0;top:0;color:__ACCENT__}
pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:10.3px}
__EXTRA__
"""


def _html_css(tokens: dict[str, Any]) -> str:
    layout = tokens["layout"]
    extra = {
        "centered": ".mast{text-align:center;border-bottom:1px solid __INK__;padding-bottom:14px}.mast h1{font-size:30px}.rsec h2{text-align:center}",
        "banded": ".namebar{background:__ACCENT__;color:#fff;padding:10px 14px}.mast .namebar h1{font-size:24px}.infobar{background:__TINT__;padding:8px 14px 9px}.mast .headline{color:__INK__;margin-top:0}.mast .infobar .contact{margin-top:4px}.rsec h2{background:__TINT__;border-bottom:none;padding:5px 9px;color:__INK__}",
        "plain": ".mast{border-bottom:1px solid __INK__;padding-bottom:10px}.mast h1{font-size:22px}.mast .headline{color:__MUTED__}.rsec h2{color:__INK__;border-bottom:1px solid __INK__;letter-spacing:.06em}.line.bullet{padding-left:0}.line.bullet:before{content:none}",
        "editorial": ".mast{border-bottom:1px solid __HAIR__;padding-bottom:12px}.mast h1{font-size:30px}.rsec{display:grid;grid-template-columns:92px minmax(0,1fr);column-gap:16px;align-items:start}.rsec h2{grid-column:1;border-bottom:none;padding:5px 0 0;font-size:9.5px;letter-spacing:.14em}.entries{grid-column:2;border-left:1px solid __HAIR__;padding-left:15px;margin-top:0}",
        "sidebar": ".mast{border-bottom:1px solid __HAIR__;padding-bottom:10px}.mast h1{font-size:27px}.cols{display:grid;grid-template-columns:minmax(0,30%) minmax(0,1fr);gap:18px;align-items:start}.rail{background:__TINT__;padding:12px 13px 14px}.rail .contact{font-size:9.3px;color:__INK__;margin-top:0;line-height:1.6}.rail .rsec{margin-top:12px}.rail .rsec:first-of-type{margin-top:0}.rail .rsec h2{border-bottom:none;padding:0;font-size:9.5px}.rail .entries{margin-top:4px}.rail .line{font-size:9.3px;margin-top:2px}.rail .lead{font-size:9.5px;margin-top:4px}.main .rsec{margin-top:14px}.main .rsec:first-child{margin-top:0}",
        "balanced": ".ribbon{background:__ACCENT__;color:#fff;padding:16px 18px}.mast .ribbon h1{font-size:27px}.mast .ribbon .headline{color:#fff;margin-top:6px;font-weight:600}.mast>.contact{color:__ACCENT__;font-weight:600;margin-top:9px}.rsec{margin-top:calc(__SGAP__px + 4px)}.rsec h2{background:__ACCENT__;color:#fff;border-bottom:none;padding:5px 10px;letter-spacing:.1em}",
    }.get(layout, "")
    css = CSS_TEMPLATE.replace("__EXTRA__", extra)
    for token, value in (("__FONT__", FONT_STACKS[tokens["family"]]), ("__INK__", tokens["ink"]), ("__ACCENT__", tokens["accent"]),
                         ("__TINT__", tokens["tint"]), ("__HAIR__", tokens["hair"]), ("__MUTED__", tokens["muted"]),
                         ("__PAD__", str(tokens["margin_mm"])), ("__SGAP__", "9" if tokens["compact"] else "16")):
        css = css.replace(token, value)
    return css


def render_preview_html(snapshot: dict[str, Any], template_key: str) -> str:
    content = resume_content(snapshot)
    tokens = design_tokens(snapshot, template_key)
    body = f'<div class="doc"><pre>{escape(content["text"])}</pre></div>' if content["imported"] else _html_body(content, tokens)
    title = escape(content["header"]["name"] or "Resume")
    css = _html_css(tokens)
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f"<title>{title}</title><style>{css}</style></head>"
            f"<body class=\"theme-{tokens['layout']}\" data-template=\"{escape(tokens['key'])}\" data-layout=\"{tokens['layout']}\">"
            f'<div class="sheet">{body}</div></body></html>')


# ---------------------------------------------------------------- PDF export

def _styles(tokens: dict[str, Any]) -> dict[str, ParagraphStyle]:
    regular, bold = FAMILIES[tokens["family"]]
    ink = HexColor(tokens["ink"])
    accent = HexColor(tokens["accent"])
    hair = HexColor(tokens["hair"])
    muted = HexColor(tokens["muted"])
    compact = tokens["compact"]
    body_size = 9.6 if compact else 10
    body_lead = 13 if compact else 14.5
    space_after = 2.5 if compact else 3.5
    sgap = 9 if compact else 16
    body = ParagraphStyle("rbody", fontName=regular, fontSize=body_size, leading=body_lead, textColor=ink, spaceAfter=space_after,
                          alignment=TA_LEFT, splitLongWords=True, allowWidows=0, allowOrphans=0, bulletFontName="ResumeSans", bulletFontSize=body_size, bulletColor=accent)
    return {
        "body": body,
        "bullet": ParagraphStyle("rbullet", parent=body, leftIndent=13, bulletIndent=2),
        "lead": ParagraphStyle("rlead", parent=body, fontName=bold, fontSize=body_size + 0.4, leading=body_lead + 1.5, spaceBefore=7, spaceAfter=3, keepWithNext=1),
        "metadata": ParagraphStyle("rmeta", parent=body, fontSize=9, leading=12.5, textColor=muted, spaceAfter=4),
        "sgap": sgap,
        "name": ParagraphStyle("rname", parent=body, fontName=bold, fontSize=21, leading=25, spaceAfter=3),
        "name_center": ParagraphStyle("rnamec", parent=body, fontName=bold, fontSize=23, leading=27, spaceAfter=4, alignment=TA_CENTER),
        "sub": ParagraphStyle("rsub", parent=body, fontSize=12.5, leading=16, textColor=accent, spaceAfter=2),
        "sub_center": ParagraphStyle("rsubc", parent=body, fontSize=12.5, leading=16, textColor=accent, spaceAfter=3, alignment=TA_CENTER),
        "contact": ParagraphStyle("rcontact", parent=body, fontSize=9, leading=12.5, textColor=muted),
        "contact_center": ParagraphStyle("rcontactc", parent=body, fontSize=9, leading=12.5, textColor=muted, alignment=TA_CENTER),
        "contact_accent": ParagraphStyle("rcontacta", parent=body, fontSize=9.5, leading=13, textColor=accent, spaceBefore=8),
        "band_name": ParagraphStyle("rbandn", parent=body, fontName=bold, fontSize=20, leading=24, textColor=white, spaceAfter=0),
        "band_headline": ParagraphStyle("rbandh", parent=body, fontSize=12, leading=15, textColor=ink, spaceAfter=0),
        "band_contact": ParagraphStyle("rbandc", parent=body, fontSize=8.5, leading=11, textColor=HexColor(MUTED), spaceAfter=0),
        "ribbon_name": ParagraphStyle("rribbn", parent=body, fontName=bold, fontSize=21, leading=25, textColor=white, spaceAfter=0),
        "ribbon_headline": ParagraphStyle("rribbh", parent=body, fontSize=11.5, leading=15, textColor=white, spaceAfter=0),
        "label": ParagraphStyle("rlabel", parent=body, fontName=bold, fontSize=9.4, leading=12, textColor=accent, spaceBefore=sgap, spaceAfter=3, keepWithNext=1),
        "label_center": ParagraphStyle("rlabelc", parent=body, fontName=bold, fontSize=9.4, leading=12, textColor=accent, spaceBefore=sgap, spaceAfter=3, keepWithNext=1, alignment=TA_CENTER),
        "label_ink": ParagraphStyle("rlabeli", parent=body, fontName=bold, fontSize=9.4, leading=12, textColor=ink, spaceBefore=sgap, spaceAfter=3, keepWithNext=1),
        "label_band_ink": ParagraphStyle("rlbandi", parent=body, fontName=bold, fontSize=9.4, leading=12, textColor=ink, spaceAfter=0),
        "label_band_white": ParagraphStyle("rlbandw", parent=body, fontName=bold, fontSize=9.4, leading=12, textColor=white, spaceAfter=0),
        "gutter_label": ParagraphStyle("rgutter", parent=body, fontName=bold, fontSize=8.5, leading=11, textColor=accent, spaceAfter=0),
        "hair": hair,
        "ink": ink,
        "accent": accent,
        "regular": regular,
        "bold": bold,
        "body_size": body_size,
        "body_lead": body_lead,
    }


def _band(flowables: list, background: HexColor, width: float, pad: tuple[int, int, int]) -> Table:
    table = Table([[flowables]], colWidths=[width])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), background), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), pad[1]), ("RIGHTPADDING", (0, 0), (-1, -1), pad[1]),
                               ("TOPPADDING", (0, 0), (-1, -1), pad[0]), ("BOTTOMPADDING", (0, 0), (-1, -1), pad[2])]))
    return table


def _mast_flow(content: dict[str, Any], tokens: dict[str, Any], styles: dict[str, ParagraphStyle], width: float) -> list:
    header = content["header"]
    layout = tokens["layout"]
    name, headline, contact = header["name"], header["headline"], " · ".join(header["contact"])
    if not name and not headline:
        return []
    ink = HexColor(tokens["ink"])
    accent = HexColor(tokens["accent"])
    tint = HexColor(tokens["tint"])
    if layout == "banded":
        out: list = []
        if name:
            out.append(_band([Paragraph(escape(name), styles["band_name"])], accent, width, (9, 12, 10)))
        info = []
        if headline:
            info.append(Paragraph(escape(headline), styles["band_headline"]))
        if contact:
            if headline:
                info.append(Spacer(1, 4))
            info.append(Paragraph(_linked_text(contact), styles["band_contact"]))
        if info:
            out.append(_band(info, tint, width, (6, 12, 9)))
        return out
    if layout == "balanced":
        cells: list = []
        if name:
            cells.append(Paragraph(escape(name), styles["ribbon_name"]))
        if headline:
            if name:
                cells.append(Spacer(1, 6))
            cells.append(Paragraph(escape(headline), styles["ribbon_headline"]))
        out = [_band(cells, accent, width, (15, 18, 15))] if cells else []
        if contact:
            out.append(Paragraph(_linked_text(contact), styles["contact_accent"]))
        return out
    centered = layout == "centered"
    out = []
    if name:
        out.append(Paragraph(escape(name), styles["name_center"] if centered else styles["name"]))
    if headline:
        out.append(Paragraph(escape(headline), styles["sub_center"] if centered else styles["sub"]))
    if contact:
        out.append(Paragraph(_linked_text(contact), styles["contact_center"] if centered else styles["contact"]))
    rule = HRFlowable(thickness=0.9 if layout in {"centered", "plain"} else 0.6, color=ink if layout in {"centered", "plain"} else styles["hair"], spaceBefore=8, spaceAfter=0)
    rule.keepWithNext = 1
    out.append(rule)
    return out


def _section_flow(content: dict[str, Any], tokens: dict[str, Any], styles: dict[str, ParagraphStyle], width: float) -> list:
    layout = tokens["layout"]
    out: list = []
    for section in content["sections"]:
        label = escape(section["label"].upper())
        if layout in {"banded", "balanced"}:
            band_style = styles["label_band_ink"] if layout == "banded" else styles["label_band_white"]
            band = _band([Paragraph(label, band_style)], HexColor(tokens["tint"] if layout == "banded" else tokens["accent"]), width, (4, 9, 7))
            band.keepWithNext = 1
            out.append(Spacer(1, styles["sgap"]))
            out.append(band)
        else:
            label_style = styles["label_center"] if layout == "centered" else styles["label_ink"] if layout == "plain" else styles["label"]
            out.append(Paragraph(label, label_style))
            rule = HRFlowable(thickness=0.8 if layout == "plain" else 0.5, color=styles["ink"] if layout == "plain" else styles["hair"], spaceBefore=1, spaceAfter=4)
            rule.keepWithNext = 1
            out.append(rule)
        for entry in section["entries"]:
            out.extend(_entry_flow(entry, section["key"], styles, width))
    return out


def _linked_text(text: str) -> str:
    """Escape user input first, adding only validated HTTP(S) link annotations."""
    parts = []
    start = 0
    for match in re.finditer(r"https?://[^\s<>]+", text):
        parts.append(escape(text[start:match.start()]))
        url = escape(match[0], quote=True)
        parts.append(f'<link href="{url}">{url}</link>')
        start = match.end()
    parts.append(escape(text[start:]))
    return "".join(parts)


class _BulletParagraph(Paragraph):
    """Keep ordinary bullets whole without nesting KeepTogether flowables.

    Nested keep groups hide their real height from a preceding section heading.
    Over-page bullets must still be splittable to avoid a LayoutError.
    """

    def split(self, availWidth, availHeight):
        if self.height <= 240:
            return []
        return super().split(availWidth, availHeight)


def _entry_flow(entry, key, styles, width):
    out = []
    if entry["lead"]:
        # Dates occupy their own line: even an exceptionally long title cannot collide.
        out.append(Paragraph(escape(entry["lead"]), styles["lead"]))
    if entry.get("dates"):
        date = Paragraph(escape(entry["dates"]), styles["metadata"])
        date.keepWithNext = bool(entry["lines"] or entry.get("details"))
        out.append(date)
    for line in entry["lines"]:
        bullet = key in BULLET_SECTIONS
        paragraph_type = _BulletParagraph if bullet else Paragraph
        out.append(paragraph_type(_linked_text(line), styles["bullet"] if bullet else styles["body"], bulletText="•" if bullet else None))
    details = entry.get("details", []) + entry.get("links", [])
    if out and details:
        out[-1].keepWithNext = 1
    for line in details:
        paragraph = Paragraph(_linked_text(line), styles["metadata"])
        paragraph.keepWithNext = 1
        out.append(paragraph)
    if out:
        out[-1].keepWithNext = 0
        if key not in BULLET_SECTIONS and entry["lead"]:
            height = sum(item.wrap(width - 12, PAGE_HEIGHT)[1] + item.getSpaceAfter() for item in out)
            if height <= 160:
                for item in out[:-1]:
                    item.keepWithNext = 1
    return out


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("ResumeSans", 8)
    canvas.setFillColor(HexColor(MUTED))
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, doc.bottomMargin - 17, str(doc.page))
    canvas.restoreState()


class _ResumeDocTemplate(SimpleDocTemplate):
    def afterPage(self):
        _page_footer(self.canv, self)


class _SidebarDocTemplate(BaseDocTemplate):
    def afterPage(self):
        _page_footer(self.canv, self)


def _simple_doc(output: BytesIO, tokens: dict[str, Any]) -> SimpleDocTemplate:
    margin = tokens["margin_mm"] * mm
    return _ResumeDocTemplate(output, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), leftMargin=margin, rightMargin=margin,
                             topMargin=margin, bottomMargin=margin, pageCompression=0, invariant=1,
                             title="Resume", author="", creator="CareerPilot")


def _pdf_imported(output: BytesIO, content: dict[str, Any], tokens: dict[str, Any]) -> None:
    doc = _simple_doc(output, tokens)
    styles = _styles(tokens)
    story = []
    for line in content["text"].splitlines():
        story.append(Paragraph(escape(line), styles["body"]) if line.strip() else Spacer(1, 5))
    doc.build(story or [Paragraph("Resume", styles["body"])])


def _pdf_flow(output: BytesIO, content: dict[str, Any], tokens: dict[str, Any]) -> None:
    doc = _simple_doc(output, tokens)
    width = PAGE_WIDTH - 2 * tokens["margin_mm"] * mm
    styles = _styles(tokens)
    story = _mast_flow(content, tokens, styles, width) + _section_flow(content, tokens, styles, width)
    if not story:
        story = [Paragraph("Resume", styles["body"])]
    doc.build(story)


def _pdf_editorial(output: BytesIO, content: dict[str, Any], tokens: dict[str, Any]) -> None:
    doc = _simple_doc(output, tokens)
    width = PAGE_WIDTH - 2 * tokens["margin_mm"] * mm
    styles = _styles(tokens)
    story = _mast_flow(content, tokens, styles, width)
    gutter = 88
    # One splittable row per flowable, rather than a whole-document Table chained
    # to the masthead rule (which pushed the entire body off page one).
    for section in content["sections"]:
        first = True
        story.append(Spacer(1, styles["sgap"]))
        for entry in section["entries"]:
            for item in _entry_flow(entry, section["key"], styles, width - gutter - 16):
                label = Paragraph(escape(section["label"].upper()), styles["gutter_label"]) if first else ""
                table = Table([[label, item]], colWidths=[gutter, width - gutter], splitByRow=1, splitInRow=1)
                table.keepWithNext = item.getKeepWithNext()
                table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 10),
                                 ("LEFTPADDING", (1, 0), (1, -1), 16), ("RIGHTPADDING", (1, 0), (1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 5 if item.style.name == "rlead" else 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                 ("LINEBEFORE", (1, 0), (1, -1), 0.7, styles["hair"])]))
                story.append(table)
                first = False
    doc.build(story or [Paragraph("Resume", styles["body"])])


def _pdf_sidebar(output: BytesIO, content: dict[str, Any], tokens: dict[str, Any]) -> None:
    styles = _styles(tokens)
    regular, bold = styles["regular"], styles["bold"]
    margin = tokens["margin_mm"] * mm
    left = bottom = top = margin
    avail_w = PAGE_WIDTH - 2 * margin
    avail_h = PAGE_HEIGHT - 2 * margin
    rail_w = max(120, round(avail_w * 0.3))
    gap = 16
    main_w = avail_w - rail_w - gap
    main_x = left + rail_w + gap
    ink = HexColor(tokens["ink"])
    accent = HexColor(tokens["accent"])
    hair = HexColor(tokens["hair"])
    tint = HexColor(tokens["tint"])
    muted = HexColor(MUTED)
    header = content["header"]
    mast = [Paragraph(escape(header[field]), styles[style]) for field, style in (("name", "name"), ("headline", "sub")) if header[field]]
    mast_height = sum(item.wrap(avail_w, PAGE_HEIGHT)[1] + item.getSpaceAfter() for item in mast)
    rule_y = PAGE_HEIGHT - top - mast_height - 8
    frame_top = rule_y - 12 if mast else PAGE_HEIGHT - top

    rail_pad = 8
    rail_text_w = rail_w - 2 * rail_pad
    font_map = {"label": (bold, 9, 12), "lead": (bold, 9, 12.5), "line": (regular, 9, 12.5), "contact": (regular, 9, 12.5)}
    def rail_paragraph(kind, text):
        font, size, leading = font_map[kind]
        style = ParagraphStyle("rail_" + kind, fontName=font, fontSize=size, leading=leading, splitLongWords=True,
                               textColor=accent if kind == "label" else muted if kind == "contact" else ink)
        return Paragraph(_linked_text(text), style)

    budget = frame_top - bottom - 22
    rail_blocks = []
    rail_keys = set()
    overflow_contact = []

    def pack(blocks):
        paragraphs = [rail_paragraph(kind, text) for kind, text in blocks]
        return [(paragraph, paragraph.wrap(rail_text_w, PAGE_HEIGHT)[1] + 3) for paragraph in paragraphs]

    contacts = pack([("contact", value) for value in header["contact"]])
    if sum(height for _, height in contacts) <= budget:
        rail_blocks.extend(contacts)
    else:
        overflow_contact = [{"key": "professional_links", "label": "Contact", "entries": [{"lead": None, "lines": header["contact"]}]}]
    used = sum(height for _, height in rail_blocks)
    for section in content["sections"]:
        if section["key"] not in RAIL_SECTIONS:
            continue
        blocks = [("label", section["label"].upper())]
        for entry in section["entries"]:
            if entry["lead"]:
                blocks.append(("lead", entry["lead"]))
            if entry.get("dates"):
                blocks.append(("line", entry["dates"]))
            blocks.extend(("line", line) for line in entry["lines"] + entry.get("details", []) + entry.get("links", []))
        section_blocks = pack(blocks)
        height = sum(height for _, height in section_blocks) + 9
        if used + height <= budget:
            rail_blocks.extend([(None, 9), *section_blocks])
            used += height
            rail_keys.add(section["key"])
        # A section that cannot fit in the rail stays whole in the main flow.
        # Continuation pages then use the full width instead of empty main columns.

    def draw_mast(canvas) -> None:
        if not mast:
            return
        cursor = PAGE_HEIGHT - top
        for paragraph in mast:
            height = paragraph.wrap(avail_w, PAGE_HEIGHT)[1]
            cursor -= height
            paragraph.drawOn(canvas, left, cursor)
            cursor -= paragraph.getSpaceAfter()
        canvas.setStrokeColor(hair)
        canvas.setLineWidth(0.9)
        canvas.line(left, rule_y, left + avail_w, rule_y)

    def draw_rail(canvas) -> None:
        if not rail_blocks:
            return
        start_y = frame_top - 6
        total = sum(height for _, height in rail_blocks)
        rect_bottom = start_y - total - 8
        canvas.setFillColor(tint)
        canvas.rect(left, rect_bottom, rail_w, start_y - rect_bottom, stroke=0, fill=1)
        cursor = start_y - 8
        for paragraph, height in rail_blocks:
            cursor -= height
            if paragraph is not None:
                paragraph.wrap(rail_text_w, height)
                paragraph.drawOn(canvas, left + rail_pad, cursor + 3)

    def on_first(canvas, doc) -> None:
        draw_mast(canvas)
        draw_rail(canvas)

    padding = dict(topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0)
    if not rail_blocks:
        main_x, main_w = left, avail_w
    frame_page1 = Frame(main_x, bottom, main_w, frame_top - bottom, id="main1", **padding)
    templates = [
        PageTemplate(id="first", frames=[frame_page1], onPage=on_first),
        PageTemplate(id="wide", frames=[Frame(left, bottom, avail_w, avail_h, id="wide", **padding)]),
    ]
    doc = _SidebarDocTemplate(output, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), leftMargin=left, rightMargin=left,
                          topMargin=top, bottomMargin=bottom, pageCompression=0, invariant=1,
                          title="Resume", author="", creator="CareerPilot")
    doc.addPageTemplates(templates)
    main_styles = dict(styles)
    main_styles["label"] = ParagraphStyle("rside", parent=styles["label"], spaceBefore=styles["sgap"])
    story: list = [NextPageTemplate("wide")]
    main_content = {**content, "sections": overflow_contact + [section for section in content["sections"] if section["key"] not in rail_keys]}
    story += _section_flow(main_content, tokens, main_styles, main_w)
    if len(story) == 1:
        story.append(Spacer(1, 2))
    doc.build(story)


def render_pdf(snapshot: dict[str, Any], template_key: str) -> bytes:
    """Create searchable, paginated PDFs with embedded fonts and real text wrapping."""
    content = resume_content(snapshot)
    tokens = design_tokens(snapshot, template_key)
    output = BytesIO()
    layout = tokens["layout"]
    if content["imported"]:
        _pdf_imported(output, content, tokens)
    elif layout == "sidebar":
        _pdf_sidebar(output, content, tokens)
    elif layout == "editorial":
        _pdf_editorial(output, content, tokens)
    else:
        _pdf_flow(output, content, tokens)
    return output.getvalue()
