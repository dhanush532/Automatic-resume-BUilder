from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CareerPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "career_preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    desired_job_titles: Mapped[list[str]] = mapped_column(ARRAY(String(120)), default=list, nullable=False)
    industries: Mapped[list[str]] = mapped_column(ARRAY(String(120)), default=list, nullable=False)
    preferred_locations: Mapped[list[str]] = mapped_column(ARRAY(String(120)), default=list, nullable=False)
    work_arrangements: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list, nullable=False)
    employment_types: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list, nullable=False)
    expected_salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    expected_salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    willing_to_relocate: Mapped[bool | None] = mapped_column(Boolean)
    preferred_company_sizes: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list, nullable=False)
    company_preferences: Mapped[str | None] = mapped_column(Text)
    exclusions: Mapped[list[str]] = mapped_column(ARRAY(String(160)), default=list, nullable=False)
    __table_args__ = (CheckConstraint("expected_salary_min IS NULL OR expected_salary_max IS NULL OR expected_salary_min <= expected_salary_max", name="ck_career_preferences_salary_range"),)


class ProfessionalLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "professional_links"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "label", name="uq_professional_links_user_label"),)


class Education(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "education"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    institution: Mapped[str] = mapped_column(String(180), nullable=False)
    degree: Mapped[str] = mapped_column(String(160), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(160))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grade: Mapped[str | None] = mapped_column(String(40))
    coursework: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_education_dates"),)


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skills"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)


class UserSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_skills"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    proficiency: Mapped[str] = mapped_column(String(20), nullable=False)
    experience_months: Mapped[int | None] = mapped_column(nullable=True)
    last_used: Mapped[date | None] = mapped_column(Date)
    skill: Mapped[Skill] = relationship()
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_skills_user_skill"), CheckConstraint("experience_months IS NULL OR experience_months >= 0", name="ck_user_skills_experience"))


class Experience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[str | None] = mapped_column(Text)
    technology_notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_experiences_dates"),)


class ExperienceSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experience_skills"
    experience_id: Mapped[UUID] = mapped_column(ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    skill: Mapped[Skill] = relationship()
    __table_args__ = (UniqueConstraint("experience_id", "skill_id", name="uq_experience_skills_experience_skill"),)


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    problem_solved: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(String(160))
    technology_notes: Mapped[str | None] = mapped_column(Text)
    features: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(String(2048))
    live_url: Mapped[str | None] = mapped_column(String(2048))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    team_or_individual: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    results: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_projects_dates"), CheckConstraint("team_or_individual IN ('team', 'individual')", name="ck_projects_team_type"))


class ProjectSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_skills"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    skill: Mapped[Skill] = relationship()
    __table_args__ = (UniqueConstraint("project_id", "skill_id", name="uq_project_skills_project_skill"),)


class Certification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "certifications"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    issuer: Mapped[str] = mapped_column(String(180), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    credential_id: Mapped[str | None] = mapped_column(String(160))
    credential_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date", name="ck_certifications_dates"),)


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    provider: Mapped[str] = mapped_column(String(180), nullable=False)
    completion_date: Mapped[date | None] = mapped_column(Date)
    credential_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)


class Achievement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "achievements"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(180))
    achieved_on: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(2048))


class Language(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "languages"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(80), nullable=False)
    proficiency: Mapped[str] = mapped_column(String(20), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "language", name="uq_languages_user_language"),)


class OpenSourceContribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "open_source_contributions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    contribution: Mapped[str] = mapped_column(String(180), nullable=False)
    technology_notes: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_open_source_dates"), UniqueConstraint("user_id", "repository", "contribution", name="uq_open_source_user_repo_contribution"))
