"""Bounded document extraction and evidence-based resume checks. No external AI calls."""
from __future__ import annotations

import re
from io import BytesIO
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader, apply_configuration

MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_TEXT = 60000
SECTION_NAMES = {
    "summary": ("summary", "professional summary", "profile", "objective", "about me"),
    "experience": ("experience", "work experience", "professional experience", "employment", "employment history"),
    "education": ("education", "academic background", "qualifications"),
    "skills": ("skills", "technical skills", "core competencies", "technologies", "key skills"),
    "projects": ("projects", "personal projects", "selected projects", "academic projects"),
    "certifications": ("certifications", "certificates", "licenses"),
    "achievements": ("achievements", "awards", "honors"),
}
SKILLS = ("Python", "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "SQL", "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "Java", "C++", "C#", "Go", "Rust", "HTML", "CSS", "Tailwind", "FastAPI", "Django", "Flask", "Spring", "GraphQL", "REST", "Figma", "Excel", "Tableau", "Power BI", "TensorFlow", "PyTorch", "Pandas", "NumPy", "Linux", "Agile", "Scrum", "Salesforce", "SEO", "Project management", "Data analysis", "Communication", "Leadership")
ACTION = re.compile(r"^(?:[•*\-–]\s*)?(built|developed|designed|led|created|implemented|improved|reduced|increased|delivered|launched|managed|optimized|automated|achieved|analyzed|collaborated|deployed|supported|maintained|resolved|organized|researched)\b", re.I)


@apply_configuration(maximum_declared_stream_length=4_000_000, zlib_maximum_output_length=4_000_000,
                     lzw_maximum_output_length=4_000_000, run_length_maximum_output_length=4_000_000,
                     array_based_stream_maximum_output_length=4_000_000, stream_decoding_work_maximum_length=16_000_000,
                     stream_parsing_work_maximum_count=200_000, page_tree_maximum_entries=100,
                     page_tree_maximum_depth=20, xform_maximum_invocations_per_extraction=100)
def extract_document(data: bytes, filename: str) -> str:
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Choose a non-empty file smaller than 3 MB.")
    extension = filename.rsplit(".", 1)[-1].lower()
    try:
        if extension == "pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("This file is not a valid PDF.")
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise ValueError("Remove the PDF password before uploading.")
            if len(reader.pages) > 10:
                raise ValueError("Please upload a resume of 10 pages or fewer.")
            chunks = []
            for page in reader.pages:
                stream = page.get_contents()
                if stream and len(stream.get_data()) > 4 * 1024 * 1024:
                    raise ValueError("This PDF is too complex. Export a simpler PDF or paste its text.")
                chunks.append(page.extract_text() or "")
                if sum(map(len, chunks)) > MAX_TEXT:
                    raise ValueError("Resume text is too long. Limit it to 60,000 characters.")
            text = "\n".join(chunks)
        elif extension == "docx":
            with ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 300 or sum(item.file_size for item in entries) > 12 * 1024 * 1024:
                    raise ValueError("This document is too complex. Export it as PDF or paste its text.")
                xml = archive.read("word/document.xml")
                if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                    raise ValueError("Unsupported document XML.")
                root = ElementTree.fromstring(xml)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                text = "\n".join(
                    "".join(t.text or "" for t in paragraph.findall(".//w:t", ns))
                    for paragraph in root.findall(".//w:p", ns)
                )
        elif extension == "txt":
            text = data.decode("utf-8-sig")
        else:
            raise ValueError("Use PDF, DOCX, or UTF-8 TXT. You can also paste resume text.")
    except ValueError:
        raise
    except (BadZipFile, KeyError, UnicodeError, ElementTree.ParseError) as exc:
        raise ValueError("Could not read this document. Try exporting it as PDF or paste its text.") from exc
    except Exception as exc:
        raise ValueError("Could not read this PDF. Try a fresh export or paste its text.") from exc
    if len(text) > MAX_TEXT:
        raise ValueError("Resume text is too long. Limit it to 60,000 characters.")
    if len(text.strip()) < 80:
        raise ValueError("Not enough readable text. Scanned PDFs need OCR first; alternatively paste your resume text.")
    return text.replace("\x00", "").strip()


