from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AIProvider(Protocol):
    def analyze_job_requirements(self, job_description: str) -> dict[str, Any]: ...

    def customize_resume(self, *, job_description: str, resume_snapshot: dict[str, Any]) -> dict[str, Any]: ...


class AIProviderUnavailable(RuntimeError):
    """Raised when no configured AI provider is available."""


@dataclass(frozen=True)
class UnavailableAIProvider:
    reason: str = "No AI provider is configured for this environment."

    def analyze_job_requirements(self, job_description: str) -> dict[str, Any]:
        raise AIProviderUnavailable(self.reason)

    def customize_resume(self, *, job_description: str, resume_snapshot: dict[str, Any]) -> dict[str, Any]:
        raise AIProviderUnavailable(self.reason)


def get_ai_provider() -> AIProvider:
    """Provider boundary for future configured AI integrations.

    Base Resume System behavior is deterministic and does not require external credentials.
    """

    return UnavailableAIProvider()
