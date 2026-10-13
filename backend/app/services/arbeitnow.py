"""Read-only integration with Arbeitnow's documented public API.

Permission/attribution: https://www.arbeitnow.com/terms (section 11).
No candidate information, cookies, credentials, or application submissions are sent.
"""

import json
import re
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import get_settings
from app.services.job_sources import (
    JobSourceAdapter,
    JobSourceRegistry,
    JobVerification,
    NormalizedJob,
    normalized_job_from_mapping,
    validate_url,
)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
LISTING_HOSTS = {"www.arbeitnow.com", "www.arbeitnow.co.uk", "www.arbeitnow.fr", "www.arbeitnow.ch"}


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "br", "li", "div", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: str) -> str:
    parser = _PlainText()
    parser.feed(unescape(value))
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


class ArbeitnowAdapter(JobSourceAdapter):
    source_key = "arbeitnow"
    source_name = "Arbeitnow"
    source_type = "api"
    minimum_interval_seconds = 6 * 60 * 60
    snapshot_complete = False
    configuration = {"api_url": API_URL, "attribution_url": "https://www.arbeitnow.com", "policy_url": "https://www.arbeitnow.com/terms", "mode": "MANUAL_APPLICATION", "adapter_version": 1}

    def __init__(self, *, client: httpx.Client | None = None, max_pages: int = 3) -> None:
        if not 1 <= max_pages <= 3:
            raise ValueError("Fetch between one and three pages per sync.")
        self.client, self.max_pages = client, max_pages

    def fetch_jobs(self, *, cursor: str | None = None) -> list[Mapping[str, Any]]:
        if cursor is not None:
            raise ValueError("Arbeitnow sync starts at page one; arbitrary cursors are not allowed.")
        self.snapshot_complete = False
        client = self.client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)
        started = time.monotonic()
        jobs: list[Mapping[str, Any]] = []
        try:
            for page in range(1, self.max_pages + 1):
                with client.stream("GET", API_URL, params={"page": page}, headers={"Accept": "application/json", "User-Agent": "CareerPilot/0.1 (read-only job discovery)"}, follow_redirects=False) as response:
                    response.raise_for_status()
                    if "application/json" not in response.headers.get("content-type", ""):
                        raise ValueError("Source returned an unexpected content type.")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 5_000_000 or time.monotonic() - started > 90:
                            raise ValueError("Source response exceeded size or time limit.")
                payload = json.loads(content)
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list) or len(payload["data"]) > 1000:
                    raise ValueError("Unexpected source response schema.")
                if not all(isinstance(item, dict) for item in payload["data"]):
                    raise ValueError("Unexpected source job schema.")
                jobs.extend(payload["data"])
                links = payload.get("links")
                if not isinstance(links, dict) or "next" not in links:
                    raise ValueError("Source pagination metadata missing; completeness is unknown.")
                next_url = links["next"]
                if next_url is None:
                    self.snapshot_complete = True
                    break
                # Validate metadata, then construct our OWN fixed-host URL for the next request.
                parsed = urlparse(str(next_url))
                if (parsed.scheme != "https" or parsed.netloc != "www.arbeitnow.com" or parsed.path != "/api/job-board-api"
                        or parse_qs(parsed.query) != {"page": [str(page + 1)]} or parsed.fragment):
                    raise ValueError("Untrusted or non-sequential pagination link.")
            return jobs
        finally:
            if self.client is None:
                client.close()

    def identify_external_job_id(self, raw: Mapping[str, Any]) -> str:
        slug = raw.get("slug")
        if not isinstance(slug, str) or not re.fullmatch(r"[\w-]{1,255}", slug):
            raise ValueError("Missing or invalid source job slug.")
        return slug

    def canonical_application_url(self, raw: Mapping[str, Any]) -> str:
        url = validate_url(str(raw.get("url", "")), field="application_url")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc not in LISTING_HOSTS or not parsed.path.startswith("/jobs/"):
            raise ValueError("Application link is outside the authorized source.")
        return url

    def source_metadata(self, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"attribution_url": "https://www.arbeitnow.com", "verification_basis": "aggregator_listing", "adapter_version": 1}

    def verify(self, raw: Mapping[str, Any]) -> JobVerification:
        self.canonical_application_url(raw)
        description = plain_text(str(raw.get("description", "")))
        suspicious = re.search(r"(?:pay|send|transfer).{0,35}(?:application fee|recruitment fee|registration fee|bitcoin|crypto)|(?:application|recruitment|registration) fee.{0,25}(?:required|payable)", description, re.I)
        if suspicious:
            return JobVerification(status="UNVERIFIED", verified_at=datetime.now(UTC), verification_status="SUSPICIOUS",
                                   reason="Possible recruitment-payment request detected. Review manually; this heuristic can be wrong.")
        return JobVerification(status="ACTIVE", verified_at=datetime.now(UTC), verification_status="LIKELY_LEGITIMATE",
                               reason="Present in Arbeitnow's public API with a source-hosted destination and employer name. Employer identity and final destination are not independently verified; legitimacy is not guaranteed.")

    def normalize(self, raw: Mapping[str, Any]) -> NormalizedJob:
        # Unknown salary, qualifications, skills and work authorization stay unknown.
        # Source tags are categories, not evidence that a skill is required.
        created_at = raw.get("created_at")
        if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
            raise ValueError("Source posting timestamp missing or invalid.")
        posted = datetime.fromtimestamp(created_at, tz=UTC)
        types = raw.get("job_types", [])
        employment = types[0] if isinstance(types, list) and len(types) == 1 else "unknown"
        mapped = {**raw, "external_job_id": self.identify_external_job_id(raw), "company": raw.get("company_name"),
                  "description": plain_text(str(raw.get("description", ""))), "posted_at": posted,
                  "remote_type": "remote" if raw.get("remote") is True else "unknown",
                  "employment_type": employment, "skills": [], "salary": None}
        if not isinstance(mapped["company"], str) or not isinstance(raw.get("title"), str):
            raise ValueError("Missing employer or job title.")
        return normalized_job_from_mapping(mapped, adapter=self)


def configured_registry() -> JobSourceRegistry:
    return JobSourceRegistry([ArbeitnowAdapter()] if get_settings().job_source_config == "arbeitnow" else [])
