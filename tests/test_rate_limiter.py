import time
from stargazer.rate_limiter import RateLimiter


def test_rate_limiter_enforces_delay():
    limiter = RateLimiter(min_delay=0.1)
    start = time.monotonic()
    limiter.wait()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1, f"Expected >= 0.1s, got {elapsed:.3f}s"


def test_rate_limiter_no_delay_on_first_call():
    limiter = RateLimiter(min_delay=1.0)
    start = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed < 0.05, f"First call should be instant, took {elapsed:.3f}s"
