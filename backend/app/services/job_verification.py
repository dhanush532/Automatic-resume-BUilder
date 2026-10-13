"""Availability and trust are separate; stale data never silently stays active."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, or_

from app.core.config import get_settings
from app.models.jobs import Job


def freshness_cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(hours=get_settings().job_freshness_hours)


def effective_status_expression():
    now = datetime.now(UTC)
    return case(
        (Job.status == "CLOSED", "CLOSED"),
        (or_(Job.status == "EXPIRED", Job.deadline_at <= now), "EXPIRED"),
        (Job.last_seen_at < freshness_cutoff(now), "UNVERIFIED"),
        else_=Job.status,
    )


def effective_verification(job: Job) -> tuple[str, str, str | None]:
    reason = (job.source_metadata or {}).get("verification_reason")
    now = datetime.now(UTC)
    if job.status == "CLOSED":
        return "CLOSED", "CLOSED", reason or "The source reports this listing closed."
    if job.status == "EXPIRED" or (job.deadline_at and job.deadline_at <= now):
        return "EXPIRED", "EXPIRED", "The listing or its application deadline has expired."
    if job.last_seen_at < freshness_cutoff(now):
        return "UNVERIFIED", "UNVERIFIED", "Listing has not been refreshed within the freshness window. Recheck the source."
    return job.status, job.verification_status, reason
