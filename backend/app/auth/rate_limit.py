from collections import defaultdict, deque
from time import monotonic


class InMemoryRateLimiter:
    """A development-safe limiter; production deployments should use a shared store."""

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = monotonic()
        attempts = self._attempts[key]
        cutoff = now - window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= limit:
            return False
        attempts.append(now)
        return True

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)


login_rate_limiter = InMemoryRateLimiter()
