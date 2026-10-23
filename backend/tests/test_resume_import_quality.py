"""Regressions reproduced after the reference-workflow review."""
from copy import deepcopy
from io import BytesIO

import pytest
from pypdf import PdfReader
from resume_quality_fixture import quality_snapshot, short_snapshot

from app.services.pdf import (
    _luminance,
    design_tokens,
    render_pdf,
    render_preview_html,
    resume_content,
)
from app.services.resume_document import imported_document
from app.services.resume_review import find_evidenced_skills, has_impact_evidence, review_resume
from app.services.resume_tailoring import analyze_job, tailor_snapshot
from app.services.resume_themes import THEMES

IMPORTED = """Alex Morgan
alex@example.com | https://github.com/alex
Summary
Computer science student building backend services and reproducible experiments.
Projects
Service catalog — verified backend implementation
- Built FastAPI endpoints with PostgreSQL transactions and Docker integration tests.
- Ongoing work: validating retry handling; production rollout is not complete.
Experiment workspace — reproducible model evaluation
- Trained PyTorch classifiers and evaluated scikit-learn baselines.
- Documented held-out dataset limitations without claiming production deployment.
Skills
Python, FastAPI, PostgreSQL, Docker, PyTorch, scikit-learn
Education
BSc Computer Science, Example University
"""


@pytest.mark.parametrize("key", THEMES)
def test_imported_resume_uses_theme_and_preserves_its_evidence_once(key):
    snapshot = {"source": "document_import", "imported_text": IMPORTED}
    before = deepcopy(snapshot)
    content = resume_content(snapshot)
    assert content["imported"] and content["sections"]
    assert content["text"] == IMPORTED
    reader = PdfReader(BytesIO(render_pdf(snapshot, key)))
    text = " ".join(" ".join(page.extract_text().split()) for page in reader.pages)
    for value in ("Service catalog", "Experiment workspace", "validating retry handling", "Documented held-out dataset limitations", "BSc Computer Science"):
        assert text.count(value) == 1, (key, value)
    assert text.startswith("Alex Morgan")
    assert snapshot == before
    html = render_preview_html(snapshot, key)
    assert 'class="lead"' in html
    assert '<pre>' not in html


def test_imported_project_blocks_are_tailored_without_changing_claims_or_history():
    snapshot = {"source": "document_import", "imported_text": IMPORTED}
    backend = tailor_snapshot(snapshot, "Backend internship", "Required: FastAPI, PostgreSQL, Docker. Build transactional backend services.")
    ml = tailor_snapshot(snapshot, "AI/ML internship", "Required: PyTorch, scikit-learn. Train classifiers and evaluate models.")
    assert backend["imported_text"].index("Service catalog") < backend["imported_text"].index("Experiment workspace")
    assert ml["imported_text"].index("Experiment workspace") < ml["imported_text"].index("Service catalog")
    assert sorted(backend["imported_text"].splitlines()) == sorted(ml["imported_text"].splitlines())
    assert sorted(ml["imported_text"].splitlines()) == sorted(IMPORTED.splitlines())
    assert snapshot["imported_text"] == IMPORTED
    assert resume_content(ml)["sections"][1]["entries"][0]["lead"].startswith("Experiment workspace")


def test_ambiguous_import_prose_is_not_split_into_invented_projects():
    text = "Alex Morgan\nProjects\nA narrative without explicit boundaries.\nAnother line of work.\nEducation\nExample University"
    document = imported_document(text)
    assert len(document["sections"][0]["blocks"]) == 1
    result = tailor_snapshot({"source": "document_import", "imported_text": text}, "Backend intern", "Build Python services and maintain existing applications.")
    assert result["imported_text"] == text


@pytest.mark.parametrize("key", THEMES)
def test_contact_without_name_and_repeated_evidence_are_not_lost(key):
    text = "alex@example.com\nProjects\nRepeated evidence.\nRepeated evidence."
    result = PdfReader(BytesIO(render_pdf({"source": "document_import", "imported_text": text}, key)))
    extracted = " ".join(page.extract_text() for page in result.pages)
    assert extracted.count("alex@example.com") == 1
    assert extracted.count("Repeated evidence.") == 2


def test_partial_section_order_does_not_silently_omit_qualifications():
    snapshot = quality_snapshot(False)
    snapshot["resume_meta"]["section_order"] = ["projects"]
    snapshot["resume_meta"]["hidden_sections"] = ["skills"]
    keys = [section["key"] for section in resume_content(snapshot)["sections"]]
    assert "education" in keys and "experience" in keys and "projects" in keys
    assert "skills" not in keys


@pytest.mark.parametrize("accent", ("#ffffff", "#ffff00", "#99ffaa", "#173c32", "#000000"))
def test_custom_accent_has_readable_foreground_and_text(accent):
    tokens = design_tokens({"resume_meta": {"design": {"accent": accent}}}, "modern")
    background, foreground = _luminance(accent), _luminance(tokens["on_accent"])
    assert (max(background, foreground) + 0.05) / (min(background, foreground) + 0.05) >= 4.5
    assert 1.05 / (_luminance(tokens["text_accent"]) + 0.05) >= 4.5


