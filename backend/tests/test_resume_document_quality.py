"""Content integrity, pagination, grounding, and exact-PDF preview regressions."""
import re
from base64 import b64decode
from copy import deepcopy
from io import BytesIO

import pytest
from pypdf import PdfReader
from resume_quality_fixture import quality_snapshot, short_snapshot
from test_job_targeting_and_themes import resume_user  # noqa: F401

from app.services.pdf import render_pdf, resume_content
from app.services.resume_tailoring import analyze_job, concise, tailor_snapshot
from app.services.resume_themes import THEMES


def pages(snapshot, key):
    reader = PdfReader(BytesIO(render_pdf(snapshot, key)))
    return reader, [page.extract_text() or "" for page in reader.pages]


@pytest.mark.parametrize("key", THEMES)
def test_long_documents_keep_all_evidence_once_and_headings_with_first_bullet(key):
    source = quality_snapshot()
    before = deepcopy(source)
    reader, text_pages = pages(source, key)
    assert source == before
    assert 2 <= len(text_pages) <= 5
    text = " ".join(text_pages)
    assert text_pages[0].lstrip().startswith("Alex Morgan")
    assert "\ufffd" not in text and "\x7f" not in text
    for index in range(7):
        for letter in "ABCD":
            assert text.count(f"Evidence{index}{letter}") == 1, (key, index, letter)
        title_page = next(i for i, page in enumerate(text_pages) if f"Project{index}" in page)
        assert f"Evidence{index}A" in text_pages[title_page], (key, index)
    assert text.count("Faculty scholarship") == 1
    assert text.count("Grade: 3.8 / 4.0") == 1
    assert text.count("SKILLS") == 1
    assert text.count("EDUCATION") == 1
    assert "BSc Computer Science" in next(page for page in text_pages if "EDUCATION" in page)
    assert "Python" in next(page for page in text_pages if "SKILLS" in page)
    assert "EXPERIENCE" in text_pages[0]  # No masthead-only first page.
    assert all(len(page.split()) > 20 for page in text_pages)  # No empty/tiny tail pages.
    assert all(abs(float(page.mediabox.width) - 595.276) < 0.1 for page in reader.pages)
    assert all(abs(float(page.mediabox.height) - 841.89) < 0.1 for page in reader.pages)
    assert any(page.get("/Annots") for page in reader.pages)
    assert any("/ToUnicode" in font.get_object() for page in reader.pages for font in page["/Resources"]["/Font"].get_object().values())


@pytest.mark.parametrize("key", THEMES)
def test_short_document_is_readable_without_forcing_small_text(key):
    snapshot = short_snapshot()
    reader, text = pages(snapshot, key)
    assert len(reader.pages) == 1
    assert "Evidence0D" in " ".join(text)


@pytest.mark.parametrize("key", ("professional", "developer", "ats_readable"))
def test_single_over_page_bullet_can_split_without_losing_content(key):
    snapshot = quality_snapshot(long=False)
    snapshot["projects"] = [{"name": "Oversized project", "description": "StartMarker " + "Documented implementation detail and failure handling. " * 250 + "EndMarker"}]
    _, text_pages = pages(snapshot, key)
    text = " ".join(text_pages)
    assert len(text_pages) > 1
    assert text.count("StartMarker") == text.count("EndMarker") == 1


def test_sidebar_rail_outlives_main_and_does_not_repeat_or_drop_entries():
    snapshot = quality_snapshot(long=False)
    snapshot["projects"] = []
    snapshot["education"] = [{"degree": f"QualificationMarker{i}", "institution": "Example University", "description": "Relevant coursework and verified education detail. " * 5} for i in range(25)]
    _, text_pages = pages(snapshot, "developer")
    assert len(text_pages) > 2
    text = " ".join(text_pages)
    for index in range(25):
        assert len(re.findall(rf"\bQualificationMarker{index}\b", text)) == 1
    assert text.count("SKILLS") == 1
    assert "QualificationMarker24" in text_pages[-1]


def test_duplicate_section_order_and_duplicate_bullets_do_not_duplicate_content():
    snapshot = quality_snapshot(long=False)
    snapshot["resume_meta"]["section_order"] += ["projects"]
    snapshot["projects"][0]["features"] = "  - " + snapshot["projects"][0]["description"]
    sections = resume_content(snapshot)["sections"]
    assert [section["key"] for section in sections].count("projects") == 1
    assert sections[2]["entries"][0]["lines"].count(snapshot["projects"][0]["description"]) == 1


