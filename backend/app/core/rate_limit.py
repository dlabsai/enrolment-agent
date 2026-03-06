from asyncio import Lock
from dataclasses import dataclass
from time import monotonic


@dataclass
class RateLimitBucket:
    count: int
    reset_at: float


class RateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._buckets: dict[str, RateLimitBucket] = {}
        self._lock = Lock()

    async def hit(self, key: str) -> tuple[bool, int]:
        now = monotonic()
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now >= bucket.reset_at:
                self._buckets[key] = RateLimitBucket(count=1, reset_at=now + self._window_seconds)
                return True, self._window_seconds

            if bucket.count >= self._max_attempts:
                retry_after = max(1, int(bucket.reset_at - now))
                return False, retry_after

            bucket.count += 1
            retry_after = max(1, int(bucket.reset_at - now))
            return True, retry_after
