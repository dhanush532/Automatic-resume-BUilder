from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.user import SecurityTokenPurpose, User
from app.services.security_tokens import security_token_service

PASSWORD = "Trustworthy!234"


@pytest.fixture
def resume_user(client: TestClient, db_session: Session):
    suffix = uuid4().hex[:12]
    payload = {
        "full_name": "Resume Owner",
        "username": f"resume_{suffix}",
        "email": f"resume-{suffix}@example.com",
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


def create_resume(client: TestClient) -> dict[str, object]:
    templates = client.get("/api/v1/resumes/templates")
    assert templates.status_code == 200, templates.text
    assert len(templates.json()) == 7
    return client.post("/api/v1/resumes", json={"name": "My master resume", "template_id": templates.json()[0]["id"], "type": "master"}).json()


def test_resume_crud_versioning_duplicate_restore_and_pdf(client: TestClient, resume_user: dict[str, str]):
    assert client.get("/api/v1/resumes").status_code == 200
    profile = client.put("/api/v1/passport/profile", json={"full_name": "Resume Owner", "headline": "Platform engineer", "bio": "I build reliable platforms."})
    preferences = client.put("/api/v1/passport/preferences", json={"desired_job_titles": ["Platform engineer"], "expected_salary_min": "90000.00", "expected_salary_max": "120000.00", "salary_currency": "USD"})
    education = client.post("/api/v1/passport/education", json={"institution": "State University", "degree": "BSc"})
    assert profile.status_code == 200 and preferences.status_code == 200 and education.status_code == 201

    auto_resumes = client.get("/api/v1/resumes")
    assert auto_resumes.status_code == 200 and len(auto_resumes.json()) == 1
    resume = auto_resumes.json()[0]
    assert resume["name"] == "My resume"
    assert resume["version_count"] == 1
    first = resume["latest_version"]
    assert first["source"] == "passport"
    assert first["content_snapshot"]["profile"]["headline"] == "Platform engineer"

    templates = client.get("/api/v1/resumes/templates").json()
    update = client.patch(f"/api/v1/resumes/{resume['id']}", json={"name": "Platform resume", "template_id": templates[1]["id"]})
    assert update.status_code == 200, update.text
    assert update.json()["version_count"] == 2
    manual = client.post(f"/api/v1/resumes/{resume['id']}/versions", json={"headline_override": "Staff platform engineer", "summary_override": "A reviewed summary.", "change_summary": "Refined headline"})
    assert manual.status_code == 201, manual.text
    versions = client.get(f"/api/v1/resumes/{resume['id']}/versions")
    assert versions.status_code == 200 and [item["version_number"] for item in versions.json()] == [3, 2, 1]

    preview = client.get(f"/api/v1/resumes/{resume['id']}/preview")
    assert preview.status_code == 200 and "Staff platform engineer" in preview.json()["html"]
    pdf = client.get(f"/api/v1/resumes/{resume['id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF-") and b"Staff platform engineer" in pdf.content

    restored = client.post(f"/api/v1/resumes/{resume['id']}/versions/{first['id']}/restore")
    assert restored.status_code == 201, restored.text
    assert restored.json()["version_number"] == 4 and restored.json()["restored_from_version_id"] == first["id"]
    duplicate = client.post(f"/api/v1/resumes/{resume['id']}/duplicate")
    assert duplicate.status_code == 201 and duplicate.json()["version_count"] == 1
    assert client.delete(f"/api/v1/resumes/{duplicate.json()['id']}").status_code == 204
    assert client.get(f"/api/v1/resumes/{duplicate.json()['id']}").status_code == 404


def test_resume_template_validation_and_customization_review(client: TestClient, resume_user: dict[str, str]):
    resume = create_resume(client)
    assert client.post("/api/v1/resumes", json={"name": "Invalid", "template_id": str(uuid4())}).status_code == 422
    invalid = client.post(f"/api/v1/resumes/{resume['id']}/versions", json={"hidden_sections": ["made_up"]})
    assert invalid.status_code == 422
    snapshot = resume["latest_version"]["content_snapshot"]
    evidence = UUID(snapshot["profile"]["source_id"]) if snapshot["profile"]["source_id"] else None
    assert evidence is None
    client.put("/api/v1/passport/profile", json={"full_name": "Resume Owner", "headline": "Engineer"})
    refreshed = client.post(f"/api/v1/resumes/{resume['id']}/versions", json={"change_summary": "Refresh from Career Passport"})
    assert refreshed.status_code == 201
    resume = client.get(f"/api/v1/resumes/{resume['id']}").json()
    evidence = UUID(resume["latest_version"]["content_snapshot"]["profile"]["source_id"])
    base_version_id = resume["latest_version"]["id"]
    bad = client.post(f"/api/v1/resumes/{resume['id']}/customizations", json={"base_version_id": base_version_id, "generated_content": {"summary_override": "Invented", "source_evidence": [str(uuid4())]}})
    assert bad.status_code == 422
    pending = client.post(f"/api/v1/resumes/{resume['id']}/customizations", json={"base_version_id": base_version_id, "generated_content": {"summary_override": "Reviewed summary", "source_evidence": [str(evidence)], "missing_requirements": ["Kubernetes"]}, "changes": ["Tightened summary"]})
    assert pending.status_code == 201, pending.text
    customization_id = pending.json()["id"]
    assert client.post(f"/api/v1/resumes/{resume['id']}/customizations/{customization_id}/reject").json()["status"] == "rejected"
    pending_again = client.post(f"/api/v1/resumes/{resume['id']}/customizations", json={"base_version_id": base_version_id, "generated_content": {"headline_override": "Reviewed engineer", "source_evidence": [str(evidence)]}})
    approved = client.post(f"/api/v1/resumes/{resume['id']}/customizations/{pending_again.json()['id']}/approve")
    assert approved.status_code == 201 and approved.json()["source"] == "ai_approved"
    unavailable = client.post(f"/api/v1/resumes/{resume['id']}/customizations/generate", json={"job_description": "We need a platform engineer with distributed systems experience."})
    assert unavailable.status_code == 503


def test_resume_owner_isolation(client: TestClient, db_session: Session, resume_user: dict[str, str]):
    other_client = TestClient(__import__("app.main", fromlist=["app"]).app)
    suffix = uuid4().hex[:12]
    payload = {"full_name": "Other Resume Owner", "username": f"other_resume_{suffix}", "email": f"other-resume-{suffix}@example.com", "phone": f"+1415{int(suffix[:7], 16) % 10_000_000:07d}", "password": PASSWORD, "confirm_password": PASSWORD, "terms_accepted": True}
    response = other_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    other_id = response.json()["id"]
    other_user = db_session.get(User, other_id)
    assert other_user
    _, raw_token = security_token_service.issue(db_session, user_id=other_user.id, purpose=SecurityTokenPurpose.EMAIL_VERIFICATION, ttl=timedelta(hours=1))
    db_session.commit()
    assert other_client.post("/api/v1/auth/verify-email", json={"token": raw_token}).status_code == 200
    assert other_client.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": PASSWORD}).status_code == 200
    other_resume = create_resume(other_client)
    assert client.get(f"/api/v1/resumes/{other_resume['id']}").status_code == 404
    assert client.patch(f"/api/v1/resumes/{other_resume['id']}", json={"name": "stolen"}).status_code == 404
    assert client.get(f"/api/v1/resumes/{other_resume['id']}/versions").status_code == 404
    assert client.delete(f"/api/v1/resumes/{other_resume['id']}").status_code == 404
    db_session.rollback()
    db_session.execute(delete(User).where(User.id == other_id))
    db_session.commit()
    other_client.close()
