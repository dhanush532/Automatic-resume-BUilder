from __future__ import annotations

import hashlib
import ipaddress
import re
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.jobs import Company, Job, JobSkill, JobSource, JobVerificationEvent

JOB_STATUSES = {"ACTIVE", "CLOSED", "EXPIRED", "UNVERIFIED"}
VERIFICATION_STATUSES = {"VERIFIED", "LIKELY_LEGITIMATE", "UNVERIFIED", "SUSPICIOUS", "EXPIRED", "CLOSED"}
REMOTE_TYPES = {"remote", "hybrid", "onsite", "unknown"}
EMPLOYMENT_TYPES = {"full_time", "part_time", "contract", "internship", "temporary", "freelance", "volunteer", "unknown"}
SALARY_PERIODS = {"hour", "day", "week", "month", "year"}


class SyncBlockedError(ValueError):
    """Safe operator-facing errors which did not initiate a provider request."""


@dataclass(frozen=True)
class CompanyData:
    name: str
    normalized_name: str
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    headquarters: str | None = None


@dataclass(frozen=True)
class JobSkillData:
    name: str
    normalized_name: str
    is_required: bool = True
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobVerification:
    status: str = "UNVERIFIED"
    verified_at: datetime | None = None
    reason: str | None = None
    verification_status: str = "UNVERIFIED"


@dataclass(frozen=True)
class NormalizedJob:
    company: CompanyData
    title: str
    description: str
    external_job_id: str | None
    location: str | None
    normalized_location: str | None
    remote_type: str
    employment_type: str
    experience_requirements: str | None
    education_requirements: str | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    salary_currency: str | None
    salary_period: str | None
    application_url: str
    canonical_url: str | None
    source_url: str
    posted_at: datetime | None
    deadline_at: datetime | None
    source_metadata: dict[str, Any]
    skills: tuple[JobSkillData, ...]
    verification: JobVerification


