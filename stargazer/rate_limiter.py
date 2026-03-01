import time


class RateLimiter:
    """Simple rate limiter that enforces minimum delay between calls."""

    def __init__(self, min_delay: float = 1.0):
        self.min_delay = min_delay
        self._last_call: float | None = None

    def wait(self):
        if self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            remaining = self.min_delay - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()
