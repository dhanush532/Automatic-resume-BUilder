"""Job-specific resume generation, design customization, and theme rendering."""
import re
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.user import SecurityTokenPurpose, User
from app.services.pdf import render_pdf, render_preview_html, resume_content
from app.services.resume_tailoring import tailor_snapshot, text_of
from app.services.resume_themes import THEMES, recommended_theme
from app.services.security_tokens import security_token_service

PASSWORD = "Trustworthy!234"
JD = (
    "We are hiring a Senior Python Engineer to build data platforms.\n"
    "Requirements: 5 years experience, Bachelor's degree, Kubernetes required.\n"
    "Responsibilities: build services, maintain pipelines, lead code reviews, collaborate with product teams."
)
SIX_KEYS = ("minimal", "modern", "ats_readable", "professional", "developer", "creative")


def _snapshot() -> dict:
    return {
        "schema_version": 1,
        "source": "career_passport",
        "profile": {"full_name": "Alex Morgan", "headline": "Platform engineer", "bio": "I build reliable platforms and lead small delivery teams.", "email": "alex@example.com", "location": "Berlin"},
        "professional_links": [{"source_id": "l1", "label": "Site", "url": "https://alex.dev"}],
        "career_preferences": None,
        "education": [{"source_id": "e1", "degree": "BSc Computer Science", "institution": "Example University", "start_date": "2014", "end_date": "2018", "description": ""}],
        "skills": [{"source_id": "s1", "name": "Python", "proficiency": "Advanced"}, {"source_id": "s2", "name": "React", "proficiency": "Intermediate"}],
        "experience": [
            {"source_id": "x1", "title": "Platform engineer", "company": "ACME", "start_date": "2020-01-01", "end_date": None, "description": "Responsible for building data pipelines serving 200 users.", "achievements": "Reduced latency by 35%.", "technology_notes": "Python, FastAPI"},
            {"source_id": "x2", "title": "Developer", "company": "Globex", "start_date": "2017-06-01", "end_date": "2020-01-01", "description": "Maintained React dashboards for support teams.", "achievements": "", "technology_notes": "React, SQL"},
        ],
        "projects": [{"source_id": "p1", "name": "Job tracker", "description": "Accessible job tracking workspace.", "results": "Used by 120 job seekers", "github_url": "https://github.com/alex/tracker", "live_url": "", "features": "", "problem_solved": ""}],
        "certifications": [], "courses": [], "achievements": [], "languages": [], "open_source_contributions": [],
        "resume_meta": {"hidden_sections": [], "section_order": ["profile", "professional_links", "experience", "projects", "education", "skills", "certifications", "courses", "achievements", "languages", "open_source_contributions"]},
    }


def _long_snapshot() -> dict:
    snap = _snapshot()
    snap["experience"] = [
        {"source_id": f"x{i}", "title": f"Engineer {i}", "company": "ACME", "start_date": "2020-01-01", "end_date": "2021-01-01",
         "description": f"Built APIs number {i} serving 200 users with important content. " * 5, "achievements": f"Cut latency by {i}%.", "technology_notes": "Python, Docker"}
        for i in range(12)
    ]
    snap["projects"] = [
        {"source_id": f"p{i}", "name": f"Project {i}", "description": "Tracking workspace with important content. " * 6, "results": f"{i}00 adopters", "github_url": "", "live_url": "", "features": "", "problem_solved": ""}
        for i in range(6)
    ]
    return snap