@pytest.mark.parametrize("text,expected", (
    ("Python; no experience with Kubernetes.", ["Python"]),
    ("No experience with Python or Docker.", []),
    ("No Kubernetes experience.", []),
    ("Not familiar with PyTorch or scikit-learn.", []),
    ("Plan to learn Kubernetes. Built Docker services.", ["Docker"]),
    ("Will implement Kubernetes after testing. Built a Python API.", ["Python"]),
    ("No downtime with Kubernetes and Docker.", ["Docker", "Kubernetes"]),
    ("No experience with Docker. Used Docker in an older project.", ["Docker"]),
    ("Built Next.js and Node.js services.", ["Next.js", "Node.js"]),
))
def test_only_positive_skill_mentions_are_evidence(text, expected):
    assert find_evidenced_skills(text) == expected


def test_negative_skill_mentions_do_not_satisfy_job_requirements():
    text = "Python developer. No experience with Kubernetes. Plan to learn PyTorch."
    analysis = analyze_job("Engineer", "Required: Kubernetes and PyTorch", text)
    assert "Kubernetes" in analysis["missing_qualifications"]
    assert "PyTorch" in analysis["missing_qualifications"]
    assert "kubernetes" not in analysis["matched_keywords"]
    assert review_resume(text, "Kubernetes and PyTorch")["job_match"]["matched"] == []


@pytest.mark.parametrize("text", (
    "Built a Python 3.12 parser in 2024.", "Developed a Node.js 20 API in 2025.",
    "Built a service from 2021 to 2024.", "Will reduce latency by 40%.",
    "Planning to support 200 users.",
))
def test_dates_versions_and_future_targets_are_not_impact_metrics(text):
    assert not has_impact_evidence(text)


@pytest.mark.parametrize("text", ("Reduced latency by 35%.", "Built validation across 3 services.", "Supported 200 users.", "Saved 4 hours per release."))
def test_verified_scope_and_outcomes_are_recognized(text):
    assert has_impact_evidence(text)


@pytest.mark.parametrize("proposed", (None, [], {"bullet_rewrites": None}, {"bullet_rewrites": [None, "bad", {}]},
                                     {"bullet_rewrites": [{"section": [], "field": "description", "source_id": "p1"}]},
                                     {"bullet_rewrites": [{"section": "projects", "field": {}, "source_id": "p1"}]},
                                     {"bullet_rewrites": [{"section": "projects", "field": "description", "source_id": None}]}))
def test_malformed_provider_output_keeps_grounded_draft(monkeypatch, proposed):
    class Provider:
        def customize_resume(self, **kwargs):
            return proposed

    monkeypatch.setattr("app.services.resume_tailoring.get_ai_provider", lambda: Provider())
    result = tailor_snapshot(quality_snapshot(False), "Backend engineer", "Build Python services with FastAPI and PostgreSQL.")
    assert result["job_target"]["method"] == "grounded_rules"
    assert len(result["projects"]) == 2


def test_inline_required_and_preferred_headings_are_separated():
    result = analyze_job("Engineer", "Required: Python. Preferred: Docker. Responsibilities: Build APIs.", "Python projects")
    assert result["required_qualifications"] == ["Required: Python."]
    assert result["preferred_qualifications"] == ["Preferred: Docker."]


def test_provider_edit_without_record_id_cannot_match_an_unidentified_record(monkeypatch):
    source = quality_snapshot(False)
    source["projects"][0].pop("source_id")
    original = source["projects"][0]["description"]

    class Provider:
        def customize_resume(self, **kwargs):
            return {"bullet_rewrites": [{"section": "projects", "field": "description", "text": original}]}

    monkeypatch.setattr("app.services.resume_tailoring.get_ai_provider", lambda: Provider())
    result = tailor_snapshot(source, "Backend engineer", "Build Python services with FastAPI and PostgreSQL.")
    assert result["job_target"]["method"] == "grounded_rules"
    assert next(item for item in result["projects"] if not item.get("source_id"))["description"] == original


def test_html_bullet_character_is_a_css_escape_not_a_control_character():
    html = render_preview_html(quality_snapshot(False), "modern")
    assert '\\2022' in html
    assert '\x82' not in html


def test_summary_does_not_copy_a_project_bullet_and_duplicate_its_claim():
    snapshot = quality_snapshot(False)
    result = tailor_snapshot(snapshot, "Backend engineer", "Required: Python, FastAPI, PostgreSQL. Build reliable backend services.")
    assert snapshot["projects"][0]["description"] not in result["profile"]["bio"]
    assert "Relevant skills:" in result["profile"]["bio"]


@pytest.mark.parametrize("key", THEMES)
def test_short_tailored_document_does_not_strand_education_on_a_second_page(key):
    result = tailor_snapshot(short_snapshot(), "Backend engineering internship", "Required: Python, FastAPI, PostgreSQL, Docker. Build backend services and validate retry handling.")
    reader = PdfReader(BytesIO(render_pdf(result, key)))
    assert len(reader.pages) == 1
    assert "BSc Computer Science" in reader.pages[0].extract_text()


@pytest.mark.parametrize("key", ("modern", "professional", "developer", "creative"))
def test_imported_long_preamble_flows_instead_of_overflowing_masthead(key):
    text = "Alex Morgan\nalex@example.com\n" + "DetailedPreamble implementation notes. " * 150 + "\nProjects\nBuilt an application."
    reader = PdfReader(BytesIO(render_pdf({"source": "document_import", "imported_text": text}, key)))
    extracted = " ".join(page.extract_text() for page in reader.pages)
    assert extracted.count("DetailedPreamble") == 150
