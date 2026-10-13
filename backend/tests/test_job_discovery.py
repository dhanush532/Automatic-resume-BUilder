from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.models.jobs import Job, JobSkill, JobSource, JobVerificationEvent
from app.services.arbeitnow import API_URL, ArbeitnowAdapter, configured_registry, plain_text
from app.services.job_sources import (
    JobSyncService,
    identity_key,
    normalize_company_name,
    parse_decimal,
    validate_url,
)
from tests.test_jobs import AuthorizedFeedAdapter, _raw_job, _sync_jobs, job_user  # noqa: F401


def raw_feed(**changes):
    return {"slug": "example-100", "company_name": "Example Test Employer", "title": "Software Engineer",
            "description": "<p>Build reliable services.</p>", "location": "Berlin", "remote": True,
            "job_types": ["full-time"], "tags": ["Marketing"], "created_at": 1791849600,
            "url": "https://www.arbeitnow.com/jobs/example-100", **changes}


def adapter_for(payload, *, status=200):
    def handler(request):
        assert request.url.host == "www.arbeitnow.com"
        assert request.method == "GET"
        assert "cookie" not in request.headers and "authorization" not in request.headers
        return httpx.Response(status, json=payload)
    return ArbeitnowAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_real_adapter_normalization_and_html_safety():
    adapter = adapter_for({"data": [raw_feed()], "links": {"next": None}})
    normalized = adapter.normalize(adapter.fetch_jobs()[0])
    assert adapter.snapshot_complete
    assert normalized.verification.verification_status == "LIKELY_LEGITIMATE"
    assert normalized.salary_min is None and normalized.skills == ()
    assert normalized.remote_type == "remote"
    assert normalized.employment_type == "full_time"
    assert normalized.description == "Build reliable services."
    assert plain_text("&lt;p&gt;Hello&lt;/p&gt;<script>bad()</script>") == "Hello"
    assert adapter.normalize(raw_feed(remote=False)).remote_type == "unknown"


def test_adapter_pagination_is_bounded_and_not_a_complete_snapshot():
    requests = []
    def handler(request):
        page = int(request.url.params["page"])
        requests.append(page)
        return httpx.Response(200, json={"data": [raw_feed(slug=f"job-{page}")], "links": {"next": f"{API_URL}?page={page + 1}"}})
    adapter = ArbeitnowAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(adapter.fetch_jobs()) == 3
    assert requests == [1, 2, 3] and not adapter.snapshot_complete


@pytest.mark.parametrize("next_url", ["http://127.0.0.1/admin", "https://evil.example/jobs?page=2", f"{API_URL}?page=1", f"{API_URL}?page=2&secret=x"])
def test_adapter_rejects_untrusted_pagination(next_url):
    with pytest.raises(ValueError):
        adapter_for({"data": [], "links": {"next": next_url}}).fetch_jobs()


@pytest.mark.parametrize("status", [301, 403, 429, 500])
def test_adapter_fails_on_provider_errors_without_retry(status):
    with pytest.raises(httpx.HTTPStatusError):
        adapter_for({}, status=status).fetch_jobs()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://localhost/test", "http://127.0.0.1/x", "https://user:password@example.com/x", "https://example.com\\@evil.example/x"])
def test_unsafe_application_destinations_are_rejected(url):
    with pytest.raises(ValueError):
        validate_url(url, field="application_url")


def test_suspicious_payment_request_is_not_active():
    result = ArbeitnowAdapter().normalize(raw_feed(description="Please pay the recruitment fee to apply."))
    assert result.verification.verification_status == "SUSPICIOUS"
    assert result.verification.status == "UNVERIFIED"


@pytest.mark.parametrize("host", ["www.arbeitnow.com", "www.arbeitnow.co.uk", "www.arbeitnow.fr", "www.arbeitnow.ch"])
def test_provider_country_destinations_are_explicitly_supported(host):
    assert ArbeitnowAdapter().normalize(raw_feed(url=f"https://{host}/jobs/example-100")).application_url == f"https://{host}/jobs/example-100"


def test_lookalike_provider_destination_is_rejected():
    with pytest.raises(ValueError):
        ArbeitnowAdapter().normalize(raw_feed(url="https://www.arbeitnow.com.evil.example/jobs/100"))


def test_identity_preserves_case_query_and_unicode():
    adapter = AuthorizedFeedAdapter([])
    one = adapter.normalize(_raw_job(external_job_id="Req-A"))
    two = adapter.normalize(_raw_job(external_job_id="req-a"))
    assert identity_key(adapter.source_key, one) != identity_key(adapter.source_key, two)
    one = replace(one, external_job_id=None, canonical_url="https://example.com/Jobs?id=A&B=1")
    two = replace(one, canonical_url="https://example.com/jobs?id=a&b=1")
    assert identity_key(adapter.source_key, one) != identity_key(adapter.source_key, two)
    assert normalize_company_name("株式会社東京") == "株式会社東京"
    assert parse_decimal("NaN") is None and parse_decimal("Infinity") is None


