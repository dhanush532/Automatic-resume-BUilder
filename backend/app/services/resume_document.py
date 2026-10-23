"""Conservative structure for imported resumes; never infer employers or facts."""
import re

from app.services.resume_review import ACTION, SECTION_NAMES, find_skills

BULLET = re.compile(r"^\s*(?:[•▪◦*\-–]\s+|\d+[.)]\s+)")
ALIASES = {alias: key for key, aliases in SECTION_NAMES.items() for alias in aliases}
ALIASES.update({"links": "professional_links", "professional links": "professional_links", "languages": "languages", "courses": "courses", "courses & training": "courses", "open-source contributions": "open_source_contributions"})
ALIASES.update({"coursework & achievements": "achievements", "coursework and achievements": "achievements", "relevant coursework": "courses", "coursework": "courses"})


def _technology_line(line):
    clean = BULLET.sub("", line).strip()
    return bool(
        re.match(r"(?:technologies|tech stack|tools)\s*:", clean, re.I)
        or ("," in clean and find_skills(clean) and len(clean.split()) <= 18 and not ACTION.match(clean))
    )


def _status_line(line):
    return bool(re.match(r"(?:solo|personal|team|individual) project\b", BULLET.sub("", line).strip(), re.I))


def project_block_has_title(block):
    lines = [line for line in block if line.strip()]
    if len(lines) < 2:
        return False
    title = BULLET.sub("", lines[0]).strip()
    if not title or ACTION.match(title) or _technology_line(title) or _status_line(title):
        return False
    return bool((not BULLET.match(lines[0]) and BULLET.match(lines[1]))
                or _technology_line(lines[1]) or _status_line(lines[1]))


def repair_import_lines(text):
    """Recover line-wrap damage without inventing or completing any claims.

    Only join lowercase continuation fragments onto unfinished preceding lines.
    Headings, action-led bullets, metadata and explicit project boundaries win.
    """
    result = []
    for raw in text.splitlines():
        if re.match(r"^\s*<PARSED TEXT FOR PAGE:.*>\s*$", raw):
            continue
        if re.fullmatch(r"\s{8,}\d{1,3}\s*", raw):
            continue  # Indented, isolated PDF page footer, not a numbered bullet.
        clean = BULLET.sub("", raw).strip()
        heading = clean.rstrip(":").casefold() in ALIASES
        if heading:
            result.append(clean)
            continue
        previous = next((index for index in range(len(result) - 1, -1, -1) if result[index].strip()), None)
        if previous is not None and clean:
            last = BULLET.sub("", result[previous]).strip()
            continuation = (clean[0].islower() and not ACTION.match(clean)
                            and not _status_line(clean) and not _technology_line(clean)
                            and not last.endswith((".", "!", "?", ":"))
                            and last.rstrip(":").casefold() not in ALIASES
                            and not _status_line(last)
                            and (ACTION.match(last) or BULLET.match(result[previous]) or len(last) > 100)
                            and not re.search(r"@|https?://|linkedin\.com/|github\.com/", clean))
            tech_continuation = last.endswith(",") and _technology_line(last) and _technology_line(clean)
            list_continuation = (last.endswith(",") and not BULLET.match(raw) and not ACTION.match(clean)
                                 and not _status_line(clean) and last.rstrip(":").casefold() not in ALIASES)
            wrapped_prose = (not BULLET.match(raw) and not ACTION.match(clean)
                             and not _status_line(clean) and not _technology_line(clean)
                             and not last.endswith((".", "!", "?", ":"))
                             and (BULLET.match(result[previous]) or len(last) > 100 or len(last.split()) > 8)
                             and (raw.startswith(("  ", "\t")) or re.search(r"\b(?:a|an|the|and|or|from|with|using|of|for|in|to)$", last))
                             and not re.search(r"@|https?://|linkedin\.com/|github\.com/", clean))
            if continuation or tech_continuation or list_continuation or wrapped_prose:
                result[previous] = result[previous].rstrip() + " " + clean
                continue
        result.append(raw)
    return result


def imported_document(text: str) -> dict:
    """Recognize explicit headings and title+bullet boundaries only.

    Original lines are retained for lossless block reordering. Ambiguous prose is
    a single block, not guessed into employment/project records.
    """
    preamble, sections = [], []
    current = None
    for raw in repair_import_lines(text):
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
            clean = BULLET.sub("", line).strip()
            metadata_follows = (index + 1 < len(lines) and (_technology_line(lines[index + 1]) or _status_line(lines[index + 1])))
            repaired_title = (section["key"] == "projects" and bool(clean) and metadata_follows
                              and not ACTION.match(clean) and not _technology_line(clean) and not _status_line(clean))
            is_title = repaired_title or (line.strip() and not BULLET.match(line) and len(line.strip()) <= 180
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
            if len(lines) > 1 and ((not BULLET.match(lines[0]) and BULLET.match(lines[1]))
                                  or (section["key"] == "projects" and (_technology_line(lines[1]) or _status_line(lines[1]))
                                      and not ACTION.match(BULLET.sub("", lines[0])))):
                lead = BULLET.sub("", lines.pop(0))
            body, details, links, pre_details = [], [], [], []
            for line in lines:
                clean = BULLET.sub("", line)
                if re.match(r"https?://\S+$", clean):
                    links.append(clean)
                elif re.match(r"(?:technologies|tech stack|tools)\s*:", clean, re.I) or (lead and (_technology_line(clean) or _status_line(clean))):
                    (details if body else pre_details).append(clean)
                else:
                    body.append(clean)
            entries.append({"lead": lead, "lines": body, "dates": "", "pre_details": pre_details, "details": details, "links": links,
                            "keep_compact": bool(lead and pre_details and section["key"] == "projects")})
        if entries:
            sections.append({"key": section["key"], "label": section["label"].rstrip(":"), "entries": entries})
    return {"imported": True, "text": text, "header": {"name": name, "headline": " · ".join(headline), "contact": contact}, "sections": sections}
