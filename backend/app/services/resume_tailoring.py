"""Conservative tailoring: reorder owned evidence, remove filler, never add career facts."""
import re
from copy import deepcopy
from typing import Any

from app.services.ai import AIProviderUnavailable, get_ai_provider
from app.services.resume_review import find_skills
from app.services.resume_themes import recommended_theme

STOP = set("a an the and or for to of in on with as is are be by we you your our will can have has this that from at role team candidate work looking required preferred must should ability strong excellent experience knowledge skills responsibilities qualifications requirements including using".split())
VERBS = {"building": "built", "developing": "developed", "designing": "designed", "implementing": "implemented", "managing": "managed", "creating": "created", "maintaining": "maintained", "testing": "tested", "deploying": "deployed", "optimizing": "optimized", "supporting": "supported", "analyzing": "analyzed", "leading": "led"}


def terms(text):
    return [word.lower() for word in re.findall(r"[\w]+(?:[.+#-][\w+#]+)*", str(text)) if len(word) > 1 and word.lower() not in STOP]


def text_of(value):
    if isinstance(value, dict):
        return " ".join(text_of(item) for key, item in value.items() if key not in {"source_id", "skill_id", "source", "resume_meta", "job_target", "id"})
    if isinstance(value, list):
        return " ".join(text_of(item) for item in value)
    return "" if value is None else str(value)


def concise(line):
    """Only grammar-preserving filler removal and inflection; all numbers/nouns remain."""
    line = re.sub(r"^[\s•\u25a1\u25aa*\-]+", "", line).strip()
    match = re.match(r"(?:I was responsible for|Responsible for|Worked on|Helped with)\s+(.+)", line, re.I)
    if match:
        # 'Helped with' records a supporting role and must not become a leadership claim.
        if re.match(r"(?:Helped with|Worked on)", line, re.I):
            return line
        rest = match.group(1)
        first, separator, tail = rest.partition(" ")
        if first.lower() in VERBS:
            return VERBS[first.lower()].capitalize() + separator + tail
    return line


def analyze_job(title, description, evidence):
    keywords = list(dict.fromkeys(terms(title + " " + description)))[:100]
    known = find_skills(description)
    evidence_skills = set(find_skills(evidence))
    evidence_terms = set(terms(evidence))
    lines = [re.sub(r"^[\s•*\-]+", "", line).strip() for line in re.split(r"[\n;]+", description)]
    qualifications = [line for line in lines if re.search(r"\b(required|must|degree|bachelor|master|certif|years?|qualification|license)", line, re.I)][:25]
    responsibilities = [line for line in lines if re.search(r"\b(build|develop|design|maintain|lead|manage|deliver|implement|analy[sz]e|responsib|collaborat|support)", line, re.I)][:25]
    missing_skills = [skill for skill in known if skill not in evidence_skills]
    # Qualifications require review unless the exact claim is already in the evidence.
    missing = missing_skills + [line for line in qualifications if line.casefold() not in evidence.casefold()]
    return {"skills": known, "keywords": keywords, "qualifications": qualifications, "responsibilities": responsibilities,
            "matched_keywords": [word for word in keywords if word in evidence_terms], "missing_qualifications": list(dict.fromkeys(missing)),
            "qualification_note": "Not evidenced / needs your review. Keyword overlap alone does not establish a degree, seniority, eligibility or certification."}


def tailor_snapshot(source, title, description):
    result = deepcopy(source)
    evidence = text_of({key: value for key, value in source.items() if key != "job_target"})
    if len(evidence.strip()) < 80:
        raise ValueError("Add experience, projects or an existing resume before generating a job-specific draft.")
    analysis = analyze_job(title, description, evidence)
    targets = set(terms(title + " " + description))

    def relevance(value):
        return len(set(terms(text_of(value))) & targets)

    method = "grounded_rules"
    provider_note = "No external AI provider is configured; wording is conservatively edited from your own evidence."
    if result.get("source") == "document_import":
        # Unstructured imports cannot safely infer project boundaries or structured facts.
        # Preserve their reading order, but tighten explicit action-led wording line by line.
        result["imported_text"] = "\n".join(concise(line) if line.strip() else "" for line in source.get("imported_text", "").splitlines())
    else:
        for section in ("skills", "projects", "experience", "education", "achievements", "certifications"):
            result[section] = sorted(result.get(section, []), key=relevance, reverse=True)
        for section in ("experience", "projects", "achievements"):
            for record in result.get(section, []):
                for field in ("description", "achievements", "results", "features", "problem_solved"):
                    if record.get(field):
                        lines = [concise(line) for line in str(record[field]).splitlines() if line.strip()]
                        record[field] = "\n".join(sorted(lines, key=relevance, reverse=True))
        profile = result.setdefault("profile", {})
        summary = []
        if profile.get("bio"):
            summary.append(str(profile["bio"]).strip())
        relevant_skills = [item["name"] for item in result.get("skills", []) if relevance(item)]
        if relevant_skills:
            summary.append("Relevant skills: " + ", ".join(relevant_skills[:10]) + ".")
        projects = [item["name"] for item in result.get("projects", []) if relevance(item)]
        if projects:
            summary.append("Selected work: " + "; ".join(projects[:2]) + ".")
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
        for edit in proposed.get("bullet_rewrites", [])[:100]:
            section, field = edit.get("section"), edit.get("field")
            if section not in {"experience", "projects", "achievements"} or field not in {"description", "achievements", "results", "features"}:
                continue
            original = next((item for item in source.get(section, []) if item.get("source_id") == edit.get("source_id")), None)
            replacement = edit.get("text")
            if not original or not isinstance(replacement, str) or len(replacement) > 5000:
                continue

            def normalized(value: Any) -> list[str]:
                return terms(concise(str(value)))

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
                            "note": provider_note, "recommended_template_key": recommended_theme(title)}
    result.setdefault("resume_meta", {})["section_order"] = ["profile", "skills", "experience", "projects", "education", "certifications", "achievements", "professional_links", "courses", "languages", "open_source_contributions"]
    return result
