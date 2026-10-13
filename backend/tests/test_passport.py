from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.user import SecurityTokenPurpose, User
from app.services.security_tokens import security_token_service

PASSWORD = "Trustworthy!234"


@pytest.fixture
def passport_user(client: TestClient, db_session: Session):
    suffix = uuid4().hex[:12]
    payload = {
        "full_name": "Passport Owner",
        "username": f"passport_{suffix}",
        "email": f"passport-{suffix}@example.com",
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
    _, raw_token = security_token_service.issue(
        db_session,
        user_id=user.id,
        purpose=SecurityTokenPurpose.EMAIL_VERIFICATION,
        ttl=timedelta(hours=1),
    )
    db_session.commit()
    assert client.post("/api/v1/auth/verify-email", json={"token": raw_token}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": PASSWORD}).status_code == 200
    yield {"id": user_id, **payload}
    db_session.rollback()
    db_session.execute(delete(User).where(User.id == user_id))
    db_session.commit()


def test_unauthenticated_passport_is_rejected(client: TestClient):
    assert client.get("/api/v1/passport").status_code == 401


def test_passport_sections_crud_and_validation(client: TestClient, passport_user: dict[str, str]):
    profile = client.put(
        "/api/v1/passport/profile",
        json={
            "full_name": "Passport Owner Updated",
            "headline": "Backend engineer",
            "bio": "I build dependable systems.",
            "location": "Remote",
            "linkedin_url": "https://linkedin.com/in/passport-owner",
            "github_url": "https://github.com/passport-owner",
            "portfolio_url": "https://passport.example.com",
            "profile_photo_key": None,
            "other_links": [],
        },
    )
    assert profile.status_code == 200, profile.text
    assert client.get("/api/v1/passport/profile").json()["headline"] == "Backend engineer"

    preferences = client.put(
        "/api/v1/passport/preferences",
        json={
            "desired_job_titles": ["Backend engineer"],
            "industries": ["SaaS"],
            "preferred_locations": ["Remote"],
            "work_arrangements": ["remote"],
            "employment_types": ["full_time"],
            "expected_salary_min": "90000.00",
            "expected_salary_max": "120000.00",
            "salary_currency": "usd",
            "willing_to_relocate": False,
            "preferred_company_sizes": ["startup"],
            "company_preferences": "Mission-driven teams",
            "exclusions": ["Night shift"],
        },
    )
    assert preferences.status_code == 200, preferences.text
    assert preferences.json()["salary_currency"] == "USD"

    link = client.post("/api/v1/passport/links", json={"label": "Portfolio", "url": "https://portfolio.example.com"})
    education = client.post("/api/v1/passport/education", json={"institution": "State University", "degree": "BSc", "field_of_study": "Computer Science"})
    skill = client.post("/api/v1/passport/skills", json={"name": "Python", "category": "Programming", "proficiency": "advanced", "experience_months": 60})
    assert link.status_code == 201 and education.status_code == 201 and skill.status_code == 201
    skill_id = skill.json()["skill_id"]
    experience = client.post(
        "/api/v1/passport/experience",
        json={"company": "Acme", "title": "Engineer", "employment_type": "full_time", "start_date": "2022-01-01", "is_current": True, "skill_ids": [skill_id]},
    )
    project = client.post("/api/v1/passport/projects", json={"name": "CareerPilot", "github_url": "https://github.com/example/careerpilot", "skill_ids": [skill_id]})
    certification = client.post("/api/v1/passport/certifications", json={"name": "Cloud Associate", "issuer": "Cloud Org"})
    course = client.post("/api/v1/passport/courses", json={"name": "Distributed Systems", "provider": "Open Learning"})
    achievement = client.post("/api/v1/passport/achievements", json={"title": "Shipped a platform", "organization": "Acme"})
    language = client.post("/api/v1/passport/languages", json={"language": "English", "proficiency": "native"})
    contribution = client.post("/api/v1/passport/open-source", json={"repository": "example/project", "contribution": "Bug fix", "url": "https://github.com/example/project/pull/1"})
    assert all(response.status_code == 201 for response in (experience, project, certification, course, achievement, language, contribution)), [response.text for response in (experience, project, certification, course, achievement, language, contribution)]

    aggregate = client.get("/api/v1/passport")
    assert aggregate.status_code == 200, aggregate.text
    data = aggregate.json()
    assert data["profile"]["full_name"] == "Passport Owner Updated"
    assert len(data["professional_links"]) == 1
    assert len(data["education"]) == len(data["skills"]) == len(data["experience"]) == len(data["projects"]) == 1
    assert data["completeness"] > 0

    assert client.patch(f"/api/v1/passport/education/{education.json()['id']}", json={"institution": "State University", "degree": "MSc"}).status_code == 200
    assert client.delete(f"/api/v1/passport/courses/{course.json()['id']}").status_code == 204
    assert client.get("/api/v1/passport/courses").json() == []
    assert client.post("/api/v1/passport/languages", json={"language": "English", "proficiency": "fluent"}).status_code == 409
    assert client.post("/api/v1/passport/links", json={"label": "Bad", "url": "javascript:alert(1)"}).status_code == 422
    assert client.put("/api/v1/passport/preferences", json={"expected_salary_min": 200, "expected_salary_max": 100}).status_code == 422
    assert client.post("/api/v1/passport/experience", json={"company": "Acme", "title": "Engineer", "employment_type": "full_time", "start_date": "2024-01-01", "end_date": "2023-01-01"}).status_code == 422


def test_passport_isolation_between_users(client: TestClient, db_session: Session, passport_user: dict[str, str]):
    other_client = TestClient(__import__("app.main", fromlist=["app"]).app)
    suffix = uuid4().hex[:12]
    payload = {
        "full_name": "Other Owner",
        "username": f"other_{suffix}",
        "email": f"other-{suffix}@example.com",
        "phone": f"+1415{int(suffix[:7], 16) % 10_000_000:07d}",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "terms_accepted": True,
    }
    response = other_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    other_id = response.json()["id"]
    other_user = db_session.get(User, other_id)
    assert other_user
    _, raw_token = security_token_service.issue(db_session, user_id=other_user.id, purpose=SecurityTokenPurpose.EMAIL_VERIFICATION, ttl=timedelta(hours=1))
    db_session.commit()
    assert other_client.post("/api/v1/auth/verify-email", json={"token": raw_token}).status_code == 200
    assert other_client.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": PASSWORD}).status_code == 200
    other_profile = other_client.put("/api/v1/passport/profile", json={"full_name": "Other Owner", "headline": "Private"})
    other_education = other_client.post("/api/v1/passport/education", json={"institution": "Private College", "degree": "BA"})
    other_project = other_client.post("/api/v1/passport/projects", json={"name": "Private Project"})
    assert other_profile.status_code == 200 and other_education.status_code == 201 and other_project.status_code == 201

    own = client.get("/api/v1/passport").json()
    assert own["profile"] is None and own["education"] == [] and own["projects"] == []
    assert client.delete(f"/api/v1/passport/education/{other_education.json()['id']}").status_code == 404
    assert client.patch(f"/api/v1/passport/projects/{other_project.json()['id']}", json={"name": "Attempt"}).status_code == 404
    assert client.get("/api/v1/passport/profile").json() is None

    db_session.rollback()
    db_session.execute(delete(User).where(User.id == other_id))
    db_session.commit()
    other_client.close()