def test_backend_and_ml_roles_prioritize_different_verified_projects_and_summaries():
    source = quality_snapshot()
    before = deepcopy(source)
    backend = tailor_snapshot(source, "Backend engineering internship", "Required: FastAPI, PostgreSQL, SQL, Docker. Build backend services and implement retry handling.")
    ml = tailor_snapshot(source, "AI/ML internship", "Required: PyTorch, scikit-learn, machine learning. Train classifiers and evaluate model baselines.")
    assert "backend" in backend["projects"][0]["name"]
    assert "machine learning" in ml["projects"][0]["name"]
    assert backend["profile"]["bio"] != ml["profile"]["bio"]
    assert source == before
    for result in (backend, ml):
        assert {item["source_id"] for item in result["projects"]} == {item["source_id"] for item in source["projects"]}
        assert all("production rollout is not complete" in item["results"] for item in result["projects"])
        again = tailor_snapshot(result, result["job_target"]["title"], result["job_target"]["description"])
        assert again["profile"]["bio"] == result["profile"]["bio"]


def test_responsibility_and_supporting_work_do_not_become_completed_or_owned_work():
    assert concise("Responsible for implementing authentication; work is ongoing.") == "Implementing authentication; work is ongoing."
    assert concise("Helped with designing the API.") == "Helped with designing the API."
    assert concise("Worked on testing the service.") == "Worked on testing the service."
    assert concise("Will deploy after testing.") == "Will deploy after testing."


def test_required_and_preferred_qualifications_are_separate():
    analysis = analyze_job("Backend intern", "Requirements:\nPython and SQL\nPreferred:\nKubernetes experience\nResponsibilities:\nBuild APIs", "Python and SQL projects")
    assert "Python and SQL" in analysis["required_qualifications"]
    assert "Kubernetes experience" in analysis["preferred_qualifications"]
    assert "Kubernetes experience" not in analysis["required_qualifications"]
    assert "Kubernetes" in analysis["missing_qualifications"]


def test_provider_cannot_remove_future_tense(monkeypatch):
    source = quality_snapshot(long=False)
    source["projects"][0]["description"] = "Will implement authentication after integration testing."

    class Provider:
        def customize_resume(self, **kwargs):
            return {"bullet_rewrites": [{"section": "projects", "field": "description", "source_id": "project-0", "text": "Implement authentication after integration testing."}]}

    monkeypatch.setattr("app.services.resume_tailoring.get_ai_provider", lambda: Provider())
    result = tailor_snapshot(source, "Backend intern", "Build backend services with Python and FastAPI.")
    assert next(item for item in result["projects"] if item["source_id"] == "project-0")["description"].startswith("Will implement")
    assert result["job_target"]["method"] == "grounded_rules"


@pytest.mark.usefixtures("resume_user")
def test_preview_is_byte_identical_to_export_and_theme_only_edit_preserves_content(client):
    client.put("/api/v1/passport/profile", json={"full_name": "PDF Owner", "headline": "Engineer", "bio": "Building verified projects with explicit implementation notes and tests."})
    resume = client.get("/api/v1/resumes").json()[0]
    resume_id = resume["id"]
    saved = client.post(f"/api/v1/resumes/{resume_id}/versions", json={"summary_override": "A carefully edited summary.", "hidden_sections": ["education"]})
    assert saved.status_code == 201
    templates = client.get("/api/v1/resumes/templates").json()
    themed = client.post(f"/api/v1/resumes/{resume_id}/versions", json={"template_id": templates[1]["id"], "design": {"margin_mm": 20}})
    snapshot = themed.json()["content_snapshot"]
    assert snapshot["profile"]["bio"] == "A carefully edited summary."
    assert snapshot["resume_meta"]["hidden_sections"] == ["education"]
    preview = client.get(f"/api/v1/resumes/{resume_id}/preview?include_pdf=true")
    export = client.get(f"/api/v1/resumes/{resume_id}/pdf")
    assert b64decode(preview.json()["pdf_base64"]) == export.content
    draft = client.post("/api/v1/resumes/preview", json={"template_id": templates[0]["id"], "base_resume_id": resume_id, "include_pdf": True, "edits": {"summary_override": "Unsaved document evidence."}})
    assert draft.status_code == 200
    draft_pdf = b64decode(draft.json()["pdf_base64"])
    assert "Unsaved document evidence." in PdfReader(BytesIO(draft_pdf)).pages[0].extract_text()
    assert client.get(f"/api/v1/resumes/{resume_id}").json()["latest_version"]["id"] == themed.json()["id"]