def find_skills(text: str) -> list[str]:
    return [skill for skill in SKILLS if re.search(r"(?<![\w+#])" + re.escape(skill) + r"(?![\w+#])", text, re.I)]


def review_resume(text: str, job_description: str = "") -> dict:
    text = text.replace("\x00", "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    words = re.findall(r"\b[\w+#.-]+\b", text)
    sections: dict[str, list[str]] = {"contact": []}
    current = "contact"
    for line in lines:
        heading = re.sub(r"[^a-z ]", "", line.lower()).strip()
        matched = next((key for key, aliases in SECTION_NAMES.items() if heading in aliases), None)
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections[current].append(line)
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    action_lines = [line for line in lines if ACTION.search(line)]
    quantified = [line for line in action_lines if re.search(r"\d", line)]
    checks = []

    def check(key, title, passed, weight, detail, suggestion, evidence=None):
        checks.append({"id": key, "title": title, "passed": bool(passed), "weight": weight, "detail": detail, "suggestion": suggestion, "evidence": (evidence or [])[:3]})

    check("contact", "Reachable contact", email, 10, "A contact email was found." if email else "No contact email was detected.", "Add a professional email address near your name.")
    check("length", "Focused length", 200 <= len(words) <= 1000, 15, f"{len(words)} words extracted.", "Aim for roughly 200–1,000 words; use the space needed for relevant experience.")
    check("experience", "Experience or projects", sections.get("experience") or sections.get("projects"), 20, "Checks for a recognizable experience or projects section.", "Use a clear Experience or Projects heading and describe work you actually did.")
    check("education", "Education context", sections.get("education"), 10, "Checks for a recognizable education section.", "Add an Education heading with your qualification and institution.")
    check("skills", "Skills section", sections.get("skills"), 10, "Checks for a clearly labeled skills section.", "Group relevant skills under a Skills heading; include only skills you can demonstrate.")
    check("impact", "Evidence of impact", len(quantified) >= 2, 20, f"{len(quantified)} action-led lines contain numbers.", "Where accurate, add scale or outcomes to two bullets: users served, time saved, scope, or measurable results.", quantified)
    check("actions", "Action-led writing", len(action_lines) >= 3, 10, f"{len(action_lines)} lines start with recognized action verbs.", "Start bullets with a specific action such as Built, Analyzed, Led, or Delivered.", action_lines)
    check("links", "Supporting links", re.search(r"(?:https?://|linkedin\.com/|github\.com/)", text, re.I), 5, "Checks for a portfolio or professional URL.", "Add a relevant portfolio, LinkedIn, or GitHub link if it strengthens your application.")
    target_skills = find_skills(job_description)
    detected = find_skills(text)
    matched = [skill for skill in target_skills if skill in detected]
    missing = [skill for skill in target_skills if skill not in detected]
    name = lines[0] if lines and len(lines[0]) <= 80 and "@" not in lines[0] else ""
    return {
        "text": text, "word_count": len(words), "score": sum(c["weight"] for c in checks if c["passed"]),
        "method": "Resume readiness checklist v1 · rule-based, not an ATS or hiring prediction",
        "checks": checks, "skills": detected, "profile": {"full_name": name, "email": email.group() if email else None},
        "sections": [{"key": key, "title": key.replace("_", " ").title(), "text": "\n".join(value)} for key, value in sections.items() if value],
        "job_match": {"matched": matched, "missing": missing, "coverage": round(len(matched) / len(target_skills) * 100) if target_skills else None,
                      "note": "Matches only recognized skill terms, not seniority, eligibility, or overall suitability."},
    }
