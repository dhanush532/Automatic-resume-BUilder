from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None
    user_agent: str | None
    device_type: str | None
    browser: str | None
    operating_system: str | None


def get_request_context(request: Request) -> RequestContext:
    user_agent = request.headers.get("user-agent")
    agent = (user_agent or "").lower()
    device_type = "mobile" if any(value in agent for value in ("mobile", "android", "iphone")) else "desktop"
    browser = next(
        (name for marker, name in (("edg/", "Edge"), ("firefox/", "Firefox"), ("chrome/", "Chrome"), ("safari/", "Safari")) if marker in agent),
        "Unknown",
    )
    operating_system = next(
        (name for marker, name in (("windows", "Windows"), ("mac os", "macOS"), ("android", "Android"), ("iphone", "iOS"), ("linux", "Linux")) if marker in agent),
        "Unknown",
    )
    return RequestContext(
        ip_address=request.client.host if request.client else None,
        user_agent=user_agent[:1024] if user_agent else None,
        device_type=device_type,
        browser=browser,
        operating_system=operating_system,
    )
