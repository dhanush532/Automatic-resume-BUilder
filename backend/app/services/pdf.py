from __future__ import annotations

from html import escape
from typing import Any


def _display(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def resume_lines(snapshot: dict[str, Any], template_key: str) -> list[str]:
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
    body = "\n".join(
        f"<p class=\"{'title' if index == 1 else 'subtitle' if index == 2 else 'section' if line in section_names else 'body'}\">{escape(line)}</p>" if line else "<div class=\"spacer\"></div>"
        for index, line in enumerate(lines)
    )
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>{title}</title><style>
    @page {{ size: A4; margin: 18mm; }} body {{ font-family: {font}; color: #16213e; background: {background}; max-width: 800px; margin: 0 auto; line-height: 1.45; }}
    p {{ margin: 0 0 7px; }} .title {{ font-size: 28px; font-weight: 700; }} .subtitle {{ font-size: 17px; color: {accent}; }} .section {{ margin-top: 18px; border-bottom: 2px solid {accent}; color: {accent}; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }} .body {{ font-size: 11px; }}
    .spacer {{ height: 8px; }}
    </style></head><body data-template=\"{escape(template_key)}\">{body}</body></html>"""


def _pdf_escape(value: str) -> str:
    return value.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_pdf(snapshot: dict[str, Any], template_key: str) -> bytes:
    """Create a deterministic, text-searchable A4 PDF without external services."""

    lines = resume_lines(snapshot, template_key)
    layout = {
        "modern": (11, 18, 16),
        "professional": (10, 17, 15),
        "minimal": (10, 16, 14),
        "student": (11, 18, 16),
        "developer": (10, 17, 15),
        "creative": (11, 19, 16),
        "ats_readable": (10, 16, 14),
    }.get(template_key, (10, 16, 14))
    body_size, title_size, leading = layout
    section_names = {"Links", "Experience", "Projects", "Education", "Skills", "Certifications", "Courses & training", "Achievements", "Languages", "Open-source contributions"}
    pages = [lines[index : index + 44] for index in range(0, len(lines), 44)] or [["Career Passport"]]
    objects: list[bytes] = []
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_refs: list[int] = []
    for page_lines in pages:
        commands = ["BT", f"/F1 {body_size} Tf", "54 790 Td"]
        for index, line in enumerate(page_lines):
            if index:
                commands.append(f"0 -{leading} Td")
            if index == 1:
                commands.append(f"/F1 {title_size} Tf")
            elif line in section_names:
                commands.append(f"/F1 {body_size + 1} Tf")
            else:
                commands.append(f"/F1 {body_size} Tf")
            commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        content_ref = len(objects)
        objects.append(b"")
        objects[-1] = b""
        page_refs.append(len(objects) + 1)
        objects.append(b"")
        objects[-1] = f"<< /Type /Page /Parent PAGES /MediaBox [0 0 595 842] /Resources << /Font << /F1 1 0 R >> >> /Contents {content_ref} 0 R >>".encode()
    pages_ref = len(objects) + 1
    objects.append(f"<< /Type /Pages /Kids [{ ' '.join(f'{ref} 0 R' for ref in page_refs) }] /Count {len(page_refs)} >>".replace("PAGES", f"{pages_ref} 0 R").encode())
    catalog_ref = len(objects) + 1
    objects.append(f"<< /Type /Catalog /Pages {pages_ref} 0 R >>".encode())

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_ref} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)
