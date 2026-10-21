"""Conservative tailoring: reorder owned evidence, remove filler, never add career facts."""
import re
from copy import deepcopy
from typing import Any

from app.services.ai import AIProviderUnavailable, get_ai_provider
from app.services.resume_document import BULLET, imported_document
from app.services.resume_review import find_evidenced_skills, find_skills
from app.services.resume_themes import recommended_theme

STOP = set("a an the and or for to of in on with as is are be by we you your our will can have has this that from at role team candidate work looking required preferred must should ability strong excellent experience knowledge skills responsibilities qualifications requirements including using".split())
ONGOING_VERBS = {"building", "developing", "designing", "implementing", "managing", "creating", "maintaining", "testing", "deploying", "optimizing", "supporting", "analyzing", "leading"}


def terms(text):
    return [word.lower() for word in re.findall(r"[\w]+(?:[.+#-][\w+#]+)*", str(text)) if len(word) > 1 and word.lower() not in STOP]


def text_of(value):
    if isinstance(value, dict):
        return "\n".join(text_of(item) for key, item in value.items() if key not in {"source_id", "skill_id", "source", "resume_meta", "job_target", "id"})
    if isinstance(value, list):
        return "\n".join(text_of(item) for item in value)
    return "" if value is None else str(value)


def concise(line):
    """Remove filler without turning responsibility or ongoing work into completion."""
    line = re.sub(r"^[\s•\u25a1\u25aa*\-]+", "", line).strip()
    match = re.match(r"(?:I was responsible for|Responsible for|Worked on|Helped with)\s+(.+)", line, re.I)
    if match:
        # 'Helped with' records a supporting role and must not become a leadership claim.
        if re.match(r"(?:Helped with|Worked on)", line, re.I):
            return line
        rest = match.group(1)
        first, separator, tail = rest.partition(" ")
        if first.lower() in ONGOING_VERBS:
            return first.capitalize() + separator + tail
    return line


def analyze_job(title, description, evidence):
    keywords = list(dict.fromkeys(terms(title + " " + description)))[:100]
    known = find_skills(title + " " + description)
    evidence_skills = set(find_evidenced_skills(evidence))
    evidence_terms = set(terms(evidence))
    separated = re.sub(r"(?i)(?<!^)(?<!\n)\s+(?=(?:required|preferred|requirements|responsibilities|nice.to.have)\s*:)", "\n", description)
    lines = [re.sub(r"^[\s•*\-]+", "", line).strip() for line in re.split(r"[\n;]+", separated)]
    required, preferred = [], []
    category = required
    for line in lines:
        if re.search(r"\b(preferred|nice.to.have|bonus|desirable)\b", line, re.I):
            category = preferred
        elif re.search(r"\b(required|requirements|must|essential|minimum)\b", line, re.I):
            category = required
        if re.search(r"\b(responsibilities|what you.ll do)\b", line, re.I):
            category = None
        if category is not None and line:
            category.append(line)
    qualifications = list(dict.fromkeys(required + preferred))[:25]
    responsibilities = [line for line in lines if re.search(r"\b(build|develop|design|maintain|lead|manage|deliver|implement|analy[sz]e|responsib|collaborat|support)", line, re.I)][:25]
    missing_skills = [skill for skill in known if skill not in evidence_skills]
    for skill in missing_skills:
        evidence_terms.difference_update(terms(skill))
    # Qualifications require review unless the exact claim is already in the evidence.
    missing = missing_skills + [line for line in qualifications
                               if line.casefold() not in evidence.casefold()
                               and (re.search(r"\b(degree|bachelor|master|certif\w*|years?|license|eligib\w*|authori[sz]\w*)\b", line, re.I)
                                    or (not find_skills(line) and not line.endswith(":")))]
    return {"skills": known, "keywords": keywords, "qualifications": qualifications, "required_qualifications": required[:25], "preferred_qualifications": preferred[:25], "responsibilities": responsibilities,
            "matched_keywords": [word for word in keywords if word in evidence_terms], "missing_qualifications": list(dict.fromkeys(missing)),
            "qualification_note": "Not evidenced / needs your review. Keyword overlap alone does not establish a degree, seniority, eligibility or certification."}


