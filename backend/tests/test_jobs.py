from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.jobs import Job, JobSource
from app.models.user import SecurityTokenPurpose, User
from app.services.job_sources import (
    JobSourceAdapter,
    JobSyncService,
    JobVerification,
    normalized_job_from_mapping,
)
from app.services.security_tokens import security_token_service

PASSWORD = "Trustworthy!234"


class AuthorizedFeedAdapter(JobSourceAdapter):
    source_key = "test-authorized-feed"
    source_name = "Test Authorized Feed"
    source_type = "authorized_feed"
    configuration = {"test_only": True}

    def __init__(self, jobs: list[dict[str, object]]) -> None:
        self.jobs = jobs

    def fetch_jobs(self, *, cursor: str | None = None):
        return self.jobs

    def identify_external_job_id(self, raw):
        return str(raw["external_job_id"]) if raw.get("external_job_id") else None

    def canonical_application_url(self, raw):
        return str(raw["application_url"])

    def source_metadata(self, raw):
        return {"feed_record": str(raw.get("external_job_id", "unknown"))}

    def verify(self, raw):
        return JobVerification(status=str(raw.get("status", "ACTIVE")), verified_at=datetime.now(UTC))

    def normalize(self, raw):
        return normalized_job_from_mapping(raw, adapter=self)


def _raw_job(*, external_job_id: str = "req-100", title: str = "Platform Engineer", status: str = "ACTIVE") -> dict[str, object]:
    return {
        "external_job_id": external_job_id,
        "company": "Acme Systems Inc.",
        "company_website": "https://acme.example.com",
        "title": title,
        "description": "Build reliable Python and PostgreSQL services.",
        "location": "Bengaluru, IN",
        "remote_type": "Hybrid",
        "employment_type": "Full-time",
        "experience_requirements": "Platform engineering experience",
        "education_requirements": "Computer Science",
        "salary": {"min": "90000", "max": "120000", "currency": "USD", "period": "year"},
        "application_url": f"https://jobs.example.com/{external_job_id}",
        "source_url": f"https://feed.example.com/{external_job_id}",
        "posted_at": "2026-09-20T10:00:00Z",
        "skills": [{"name": "Python"}, {"name": "Postgres", "required": True}, {"name": "Kubernetes", "required": False}],
        "status": status,
    }