@pytest.fixture
def resume_user(client: TestClient, db_session: Session):
    suffix = uuid4().hex[:12]
    payload = {
        "full_name": "Tailoring Owner",
        "username": f"tailor_{suffix}",
        "email": f"tailor-{suffix}@example.com",
        "phone": f"+1415{int(suffix[:7], 16) % 10_000_000:07d}",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "terms_accepted": True,
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    user = db_session.get(User, user_id)
    assert user
    _, raw_token = security_token_service.issue(db_session, user_id=user.id, purpose=SecurityTokenPurpose.EMAIL_VERIFICATION, ttl=timedelta(hours=1))
    db_session.commit()
    assert client.post("/api/v1/auth/verify-email", json={"token": raw_token}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": PASSWORD}).status_code == 200
    yield {"id": user_id, **payload}
    db_session.rollback()
    db_session.execute(delete(User).where(User.id == user_id))
    db_session.commit()


def test_tailoring_reorders_evidence_and_never_invents_facts():
    source = _snapshot()
    untouched = deepcopy(source)
    result = tailor_snapshot(source, "Senior Python Engineer", JD)
    assert source == untouched
    assert result["source"] == "job_tailored"
    assert result["profile"]["headline"] == "Target role: Senior Python Engineer"
    # No numbers or skills may be invented.
    assert set(re.findall(r"\d+", text_of(result))) <= set(re.findall(r"\d+", text_of(source)))
    assert {item["name"] for item in result["skills"]} <= {item["name"] for item in source["skills"]}
    # Wording is tightened, not replaced: owned metrics survive.
    descriptions = " ".join(item.get("description", "") for item in result["experience"])
    assert "200 users" in descriptions
    assert "Reduced latency by 35%." in " ".join(item.get("achievements", "") for item in result["experience"])
    analysis = result["job_target"]["analysis"]
    assert "Python" in analysis["skills"]
    assert "Kubernetes" in analysis["missing_qualifications"]
    assert analysis["qualification_note"].startswith("Not evidenced")
    assert result["job_target"]["method"] == "grounded_rules"
    assert result["job_target"]["recommended_template_key"] == "ats_readable"


def test_tailoring_requires_minimum_owned_evidence():
    with pytest.raises(ValueError, match="Add experience"):
        tailor_snapshot({"source": "career_passport", "profile": {"bio": "Too short."}, "resume_meta": {}}, "Python Engineer", JD)


def test_tailoring_of_imported_text_keeps_reading_order():
    source = {
        "source": "document_import",
        "imported_text": "Alex Morgan\nalex@example.com\nExperience\nResponsible for building data pipelines serving 200 users.\nReduced latency by 35%.\nSkills\nPython, React, SQL",
        "resume_meta": {},
    }
    result = tailor_snapshot(source, "Python Engineer", JD)
    assert result["source"] == "document_import"
    assert "job_target" in result
    lines = result["imported_text"].splitlines()
    assert lines[0] == "Alex Morgan" and lines[1] == "alex@example.com"
    assert "Building data pipelines serving 200 users." in lines
    assert "200 users" in result["imported_text"]


def test_six_distinct_layouts_and_role_recommendations():
    layouts = [THEMES[key]["layout"] for key in SIX_KEYS]
    assert len(set(layouts)) == 6
    assert THEMES["student"]["layout"] == "banded"
    assert recommended_theme("Senior data engineer") == "ats_readable"
    assert recommended_theme("Chief of staff") == "minimal"
    assert recommended_theme("Editor") == "professional"
    assert recommended_theme("Product designer") == "creative"
    assert recommended_theme("Sales manager") == "modern"


@pytest.mark.parametrize("key", list(THEMES))
def test_each_theme_renders_html_and_searchable_pdf(key):
    snap = _snapshot()
    html = render_preview_html(snap, key)
    assert "Alex Morgan" in html and f'data-layout="{THEMES[key]["layout"]}"' in html
    pdf = render_pdf(snap, key)
    reader = PdfReader(BytesIO(pdf))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "Alex Morgan" in text and "Reduced latency by 35%." in text, key


def test_theme_previews_are_visually_distinct():
    snap = _snapshot()
    html = {key: render_preview_html(snap, key) for key in THEMES}
    assert len(set(html.values())) == len(THEMES)
    assert len({THEMES[key]["layout"] for key in SIX_KEYS}) == 6


@pytest.mark.parametrize("key", list(THEMES))
def test_long_content_paginates_for_every_theme(key):
    pdf = render_pdf(_long_snapshot(), key)
    reader = PdfReader(BytesIO(pdf))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) > 1, key
    assert "Engineer 11" in text, key


def test_job_specific_creation_is_isolated_from_master(client: TestClient, resume_user: dict):
    profile = client.put("/api/v1/passport/profile", json={"full_name": "Tailoring Owner", "headline": "Platform engineer", "bio": "I build reliable platforms for teams and mentor engineers on delivery practices."})
    assert profile.status_code == 200
    assert client.post("/api/v1/passport/education", json={"institution": "State University", "degree": "BSc Computer Science"}).status_code == 201
    resumes = client.get("/api/v1/resumes").json()
    assert len(resumes) == 1
    master = resumes[0]
    master_version = master["latest_version"]["id"]
    templates = client.get("/api/v1/resumes/templates").json()

    target = client.post("/api/v1/resumes", json={
        "name": "Tailoring Owner — Senior Platform Engineer", "template_id": templates[0]["id"],
        "base_resume_id": master["id"], "target_job_title": "Senior Platform Engineer", "job_description": JD,
    })
    assert target.status_code == 201, target.text
    created = target.json()
    assert created["type"] == "job_specific"
    snapshot = created["latest_version"]["content_snapshot"]
    assert snapshot["job_target"]["title"] == "Senior Platform Engineer"
    assert snapshot["profile"]["headline"] == "Target role: Senior Platform Engineer"
    assert "Kubernetes" in snapshot["job_target"]["analysis"]["missing_qualifications"]

    # The master resume and its versions are untouched.
    after = client.get(f"/api/v1/resumes/{master['id']}").json()
    assert after["latest_version"]["id"] == master_version
    assert "job_target" not in after["latest_version"]["content_snapshot"]

    # Further edits on the job-specific draft keep the job target.
    edited = client.post(f"/api/v1/resumes/{created['id']}/versions", json={"headline_override": "Refined platform headline", "change_summary": "Tweak summary"})
    assert edited.status_code == 201, edited.text
    assert edited.json()["content_snapshot"]["job_target"]["title"] == "Senior Platform Engineer"
    assert client.get(f"/api/v1/resumes/{created['id']}/preview").json()["html"].count("Refined platform headline") >= 1

    # Partial target input is rejected.
    bad = client.post("/api/v1/resumes", json={"name": "Bad", "template_id": templates[0]["id"], "target_job_title": "Engineer"})
    assert bad.status_code == 422


def test_draft_preview_renders_unsaved_edits_and_design(client: TestClient, resume_user: dict):
    profile = client.put("/api/v1/passport/profile", json={"full_name": "Preview Owner", "headline": "Data engineer", "bio": "I design data systems and keep pipelines observable for the teams I support."})
    assert profile.status_code == 200
    resume = client.get("/api/v1/resumes").json()[0]
    templates = {item["template_key"]: item for item in client.get("/api/v1/resumes/templates").json()}

    preview = client.post("/api/v1/resumes/preview", json={
        "template_id": templates["minimal"]["id"], "base_resume_id": resume["id"],
        "edits": {"headline_override": "Senior data engineer", "design": {"accent": "#8B0000", "font": "mono", "spacing": "compact", "margin_mm": 13}},
    })
    assert preview.status_code == 200, preview.text
    html = preview.json()["html"]
    assert "Senior data engineer" in html
    assert "#8b0000" in html.lower()
    assert 'data-layout="centered"' in html
    assert preview.json()["template_key"] == "minimal"

    side = client.post("/api/v1/resumes/preview", json={"template_id": templates["developer"]["id"], "base_resume_id": resume["id"]})
    assert side.status_code == 200 and 'data-layout="sidebar"' in side.json()["html"]

    ats = client.post("/api/v1/resumes/preview", json={"template_id": templates["developer"]["id"], "base_resume_id": resume["id"], "ats_safe": True})
    assert ats.json()["template_key"] == "ats_readable"

    unknown = client.post("/api/v1/resumes/preview", json={"template_id": str(uuid4()), "base_resume_id": resume["id"]})
    assert unknown.status_code == 422


def test_design_persists_in_versions_and_pdf_ats_toggle(client: TestClient, resume_user: dict):
    client.put("/api/v1/passport/profile", json={"full_name": "Design Owner", "headline": "Frontend engineer", "bio": "I craft accessible interfaces and maintain the design system for web products."})
    resume = client.get("/api/v1/resumes").json()[0]
    saved = client.post(f"/api/v1/resumes/{resume['id']}/versions", json={
        "design": {"accent": "#123456", "font": "serif", "spacing": "compact", "margin_mm": 14}, "change_summary": "Design tweak",
    })
    assert saved.status_code == 201, saved.text
    assert saved.json()["content_snapshot"]["resume_meta"]["design"]["accent"] == "#123456"
    assert "#123456" in client.get(f"/api/v1/resumes/{resume['id']}/preview").json()["html"].lower()
    pdf = client.get(f"/api/v1/resumes/{resume['id']}/pdf?ats_safe=true")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    invalid = client.post(f"/api/v1/resumes/{resume['id']}/versions", json={"design": {"accent": "red"}})
    assert invalid.status_code == 422


def test_templates_expose_theme_metadata_and_recommendations(client: TestClient, resume_user: dict):
    templates = client.get("/api/v1/resumes/templates").json()
    assert len(templates) == 7
    assert {item["layout"] for item in templates} == {"centered", "banded", "plain", "editorial", "sidebar", "balanced"}
    assert all(item["display_name"] and item["description"] for item in templates)
    assert sum(1 for item in templates if item["ats_safe"]) == 5
    recommended = client.get("/api/v1/resumes/templates", params={"role": "Backend engineer"}).json()
    assert [item["template_key"] for item in recommended if item["recommended"]] == ["ats_readable"]
    creative = client.get("/api/v1/resumes/templates", params={"role": "Product designer"}).json()
    assert [item["template_key"] for item in creative if item["recommended"]] == ["creative"]


def test_resume_content_hides_sections_and_preserves_import_order():
    snap = _snapshot()
    snap["resume_meta"]["hidden_sections"] = ["skills"]
    content = resume_content(snap)
    assert content["header"]["name"] == "Alex Morgan"
    assert "skills" not in {section["key"] for section in content["sections"]}
    imported = resume_content({"source": "document_import", "imported_text": "Line one\nLine two"})
    assert imported["imported"] is True and imported["text"] == "Line one\nLine two"