def tailor_snapshot(source, title, description):
    result = deepcopy(source)
    evidence = text_of({key: value for key, value in source.items() if key != "job_target"})
    if len(evidence.strip()) < 80:
        raise ValueError("Add experience, projects or an existing resume before generating a job-specific draft.")
    analysis = analyze_job(title, description, evidence)
    targets = set(terms(title + " " + description))
    title_terms = set(terms(title))
    required_terms = set(terms(" ".join(analysis["required_qualifications"])))
    target_skills = set(analysis["skills"])
    source_skills = {str(item.get("skill_id")): item.get("name", "") for item in source.get("skills", []) if item.get("skill_id")}

    def relevance(value):
        text = text_of(value)
        if isinstance(value, dict):
            text += " " + " ".join(source_skills.get(str(key), "") for key in value.get("skill_ids", []))
        words = set(terms(text))
        # Technical matches outweigh generic words; job-title and required terms
        # outweigh preferred terms. Linked project/experience skills count too.
        return 5 * len(set(find_evidenced_skills(text)) & target_skills) + 3 * len(words & title_terms) + 2 * len(words & required_terms) + len(words & targets)

    method = "grounded_rules"
    provider_note = "No external AI provider is configured; wording is conservatively edited from your own evidence."
    base_bio = (source.get("profile") or {}).get("bio") or ""
    previous = source.get("job_target") or {}
    if base_bio == previous.get("generated_summary"):
        base_bio = previous.get("base_summary", base_bio)
    if result.get("source") == "document_import":
        document = imported_document(source.get("imported_text", ""))
        output = document["preamble"][:]
        if document["sections"]:
            for section in document["sections"]:
                blocks = section["blocks"][:]
                if section["key"] == "projects":
                    # Reorder only explicit title+bullet project blocks. Ambiguous
                    # prose and chronology retain their original positions.
                    movable = [index for index, block in enumerate(blocks)
                               if len(clean := [line for line in block if line.strip()]) > 1
                               and not BULLET.match(clean[0]) and BULLET.match(clean[1])]
                    ranked = sorted((blocks[index] for index in movable), key=relevance, reverse=True)
                    for index, block in zip(movable, ranked, strict=True):
                        blocks[index] = block
                output.append(section["label"])
                output.extend(line for block in blocks for line in block)
        def edit_line(line):
            bullet = BULLET.match(line)
            return line[:bullet.end()] + concise(line[bullet.end():]) if bullet else concise(line) if line.strip() else line

        result["imported_text"] = "\n".join(edit_line(line) for line in output)
    else:
        for section in ("skills", "projects", "experience", "education", "achievements", "certifications"):
            result[section] = sorted(result.get(section, []), key=relevance, reverse=True)
        for section in ("experience", "projects", "achievements"):
            for record in result.get(section, []):
                for field in ("description", "achievements", "results", "features", "problem_solved"):
                    if record.get(field):
                        lines = list(dict.fromkeys(concise(line) for line in str(record[field]).splitlines() if line.strip()))
                        record[field] = "\n".join(sorted(lines, key=relevance, reverse=True))
        profile = result.setdefault("profile", {})
        summary = []
        if base_bio:
            sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n+", str(base_bio)) if sentence.strip()]
            selected = sorted(sentences, key=relevance, reverse=True)
            for sentence in selected:
                if len(" ".join(summary + [sentence])) <= 450:
                    summary.append(sentence)
                if len(summary) == 2:
                    break
            # A long unsplittable bio remains in the underlying profile; never
            # slice a sentence in the middle or fabricate a shorter claim.
        relevant_skills = [item["name"] for item in result.get("skills", []) if relevance(item)]
        if relevant_skills:
            summary.append("Relevant skills: " + ", ".join(relevant_skills[:6]) + ".")
        projects = [item["name"] for item in result.get("projects", []) if relevance(item) and item.get("name") and len(item["name"]) <= 90]
        if projects and projects[0].casefold() not in " ".join(summary).casefold():
            summary.append("Selected project: " + projects[0] + ".")
        if not summary:
            roles = [" at ".join(filter(None, [item.get("title"), item.get("company")])) for item in result.get("experience", [])]
            summary.append("Experience: " + "; ".join(roles[:2]) + "." if roles else "Career background presented for review against the target role.")
        profile["bio"] = " ".join(summary)[:5000]
        profile["headline"] = "Target role: " + title
        result["source"] = "job_tailored"

    # Reuse the current provider boundary. Only allow wording that preserves the
    # source's ordered semantic tokens; free-form new claims are never copied.
    try:
        proposed = get_ai_provider().customize_resume(job_description=title + "\n" + description, resume_snapshot=deepcopy(source))
        accepted = 0
        rewrites = proposed.get("bullet_rewrites", []) if isinstance(proposed, dict) else []
        for edit in (rewrites[:100] if isinstance(rewrites, list) else []):
            if not isinstance(edit, dict):
                continue
            section, field = edit.get("section"), edit.get("field")
            if section not in {"experience", "projects", "achievements"} or field not in {"description", "achievements", "results", "features"}:
                continue
            original = next((item for item in source.get(section, []) if item.get("source_id") == edit.get("source_id")), None)
            replacement = edit.get("text")
            if not original or not isinstance(replacement, str) or len(replacement) > 5000:
                continue

            def normalized(value: Any) -> list[str]:
                # Do not remove stop words here: 'will', 'not', 'without', etc.
                # carry factual meaning even though they are irrelevant to ranking.
                return re.findall(r"[\w]+(?:[.+#-][\w+#]+)*", concise(str(value)).casefold())

            # Preserve negation and metrics as well as word order.
            if normalized(replacement) != normalized(original.get(field, "")) or re.findall(r"\d+(?:\.\d+)?%?", replacement) != re.findall(r"\d+(?:\.\d+)?%?", str(original.get(field, ""))):
                continue
            destination = next((item for item in result.get(section, []) if item.get("source_id") == edit["source_id"]), None)
            if destination is None:
                continue
            destination[field] = replacement.strip()
            accepted += 1
        if accepted:
            method = "provider_assisted_grounded"
            provider_note = "Provider wording passed conservative source-evidence checks. Review the draft before applying."
        else:
            provider_note = "Provider wording was not source-equivalent; the evidence-grounded draft was retained."
    except AIProviderUnavailable:
        pass
    result["job_target"] = {"title": title, "description": description, "analysis": analysis, "method": method,
                            "note": provider_note, "recommended_template_key": recommended_theme(title),
                            "base_summary": base_bio, "generated_summary": (result.get("profile") or {}).get("bio", ""),
                            "evidence": [{"section": section, "source_id": item.get("source_id"),
                                          "matched_skills": [skill for skill in find_evidenced_skills(text_of(item)) if skill in target_skills]}
                                         for section in ("experience", "projects") for item in result.get(section, []) if relevance(item)]}
    primary = sorted(("experience", "projects"), key=lambda section: max((relevance(item) for item in result.get(section, [])), default=0), reverse=True)
    result.setdefault("resume_meta", {})["section_order"] = ["profile", *primary, "skills", "education", "certifications", "achievements", "professional_links", "courses", "languages", "open_source_contributions"]
    return result