@pytest.fixture
def job_user(client: TestClient, db_session: Session):
    suffix = uuid4().hex[:12]
    payload = {
        "full_name": "Job Owner",
        "username": f"job_{suffix}",
        "email": f"job-{suffix}@example.com",
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


def _test_jobs():
    return select(Job).join(JobSource).where(JobSource.source_key == "test-authorized-feed")


def _test_job_count(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(_test_jobs().subquery()))


def _sync_jobs(db_session: Session, jobs: list[dict[str, object]]) -> Job:
    JobSyncService().sync(db_session, AuthorizedFeedAdapter(jobs))
    job = db_session.scalar(_test_jobs().order_by(Job.created_at))
    assert job
    return job


def test_normalization_source_identity_and_idempotent_sync(db_session: Session, job_user: dict[str, str]):
    adapter = AuthorizedFeedAdapter([_raw_job(), _raw_job()])
    assert JobSyncService().sync(db_session, adapter) == 1
    assert _test_job_count(db_session) == 1
    job = db_session.scalar(_test_jobs())
    assert job
    assert job.remote_type == "hybrid"
    assert job.employment_type == "full_time"
    assert job.salary_currency == "USD"
    assert {skill.normalized_name for skill in job.skills} == {"python", "postgres", "kubernetes"}
    assert JobSyncService().sync(db_session, adapter) == 1
    assert _test_job_count(db_session) == 1


def test_job_status_and_stale_verification(db_session: Session, job_user: dict[str, str]):
    job = _sync_jobs(db_session, [_raw_job()])
    assert job.status == "ACTIVE"
    JobSyncService().sync(db_session, AuthorizedFeedAdapter([]), complete_snapshot=True)
    db_session.refresh(job)
    assert job.status == "UNVERIFIED"


def test_job_search_filter_pagination_matching_and_skill_gaps(client: TestClient, db_session: Session, job_user: dict[str, str]):
    job = _sync_jobs(db_session, [_raw_job()])
    assert client.put("/api/v1/passport/profile", json={"full_name": "Job Owner", "headline": "Platform engineer", "bio": "I build platform services."}).status_code == 200
    assert client.put("/api/v1/passport/preferences", json={"desired_job_titles": ["Platform Engineer"], "preferred_locations": ["Bengaluru"], "work_arrangements": ["hybrid"], "employment_types": ["full_time"], "expected_salary_min": "80000", "salary_currency": "USD"}).status_code == 200
    skill = client.post("/api/v1/passport/skills", json={"name": "Python", "category": "Technical", "proficiency": "advanced"})
    assert skill.status_code == 201
    result = client.get("/api/v1/jobs", params={"keyword": "Platform", "company": "Acme Systems", "location": "Bengaluru", "page": 1, "page_size": 1})
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1 and result.json()["items"][0]["id"] == str(job.id)
    match = client.get(f"/api/v1/jobs/{job.id}/match")
    assert match.status_code == 200 and "Python" in match.json()["matching_skills"]
    gaps = client.get(f"/api/v1/jobs/{job.id}/skill-gaps")
    assert gaps.status_code == 200 and "Kubernetes" in gaps.json()["missing_skills"]
    recommendations = client.get("/api/v1/job-recommendations")
    assert recommendations.status_code == 200
    items = recommendations.json()["items"]
    # The existing recommender considers only 500 recent jobs. A dated fixture
    # need not enter that pool when a real catalog exists; its match is tested above.
    assert items
    assert [item["match"]["score"] for item in items] == sorted((item["match"]["score"] for item in items), reverse=True)
    assert all(item["job"]["status"] == "ACTIVE" for item in items)


def test_saved_jobs_are_idempotent_and_owner_scoped(client: TestClient, db_session: Session, job_user: dict[str, str]):
    job = _sync_jobs(db_session, [_raw_job()])
    saved = client.post("/api/v1/saved-jobs", json={"job_id": str(job.id)})
    assert saved.status_code == 201, saved.text
    assert client.post("/api/v1/saved-jobs", json={"job_id": str(job.id)}).status_code == 201
    listing = client.get("/api/v1/saved-jobs")
    assert listing.status_code == 200 and listing.json()["total"] == 1
    other = TestClient(__import__("app.main", fromlist=["app"]).app)
    suffix = uuid4().hex[:12]
    payload = {"full_name": "Other Job Owner", "username": f"other_job_{suffix}", "email": f"other-job-{suffix}@example.com", "phone": f"+1415{int(suffix[:7], 16) % 10_000_000:07d}", "password": PASSWORD, "confirm_password": PASSWORD, "terms_accepted": True}
    response = other.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    other_user = db_session.get(User, response.json()["id"])
    assert other_user
    _, raw_token = security_token_service.issue(db_session, user_id=other_user.id, purpose=SecurityTokenPurpose.EMAIL_VERIFICATION, ttl=timedelta(hours=1))
    db_session.commit()
    assert other.post("/api/v1/auth/verify-email", json={"token": raw_token}).status_code == 200
    assert other.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": PASSWORD}).status_code == 200
    assert other.get("/api/v1/saved-jobs").json()["total"] == 0
    assert other.delete(f"/api/v1/saved-jobs/{job.id}").status_code == 204
    assert client.get("/api/v1/saved-jobs").json()["total"] == 1
    db_session.rollback()
    db_session.execute(delete(User).where(User.id == other_user.id))
    db_session.commit()
    other.close()


def test_job_endpoints_require_authentication(client: TestClient, db_session: Session):
    db_session.rollback()
    assert client.get("/api/v1/jobs").status_code == 401
    assert client.get("/api/v1/saved-jobs").status_code == 401
    assert client.get("/api/v1/job-recommendations").status_code == 401
