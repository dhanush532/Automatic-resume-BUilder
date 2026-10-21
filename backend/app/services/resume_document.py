"""Conservative structure for imported resumes; never infer employers or facts."""
import re

from app.services.resume_review import SECTION_NAMES

BULLET = re.compile(r"^\s*(?:[•▪◦*\-–]\s+|\d+[.)]\s+)")
ALIASES = {alias: key for key, aliases in SECTION_NAMES.items() for alias in aliases}
ALIASES.update({"links": "professional_links", "professional links": "professional_links", "languages": "languages", "courses": "courses", "courses & training": "courses", "open-source contributions": "open_source_contributions"})


def imported_document(text: str) -> dict:
    """Recognize explicit headings and title+bullet boundaries only.

    Original lines are retained for lossless block reordering. Ambiguous prose is
    a single block, not guessed into employment/project records.
    """
    preamble, sections = [], []
    current = None
    for raw in text.splitlines():
        label = raw.strip()
        heading = label.rstrip(":").casefold()
        key = ALIASES.get(heading)
        if key:
            current = {"key": key, "label": label, "lines": [], "blocks": []}
            sections.append(current)
        elif current is None:
            preamble.append(raw)
        else:
            current["lines"].append(raw)
    for section in sections:
        lines = section["lines"]
        blocks = section["blocks"]
        if section["key"] not in {"experience", "projects", "achievements", "open_source_contributions"}:
            blocks.append(lines[:])
            continue
        for index, line in enumerate(lines):
            # A short explicit title followed immediately by a bullet is a safe
            # boundary; dates, long prose and punctuation-ended sentences aren't.
            is_title = (line.strip() and not BULLET.match(line) and len(line.strip()) <= 180
                        and not line.rstrip().endswith((".", ";")) and index + 1 < len(lines)
                        and BULLET.match(lines[index + 1]))
            if not blocks or (is_title and any(item.strip() for item in blocks[-1])):
                blocks.append([])
            blocks[-1].append(line)
    return {"preamble": preamble, "sections": sections}


def imported_content(text: str) -> dict:
    document = imported_document(text)
    before = [line.strip() for line in document["preamble"] if line.strip()]
    name = ""
    if before and len(before[0]) <= 100 and len(before[0].split()) <= 10 and not re.search(r"@|https?://", before[0]):
        name = before.pop(0)
    contact, headline, overflow = [], [], []
    for line in before:
        if len(line) > 300 or sum(map(len, contact + headline)) + len(line) > 500:
            overflow.append(line)
        else:
            (contact if re.search(r"@|https?://|linkedin\.com|github\.com|\+?\d[\d ()-]{7,}", line) else headline).append(line)
    sections = []
    if overflow:
        sections.append({"key": "preamble", "label": "Profile", "entries": [{"lead": None, "lines": overflow, "dates": "", "details": [], "links": []}]})
    for section in document["sections"]:
        entries = []
        for block in section["blocks"]:
            lines = [line.strip() for line in block if line.strip()]
            if not lines:
                continue
            lead = None
            if len(lines) > 1 and not BULLET.match(lines[0]) and BULLET.match(lines[1]):
                lead = lines.pop(0)
            body, details, links = [], [], []
            for line in lines:
                clean = BULLET.sub("", line)
                if re.match(r"https?://\S+$", clean):
                    links.append(clean)
                elif re.match(r"(?:technologies|tech stack|tools)\s*:", clean, re.I):
                    details.append(clean)
                else:
                    body.append(clean)
            entries.append({"lead": lead, "lines": body, "dates": "", "details": details, "links": links})
        if entries:
            sections.append({"key": section["key"], "label": section["label"].rstrip(":"), "entries": entries})
    return {"imported": True, "text": text, "header": {"name": name, "headline": " · ".join(headline), "contact": contact}, "sections": sections}
