from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

InterviewType = Literal["technical", "hr", "behavioral", "project", "resume", "mixed"]


class InterviewCreate(BaseModel):
    role: str = Field(min_length=2, max_length=160)
    job_description: str = Field(default="", max_length=12000)
    resume_id: UUID | None = None
    resume_text: str = Field(default="", max_length=60000)
    interview_type: InterviewType = "mixed"
    difficulty: int = Field(default=2, ge=1, le=5)
    duration_minutes: int = Field(default=15, ge=5, le=90)
    question_count: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_source(self):
        self.role = self.role.strip()
        if len(self.role) < 2:
            raise ValueError("Enter a job role.")
        if bool(self.resume_id) == bool(self.resume_text.strip()):
            raise ValueError("Choose a saved resume or supply extracted resume text, not both.")
        if not self.resume_id and len(self.resume_text.strip()) < 80:
            raise ValueError("Supply at least 80 characters of resume text.")
        return self


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=15, max_length=1600)
    category: InterviewType


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    accuracy: int = Field(ge=0, le=100)
    relevance: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    feedback: str = Field(min_length=15, max_length=2000)
    strengths: list[str] = Field(max_length=6)
    weaknesses: list[str] = Field(max_length=6)
    corrections: list[str] = Field(max_length=6)
    sample_answer: str = Field(min_length=15, max_length=4000)
    recommendations: list[str] = Field(min_length=1, max_length=6)
    follow_up: str = Field(default="", max_length=1600)


class AnswerInput(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1, max_length=12000)


class InterviewControl(BaseModel):
    action: Literal["pause", "resume", "end"]