class JobSourceAdapter(ABC):
    """Provider-neutral boundary for authorized job APIs and feeds.

    Production adapters must use an official/licensed API or an authorized
    feed. This boundary deliberately has no browser scraping implementation.
    """

    source_key: str
    source_name: str
    source_type: str = "api"
    configuration: Mapping[str, Any] = {}
    minimum_interval_seconds: int = 0
    failure_retry_seconds: int = 300
    snapshot_complete: bool = True

    @abstractmethod
    def fetch_jobs(self, *, cursor: str | None = None) -> Iterable[Mapping[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def identify_external_job_id(self, raw: Mapping[str, Any]) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def canonical_application_url(self, raw: Mapping[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def source_metadata(self, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def verify(self, raw: Mapping[str, Any]) -> JobVerification:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedJob:
        raise NotImplementedError


class JobSourceRegistry:
    """Registry boundary; no live source is registered until configured."""

    def __init__(self, adapters: Iterable[JobSourceAdapter] = ()) -> None:
        self._adapters = {adapter.source_key: adapter for adapter in adapters}

    def get(self, source_key: str) -> JobSourceAdapter | None:
        return self._adapters.get(source_key)

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def normalize_token(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w+#./-]+", " ", value).replace("_", " ")).strip()


def normalize_company_name(value: str) -> str:
    return re.sub(r" (?:inc\.|incorporated)$", "", normalize_token(value)).strip()


def normalize_location(value: str | None) -> str | None:
    normalized = normalize_token(value)
    return normalized or None


def normalize_remote_type(value: str | None) -> str:
    normalized = normalize_token(value)
    if normalized in {"remote", "fully remote", "work from home", "wfh"}:
        return "remote"
    if normalized in {"hybrid", "hybrid remote"}:
        return "hybrid"
    if normalized in {"onsite", "on-site", "on site", "office"}:
        return "onsite"
    return "unknown"


def normalize_employment_type(value: str | None) -> str:
    normalized = normalize_token(value).replace("-", "_").replace(" ", "_")
    aliases = {
        "fulltime": "full_time",
        "full_time": "full_time",
        "parttime": "part_time",
        "part_time": "part_time",
        "intern": "internship",
        "internship": "internship",
        "contractor": "contract",
        "contract": "contract",
        "temporary": "temporary",
        "temp": "temporary",
        "freelance": "freelance",
        "volunteer": "volunteer",
    }
    return aliases.get(normalized, normalized if normalized in EMPLOYMENT_TYPES else "unknown")


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value).replace(",", "").replace("$", "").strip())
        return amount if amount.is_finite() and 0 <= amount < Decimal("10000000000") else None
    except (InvalidOperation, ValueError):
        return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_salary(value: Any) -> tuple[Decimal | None, Decimal | None, str | None, str | None]:
    if not isinstance(value, Mapping):
        return None, None, None, None
    minimum = parse_decimal(value.get("min", value.get("minimum")))
    maximum = parse_decimal(value.get("max", value.get("maximum")))
    currency = str(value.get("currency")).upper()[:3] if value.get("currency") else None
    period = normalize_token(str(value.get("period"))) if value.get("period") else None
    return minimum, maximum, currency, period if period in SALARY_PERIODS else None


def validate_url(value: str, *, field: str) -> str:
    parsed = urlparse(value)
    if (len(value) > 2048 or re.search(r"[\x00-\x20\\]", value) or parsed.scheme not in {"http", "https"}
            or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 80, 443}):
        raise ValueError(f"{field} must be a safe absolute HTTP(S) URL.")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
        raise ValueError(f"{field} must not target a local host.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError(f"{field} must not target a private address.")
    return value


def normalized_job_from_mapping(
    raw: Mapping[str, Any],
    *,
    adapter: JobSourceAdapter,
) -> NormalizedJob:
    company_name = str(raw.get("company", raw.get("company_name", ""))).strip()
    title = str(raw.get("title", "")).strip()
    description = str(raw.get("description", "")).strip()
    if not company_name or not title or not description:
        raise ValueError("A job must include a company, title, and description.")
    if len(company_name) > 180 or len(title) > 240 or len(description) > 100_000:
        raise ValueError("Job text exceeds supported limits.")
    application_url = validate_url(adapter.canonical_application_url(raw), field="application_url")
    source_url = validate_url(str(raw.get("source_url", application_url)), field="source_url")
    canonical_value = raw.get("canonical_url")
    canonical_url = validate_url(str(canonical_value), field="canonical_url") if canonical_value else application_url
    minimum, maximum, currency, period = parse_salary(raw.get("salary"))
    if minimum is not None and maximum is not None and minimum > maximum:
        minimum, maximum = maximum, minimum
    raw_skills = raw.get("skills", ())
    if not isinstance(raw_skills, (list, tuple)):
        raise ValueError("Job skills must be a list.")
    skills = tuple(
        JobSkillData(
            name=str(item.get("name", "")).strip() if isinstance(item, Mapping) else str(item).strip(),
            normalized_name=normalize_token(item.get("name") if isinstance(item, Mapping) else str(item)),
            is_required=bool(item.get("required", True)) if isinstance(item, Mapping) else True,
            source_metadata=dict(item.get("metadata", {})) if isinstance(item, Mapping) and isinstance(item.get("metadata", {}), Mapping) else {},
        )
        for item in raw_skills
        if (str(item.get("name", "")).strip() if isinstance(item, Mapping) else str(item).strip())
    )
    deduplicated_skills: dict[str, JobSkillData] = {}
    for skill in skills:
        if not skill.normalized_name or len(skill.name) > 120:
            continue
        previous = deduplicated_skills.get(skill.normalized_name)
        if previous is None or skill.is_required:
            deduplicated_skills[skill.normalized_name] = skill
    external_id = adapter.identify_external_job_id(raw)
    if external_id and len(external_id) > 255:
        raise ValueError("External job identifier exceeds supported length.")
    return NormalizedJob(
        company=CompanyData(
            name=company_name,
            normalized_name=normalize_company_name(company_name),
            website=str(raw["company_website"]) if raw.get("company_website") else None,
            logo_url=str(raw["company_logo_url"]) if raw.get("company_logo_url") else None,
            description=str(raw["company_description"]) if raw.get("company_description") else None,
            headquarters=str(raw["company_headquarters"]) if raw.get("company_headquarters") else None,
        ),
        title=title,
        description=description,
        external_job_id=external_id,
        location=str(raw["location"]).strip() if raw.get("location") else None,
        normalized_location=normalize_location(str(raw["location"])) if raw.get("location") else None,
        remote_type=normalize_remote_type(str(raw.get("remote_type", ""))),
        employment_type=normalize_employment_type(str(raw.get("employment_type", ""))),
        experience_requirements=str(raw["experience_requirements"]).strip() if raw.get("experience_requirements") else None,
        education_requirements=str(raw["education_requirements"]).strip() if raw.get("education_requirements") else None,
        salary_min=minimum,
        salary_max=maximum,
        salary_currency=currency,
        salary_period=period,
        application_url=application_url,
        canonical_url=canonical_url,
        source_url=source_url,
        posted_at=parse_datetime(raw.get("posted_at")),
        deadline_at=parse_datetime(raw.get("deadline_at")),
        source_metadata=dict(adapter.source_metadata(raw)),
        skills=tuple(deduplicated_skills.values()),
        verification=adapter.verify(raw),
    )


def identity_key(source_key: str, job: NormalizedJob) -> str:
    if job.external_job_id:
        identity = "external:" + job.external_job_id
        return f"{source_key}:v2:{hashlib.sha256(identity.encode()).hexdigest()}"
    if job.canonical_url:
        identity = "url:" + job.canonical_url.split("#", 1)[0]
        return f"{source_key}:v2:{hashlib.sha256(identity.encode()).hexdigest()}"
    return ":".join(
        (
            source_key,
            "fallback",
            job.company.normalized_name,
            normalize_token(job.title),
            job.normalized_location or "unknown",
            job.posted_at.isoformat() if job.posted_at else "unknown",
        )
    )


def upsert_company(db: Session, company_data: CompanyData) -> Company:
    # The unique normalized name remains a grouping aid, never identity-verification evidence.
    db.execute(insert(Company).values(**company_data.__dict__).on_conflict_do_nothing(index_elements=[Company.normalized_name]))
    company = db.scalar(select(Company).where(Company.normalized_name == company_data.normalized_name))
    if not company:
        company = Company(**company_data.__dict__)
        db.add(company)
        db.flush()
        return company
    for attribute in ("website", "logo_url", "description", "headquarters"):
        value = getattr(company_data, attribute)
        if value:
            setattr(company, attribute, value)
    return company


def upsert_job(db: Session, *, source: JobSource, normalized: NormalizedJob) -> Job:
    key = identity_key(source.source_key, normalized)
    # Resolve original IDs first, preserving pre-M6 rows and saved-job references.
    if normalized.external_job_id:
        job = db.scalar(select(Job).where(Job.source_id == source.id, Job.external_job_id == normalized.external_job_id))
    else:
        job = db.scalar(select(Job).where(Job.source_id == source.id, Job.canonical_url == normalized.canonical_url))
    if job is None:
        job = db.scalar(select(Job).where(Job.identity_key == key))
    now = datetime.now(UTC)
    source_metadata = dict(normalized.source_metadata)
    if normalized.verification.reason:
        source_metadata.setdefault("verification_reason", normalized.verification.reason)
    values = {
        "company_id": upsert_company(db, normalized.company).id,
        "source_id": source.id,
        "identity_key": key,
        "external_job_id": normalized.external_job_id,
        "title": normalized.title,
        "description": normalized.description,
        "location": normalized.location,
        "normalized_location": normalized.normalized_location,
        "remote_type": normalized.remote_type if normalized.remote_type in REMOTE_TYPES else "unknown",
        "employment_type": normalized.employment_type if normalized.employment_type in EMPLOYMENT_TYPES else "unknown",
        "experience_requirements": normalized.experience_requirements,
        "education_requirements": normalized.education_requirements,
        "salary_min": normalized.salary_min,
        "salary_max": normalized.salary_max,
        "salary_currency": normalized.salary_currency,
        "salary_period": normalized.salary_period,
        "application_url": normalized.application_url,
        "canonical_url": normalized.canonical_url,
        "source_url": normalized.source_url,
        "posted_at": normalized.posted_at,
        "deadline_at": normalized.deadline_at,
        "last_seen_at": now,
        "last_verified_at": normalized.verification.verified_at,
        "status": normalized.verification.status if normalized.verification.status in JOB_STATUSES else "UNVERIFIED",
        "verification_status": normalized.verification.verification_status,
        "source_metadata": source_metadata,
    }
    if job:
        for field, value in values.items():
            setattr(job, field, value)
    else:
        job = Job(first_seen_at=now, **values)
        db.add(job)
        db.flush()
    db.query(JobSkill).filter(JobSkill.job_id == job.id).delete(synchronize_session=False)
    for skill in normalized.skills:
        db.add(JobSkill(job_id=job.id, name=skill.name, normalized_name=skill.normalized_name, is_required=skill.is_required, source_metadata=skill.source_metadata))
    db.add(JobVerificationEvent(job_id=job.id, checked_at=now, verification_status=job.verification_status,
                                reason=normalized.verification.reason or "Source supplied no independent employer verification.",
                                evidence_url=normalized.source_url))
    db.flush()
    db.expire(job, ["skills"])
    return job


class JobSyncService:
    def sync(self, db: Session, adapter: JobSourceAdapter, *, cursor: str | None = None, complete_snapshot: bool = False) -> int:
        now = datetime.now(UTC)
        lease = uuid4()
        db.execute(insert(JobSource).values(source_key=adapter.source_key, name=adapter.source_name,
                   source_type=adapter.source_type, is_enabled=True, configuration=dict(adapter.configuration))
                   .on_conflict_do_nothing(index_elements=[JobSource.source_key]))
        source = db.scalar(select(JobSource).where(JobSource.source_key == adapter.source_key).with_for_update())
        assert source is not None
        if not source.is_enabled:
            db.rollback()
            raise SyncBlockedError("Job source is disabled.")
        if source.sync_locked_until and source.sync_locked_until > now:
            db.rollback()
            raise SyncBlockedError("A sync is already in progress; wait for its lease to expire if interrupted.")
        interval = min(adapter.minimum_interval_seconds, adapter.failure_retry_seconds) if source.last_error else adapter.minimum_interval_seconds
        if source.last_attempt_at and source.last_attempt_at + timedelta(seconds=interval) > now:
            retry_at = source.last_attempt_at + timedelta(seconds=interval)
            db.rollback()
            raise SyncBlockedError(f"Source cooldown is active; retry after {retry_at.isoformat()}.")
        source.last_attempt_at, source.sync_lease = now, lease
        source.sync_locked_until = now + timedelta(minutes=10)
        source_id = source.id
        db.commit()
        try:
            # Fetch and validate the ENTIRE bounded batch before any job writes. No DB locks during HTTP.
            batch: dict[str, NormalizedJob] = {}
            for raw in adapter.fetch_jobs(cursor=cursor):
                normalized = adapter.normalize(raw)
                if normalized.verification.status not in JOB_STATUSES or normalized.verification.verification_status not in VERIFICATION_STATUSES:
                    raise ValueError("Source returned an unsupported verification status.")
                batch[identity_key(adapter.source_key, normalized)] = normalized
                if len(batch) > 5000:
                    raise ValueError("Sync batch exceeds the supported bound.")
            source = db.scalar(select(JobSource).where(JobSource.id == source_id).with_for_update().execution_options(populate_existing=True))
            if source is None or source.sync_lease != lease or not source.is_enabled:
                raise ValueError("Sync lease was replaced or source disabled; batch not applied.")
            seen = {upsert_job(db, source=source, normalized=job).identity_key for job in batch.values()}
            if complete_snapshot and adapter.snapshot_complete and cursor is None:
                for job in db.scalars(select(Job).where(Job.source_id == source.id, Job.status == "ACTIVE")):
                    if job.identity_key not in seen:
                        job.status = job.verification_status = "UNVERIFIED"
                        reason = "Not seen in a complete source snapshot; closure is not confirmed."
                        job.source_metadata = {**job.source_metadata, "verification_reason": reason}
                        db.add(JobVerificationEvent(job_id=job.id, verification_status="UNVERIFIED", reason=reason, evidence_url=job.source_url))
            source.last_success_at = datetime.now(UTC)
            source.last_error = None
            source.last_job_count = len(seen)
            source.sync_lease = source.sync_locked_until = None
            db.commit()
            return len(seen)
        except Exception as error:
            db.rollback()
            source = db.scalar(select(JobSource).where(JobSource.id == source_id).with_for_update().execution_options(populate_existing=True))
            if source and source.sync_lease == lease:
                # Do not persist exception strings which may include URLs, SQL values or credentials.
                source.last_error = f"{type(error).__name__}: sync failed; prior jobs retained."
                source.sync_lease = source.sync_locked_until = None
                db.commit()
            else:
                db.rollback()
            raise
