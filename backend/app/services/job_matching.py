from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.jobs import Job, JobSkill
from app.models.passport import CareerPreference, Education, Experience, Skill, UserSkill
from app.models.user import Profile
from app.services.job_sources import normalize_token

SKILL_NORMALIZATION_RULE = "Exact normalized names plus the explicit aliases listed in the matcher; no semantic similarity is inferred."
SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "nodejs": "node.js",
    "node js": "node.js",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "py": "python",
}


@dataclass(frozen=True)
class SkillGap:
    matched: list[str]
    missing: list[str]
    uncertain: list[str]


@dataclass(frozen=True)
class JobMatch:
    score: int
    matching_skills: list[str]
    missing_skills: list[str]
    uncertain_skills: list[str]
    reasons: list[str]
    conflicts: list[str]


def canonical_skill(value: str) -> str:
    normalized = normalize_token(value)
    return SKILL_ALIASES.get(normalized, normalized)


def _passport_data(db: Session, user_id: UUID) -> tuple[set[str], list[str], list[str], CareerPreference | None, Profile | None]:
    skills = {
        canonical_skill(skill.name)
        for skill in db.scalars(select(Skill).join(UserSkill, UserSkill.skill_id == Skill.id).where(UserSkill.user_id == user_id))
    }
    experience = list(db.scalars(select(Experience).where(Experience.user_id == user_id)))
    education = list(db.scalars(select(Education).where(Education.user_id == user_id)))
    preference = db.scalar(select(CareerPreference).where(CareerPreference.user_id == user_id))
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    experience_text = [" ".join(part for part in (item.title, item.company, item.description or "", item.technology_notes or "") if part) for item in experience]
    education_text = [" ".join(part for part in (item.degree, item.field_of_study or "", item.institution) if part) for item in education]
    return skills, experience_text, education_text, preference, profile


def skill_gaps(db: Session, *, user_id: UUID, job: Job) -> SkillGap:
    user_skills, _, _, _, _ = _passport_data(db, user_id)
    job_skills = list(db.scalars(select(JobSkill).where(JobSkill.job_id == job.id).order_by(JobSkill.name)))
    matched: list[str] = []
    missing: list[str] = []
    uncertain: list[str] = []
    for skill in job_skills:
        normalized = canonical_skill(skill.name)
        if normalized in user_skills:
            matched.append(skill.name)
        elif "/" in skill.name or " or " in skill.name.casefold():
            uncertain.append(skill.name)
        else:
            missing.append(skill.name)
    return SkillGap(matched=matched, missing=missing, uncertain=uncertain)


def _contains_token(values: Iterable[str], target: str) -> bool:
    target_tokens = {token for token in re.findall(r"[a-z0-9+#.]+", target.casefold()) if len(token) > 2}
    return bool(target_tokens) and any(target_tokens & set(re.findall(r"[a-z0-9+#.]+", value.casefold())) for value in values)


def match_job(db: Session, *, user_id: UUID, job: Job) -> JobMatch:
    user_skills, experience_text, education_text, preference, profile = _passport_data(db, user_id)
    gaps = skill_gaps(db, user_id=user_id, job=job)
    job_skill_count = len(gaps.matched) + len(gaps.missing) + len(gaps.uncertain)
    reasons: list[str] = []
    conflicts: list[str] = []
    weighted: list[tuple[float, float | None]] = []

    if job_skill_count:
        skill_ratio = len(gaps.matched) / job_skill_count
        weighted.append((50, skill_ratio))
        if gaps.matched:
            reasons.append(f"Matches Passport skills: {', '.join(gaps.matched)}.")
        if gaps.missing:
            conflicts.append(f"Missing stored evidence for: {', '.join(gaps.missing)}.")
        if gaps.uncertain:
            conflicts.append(f"Ambiguous source skill labels need review: {', '.join(gaps.uncertain)}.")

    desired_roles = preference.desired_job_titles if preference else []
    if desired_roles:
        role_match = any(_contains_token([job.title], role) for role in desired_roles)
        weighted.append((20, 1 if role_match else 0))
        if role_match:
            reasons.append("Matches one of your selected job titles.")
        else:
            conflicts.append("The title does not match your selected job-title preferences.")

    preferred_locations = preference.preferred_locations if preference else []
    if job.normalized_location and preferred_locations:
        location_match = any(normalize_token(location) in job.normalized_location or job.normalized_location in normalize_token(location) for location in preferred_locations)
        weighted.append((10, 1 if location_match else 0))
        if location_match:
            reasons.append("Matches a preferred location.")
        elif job.remote_type not in {"remote", "hybrid"} and not preference.willing_to_relocate:
            conflicts.append("Location does not match your stored preferences.")
    elif job.remote_type != "unknown" and preference and preference.work_arrangements:
        arrangement_match = job.remote_type in {normalize_token(item).replace("_", "") for item in preference.work_arrangements} or (job.remote_type == "onsite" and "on_site" in preference.work_arrangements)
        weighted.append((10, 1 if arrangement_match else 0))
        if arrangement_match:
            reasons.append("Remote/work arrangement matches your preferences.")
        else:
            conflicts.append("Remote/work arrangement conflicts with your preferences.")

    if preference and preference.employment_types and job.employment_type != "unknown":
        employment_match = job.employment_type in set(preference.employment_types)
        weighted.append((10, 1 if employment_match else 0))
        if employment_match:
            reasons.append("Employment type matches your preferences.")
        else:
            conflicts.append("Employment type conflicts with your preferences.")

    if preference and (preference.expected_salary_min is not None or preference.expected_salary_max is not None) and job.salary_max is not None:
        salary_match = (preference.expected_salary_min is None or job.salary_max >= preference.expected_salary_min) and (preference.expected_salary_max is None or job.salary_min is None or job.salary_min <= preference.expected_salary_max)
        weighted.append((10, 1 if salary_match else 0))
        if salary_match:
            reasons.append("Available salary information overlaps your stored range.")
        else:
            conflicts.append("Available salary information does not overlap your stored range.")

    if job.experience_requirements:
        experience_match = bool(experience_text) and _contains_token(experience_text, job.experience_requirements)
        weighted.append((10, 1 if experience_match else 0))
        if experience_match:
            reasons.append("Your Passport contains experience text related to the source requirement.")
        else:
            conflicts.append("The source experience requirement is not supported by a direct Passport text match.")

    if job.education_requirements:
        education_match = bool(education_text) and _contains_token(education_text, job.education_requirements)
        weighted.append((10, 1 if education_match else 0))
        if education_match:
            reasons.append("Your stored education includes text related to the source requirement.")
        else:
            conflicts.append("The source education requirement is not supported by a direct Passport text match.")

    available_weight = sum(weight for weight, value in weighted if value is not None)
    earned = sum(weight * value for weight, value in weighted if value is not None)
    score = round(earned / available_weight * 100) if available_weight else 0
    if profile and profile.headline:
        reasons.append("Uses your saved Career Passport profile as the matching source.")
    if not reasons:
        reasons.append("No matching evidence was found in the current Career Passport.")
    return JobMatch(
        score=score,
        matching_skills=gaps.matched,
        missing_skills=gaps.missing,
        uncertain_skills=gaps.uncertain,
        reasons=reasons,
        conflicts=conflicts,
    )
