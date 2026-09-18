"""Anti-spam for the public supplier form: rate limiting, honeypot, CAPTCHA.

Three independent layers, cheapest first:

1. **Honeypot** — a field that is invisible to humans. Any value in it means a
   bot. This is a pure check with no state.
2. **Rate limiting** — an in-process sliding window keyed by client IP and by
   invitation token. Adequate for a single Render instance, which is what the
   free tier runs. (A multi-instance deployment would move this to Redis; noted
   in the README rather than pre-built.)
3. **CAPTCHA** — optional, because it needs a site key an MVP operator may not
   have. Cloudflare Turnstile and hCaptcha are supported; both are free.
"""

import logging
import time
from collections import defaultdict
from collections import deque
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)

HONEYPOT_FIELD = "company_website"

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"


# ------------------------------------------------------------------- honeypot
def check_honeypot(value: str | None) -> None:
    """Reject the submission if the hidden field was filled in.

    The field is named something a bot's autofill heuristics find plausible
    (``company_website``) and is hidden from humans with CSS, not with
    ``type="hidden"`` — which bots skip.
    """

    if value and value.strip():
        logger.warning("Honeypot triggered — discarding public form submission")
        raise BadRequestError("Submission rejected.")


# ---------------------------------------------------------------- rate limiting
@dataclass
class _Window:
    hits: deque[float]

    def prune(self, now: float, window_seconds: float) -> None:
        while self.hits and now - self.hits[0] > window_seconds:
            self.hits.popleft()


class SlidingWindowRateLimiter:
    """In-process sliding-window counter."""

    def __init__(self) -> None:
        self._buckets: dict[str, _Window] = defaultdict(lambda: _Window(deque()))

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: float,
    ) -> tuple[bool, int]:
        """Record a hit. Returns ``(allowed, retry_after_seconds)``."""

        if limit <= 0:
            return True, 0

        now = time.monotonic()
        window = self._buckets[key]
        window.prune(now, window_seconds)

        if len(window.hits) >= limit:
            retry_after = int(window_seconds - (now - window.hits[0])) + 1
            return False, max(1, retry_after)

        window.hits.append(now)
        return True, 0

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)

    def prune_all(self, window_seconds: float = 3600) -> None:
        """Drop stale buckets so the dict cannot grow without bound."""

        now = time.monotonic()
        stale = [
            key
            for key, window in self._buckets.items()
            if not window.hits or now - window.hits[-1] > window_seconds
        ]
        for key in stale:
            self._buckets.pop(key, None)


_limiter = SlidingWindowRateLimiter()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    return _limiter


def reset_rate_limiter() -> None:
    _limiter.reset()


def client_ip(request) -> str:
    """Best-effort client IP, honouring the proxy headers Render sets."""

    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")

    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------- CAPTCHA
async def verify_captcha(token: str | None, remote_ip: str | None = None) -> None:
    """Verify a CAPTCHA token when a provider is configured.

    No-op when ``CAPTCHA_PROVIDER=none``, which is the default: the honeypot and
    rate limiter are always active and need no third-party account.
    """

    provider = (settings.CAPTCHA_PROVIDER or "none").lower().strip()

    if provider in {"", "none", "off", "disabled"}:
        return

    if not settings.CAPTCHA_SECRET_KEY:
        logger.warning(
            "CAPTCHA_PROVIDER=%s but CAPTCHA_SECRET_KEY is unset; skipping verification",
            provider,
        )
        return

    if not token:
        raise BadRequestError("CAPTCHA verification is required.")

    if provider == "turnstile":
        url, payload = TURNSTILE_VERIFY_URL, {
            "secret": settings.CAPTCHA_SECRET_KEY,
            "response": token,
        }
    elif provider == "hcaptcha":
        url, payload = HCAPTCHA_VERIFY_URL, {
            "secret": settings.CAPTCHA_SECRET_KEY,
            "response": token,
        }
    else:
        logger.warning("Unknown CAPTCHA_PROVIDER '%s'; skipping", provider)
        return

    if remote_ip:
        payload["remoteip"] = remote_ip

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, data=payload)

    try:
        body = response.json()
    except ValueError as exc:
        raise BadRequestError("CAPTCHA verification failed.") from exc

    if not body.get("success"):
        raise BadRequestError("CAPTCHA verification failed. Please try again.")


def describe_configuration() -> dict[str, object]:
    provider = (settings.CAPTCHA_PROVIDER or "none").lower().strip()

    return {
        "captcha_provider": provider,
        "captcha_enabled": provider not in {"", "none", "off", "disabled"},
        "honeypot_field": HONEYPOT_FIELD,
        "rate_limit_per_minute": settings.PUBLIC_RATE_LIMIT_PER_MINUTE,
        "rate_limit_per_hour": settings.PUBLIC_RATE_LIMIT_PER_HOUR,
    }