def test_idempotency_preserves_legacy_job_id_and_deduplicates_skills(db_session):
    raw = _raw_job()
    raw["skills"] = ["Python", "python", {"name": "Python", "required": False}]
    job = _sync_jobs(db_session, [raw])
    original_id = job.id
    job.identity_key = "test-authorized-feed:external:req-100"
    db_session.commit()
    JobSyncService().sync(db_session, AuthorizedFeedAdapter([raw]))
    assert db_session.get(Job, original_id).identity_key.startswith("test-authorized-feed:v2:")
    assert db_session.scalar(select(func.count(JobSkill.id)).where(JobSkill.job_id == original_id)) == 1
    assert db_session.scalar(select(func.count(JobVerificationEvent.id)).where(JobVerificationEvent.job_id == original_id)) == 2


def test_failed_batch_retains_previous_jobs_and_records_error(db_session):
    job = _sync_jobs(db_session, [_raw_job()])
    with pytest.raises(ValueError):
        JobSyncService().sync(db_session, AuthorizedFeedAdapter([_raw_job(title="Changed"), {"title": "invalid"}]), complete_snapshot=True)
    db_session.refresh(job)
    assert job.title == "Platform Engineer" and job.status == "ACTIVE"
    source = db_session.get(JobSource, job.source_id)
    assert source.last_error == "ValueError: sync failed; prior jobs retained."
    assert source.sync_lease is None


def test_partial_snapshot_does_not_unverify_missing_jobs(db_session):
    job = _sync_jobs(db_session, [_raw_job()])
    adapter = AuthorizedFeedAdapter([])
    adapter.snapshot_complete = False
    JobSyncService().sync(db_session, adapter, complete_snapshot=True)
    db_session.refresh(job)
    assert job.status == "ACTIVE"


def test_cooldown_disabled_sources_and_active_lease_do_not_fetch(db_session):
    adapter = AuthorizedFeedAdapter([_raw_job()])
    JobSyncService().sync(db_session, adapter)
    source = db_session.scalar(select(JobSource).where(JobSource.source_key == adapter.source_key))
    adapter.minimum_interval_seconds = 3600
    adapter.fetch_jobs = lambda **kwargs: pytest.fail("Must not fetch blocked source")
    with pytest.raises(ValueError, match="cooldown"):
        JobSyncService().sync(db_session, adapter)
    source = db_session.get(JobSource, source.id)
    source.sync_locked_until = datetime.now(UTC) + timedelta(minutes=5)
    db_session.commit()
    with pytest.raises(ValueError, match="already in progress"):
        JobSyncService().sync(db_session, adapter)
    source = db_session.get(JobSource, source.id)
    source.is_enabled = False
    db_session.commit()
    with pytest.raises(ValueError, match="disabled"):
        JobSyncService().sync(db_session, adapter)


@pytest.mark.usefixtures("job_user")
def test_freshness_expiry_and_suspicious_exclusion(client, db_session):
    job = _sync_jobs(db_session, [_raw_job()])
    job.last_seen_at = datetime.now(UTC) - timedelta(days=10)
    db_session.commit()
    params = {"company": "Acme Systems"}
    assert client.get("/api/v1/jobs", params=params).json()["total"] == 0
    detail = client.get(f"/api/v1/jobs/{job.id}").json()
    assert detail["status"] == "UNVERIFIED" and not detail["application_link_allowed"]
    assert client.get("/api/v1/jobs", params={**params, "include_unverified": True}).json()["total"] == 1
    job.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert client.get(f"/api/v1/jobs/{job.id}").json()["status"] == "EXPIRED"
    job.deadline_at = None
    job.last_seen_at = datetime.now(UTC)
    job.verification_status = "SUSPICIOUS"
    db_session.commit()
    assert client.get("/api/v1/jobs", params=params).json()["total"] == 0
    assert not client.get(f"/api/v1/jobs/{job.id}").json()["application_link_allowed"]
    assert str(job.id) not in {item["job"]["id"] for item in client.get("/api/v1/job-recommendations").json()["items"]}


@pytest.mark.usefixtures("job_user")
def test_source_health_distinguishes_adapter_configuration(client, db_session):
    _sync_jobs(db_session, [_raw_job()])
    source = next(item for item in client.get("/api/v1/jobs/sources").json() if item["source_key"] == "test-authorized-feed")
    assert not source["configured"] and source["last_success_at"] and source["last_job_count"] == 1


@pytest.mark.usefixtures("job_user")
def test_same_origin_guard_applies_to_passport_and_resumes(client):
    headers = {"Origin": "https://evil.example"}
    assert client.put("/api/v1/passport/profile", json={"full_name": "attacker"}, headers=headers).status_code == 403
    assert client.post("/api/v1/resumes", json={}, headers=headers).status_code == 403


def test_source_settings_fail_closed(monkeypatch):
    assert Settings(_env_file=None, job_source_config="").job_source_config == ""
    with pytest.raises(ValueError):
        Settings(_env_file=None, job_source_config="https://evil.example")
    monkeypatch.setenv("JOB_SOURCE_CONFIG", "arbeitnow")
    get_settings.cache_clear()
    try:
        assert configured_registry().get("arbeitnow") is not None
    finally:
        get_settings.cache_clear()
