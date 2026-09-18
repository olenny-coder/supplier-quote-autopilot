"""OpenAI-compatible LLM client with free-tier guardrails.

One client, three providers. The only thing that changes between Groq,
OpenRouter, and Gemini is the base URL and model id, both of which come from the
environment:

    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_API_KEY=gsk_...
    LLM_MODEL=llama-3.3-70b-versatile

Everything here exists to keep a *free* tier usable:

* **Spacing** — requests are spaced so we never exceed
  ``LLM_REQUESTS_PER_MINUTE`` (Groq's free tier is ~30/min). A sliding window of
  recent call timestamps blocks the caller instead of letting the provider 429.
* **Concurrency cap** — ``LLM_MAX_CONCURRENCY`` in-flight requests.
* **Retry with backoff** — 429 and 5xx responses are retried with exponential
  backoff plus jitter, honouring ``Retry-After`` when the provider sends it.
* **Fail soft** — every public method raises ``LLMUnavailableError`` rather than
  leaking httpx errors. Callers in ``agents/`` catch it and fall back to a
  deterministic path, so an exhausted quota degrades the product instead of
  breaking it.
* **JSON mode** — ``chat_json`` asks for a JSON object and repairs the common
  ways small free models return one (markdown fences, prose around the object).
"""

import asyncio
import json
import logging
import random
import re
import time
from collections import deque
from typing import Any

import httpx

from app.core.config import LLM_PROVIDER_PRESETS
from app.core.config import settings
from app.core.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class LLMClient:
    """Async OpenAI-compatible chat client."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        requests_per_minute: int | None = None,
        max_concurrency: int | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.resolved_llm_api_key
        self.model = model or settings.LLM_MODEL
        self.requests_per_minute = requests_per_minute or settings.LLM_REQUESTS_PER_MINUTE
        self.max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS

        concurrency = max_concurrency or settings.LLM_MAX_CONCURRENCY
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._recent_calls: deque[float] = deque()
        self._throttle_lock = asyncio.Lock()

        #: Counts calls made by this process, so batch jobs can stop at a budget.
        self.calls_made = 0

    # ------------------------------------------------------------------ config
    @property
    def configured(self) -> bool:
        return bool(settings.LLM_ENABLED and self.api_key and self.base_url)

    def provider_name(self) -> str:
        for name, preset in LLM_PROVIDER_PRESETS.items():
            if preset["base_url"].rstrip("/") == self.base_url:
                return name
        return "custom"

    # ----------------------------------------------------------------- throttling
    async def _wait_for_slot(self) -> None:
        """Block until the last 60 s contain fewer than RPM calls."""

        if self.requests_per_minute <= 0:
            return

        async with self._throttle_lock:
            now = time.monotonic()

            while self._recent_calls and now - self._recent_calls[0] > 60:
                self._recent_calls.popleft()

            if len(self._recent_calls) >= self.requests_per_minute:
                sleep_for = 60 - (now - self._recent_calls[0]) + 0.05
                logger.info(
                    "LLM rate limit reached (%s/min); sleeping %.1fs",
                    self.requests_per_minute,
                    sleep_for,
                )
                await asyncio.sleep(max(0.05, sleep_for))
                now = time.monotonic()
                while self._recent_calls and now - self._recent_calls[0] > 60:
                    self._recent_calls.popleft()

            self._recent_calls.append(time.monotonic())

    # ---------------------------------------------------------------------- HTTP
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion and return the assistant message content."""

        if not self.configured:
            raise LLMUnavailableError(
                "No LLM provider configured. Set LLM_BASE_URL, LLM_API_KEY and "
                "LLM_MODEL (see README §Free LLM provider)."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            await self._wait_for_slot()

            try:
                async with self._semaphore:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                # OpenRouter asks for attribution headers; the
                                # other providers ignore them.
                                "HTTP-Referer": settings.BACKEND_URL,
                                "X-Title": settings.APP_NAME,
                            },
                            json=payload,
                        )

                self.calls_made += 1

                if response.status_code == 429 or response.status_code >= 500:
                    last_error = LLMUnavailableError(
                        f"LLM provider returned HTTP {response.status_code}"
                    )
                    delay = self._retry_delay(attempt, response)
                    logger.warning(
                        "LLM call failed (HTTP %s, attempt %s/%s); retrying in %.1fs",
                        response.status_code,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 400:
                    # 4xx other than 429 is our fault (bad model id, bad key).
                    # Retrying cannot help, so fail fast with the provider's text.
                    detail = response.text[:500]
                    raise LLMUnavailableError(
                        f"LLM provider rejected the request "
                        f"(HTTP {response.status_code}): {detail}"
                    )

                body = response.json()
                return self._extract_content(body)

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                delay = self._retry_delay(attempt, None)
                logger.warning(
                    "LLM transport error (%s, attempt %s/%s); retrying in %.1fs",
                    type(exc).__name__,
                    attempt + 1,
                    self.max_retries + 1,
                    delay,
                )
                await asyncio.sleep(delay)

        raise LLMUnavailableError(
            f"LLM provider unavailable after {self.max_retries + 1} attempts: {last_error}"
        )

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """Chat completion constrained to a JSON object.

        Providers differ in how strictly they honour ``response_format``, so the
        raw text goes through :func:`extract_json_object` before ``json.loads``.
        """

        content = await self.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        parsed = extract_json_object(content)

        if parsed is None:
            raise LLMUnavailableError(
                "The model did not return a JSON object. Try a larger LLM_MODEL."
            )

        return parsed

    # -------------------------------------------------------------------- helpers
    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        try:
            return body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"Unexpected LLM response shape: {str(body)[:300]}"
            ) from exc

    @staticmethod
    def _retry_delay(attempt: int, response: httpx.Response | None) -> float:
        """Exponential backoff with jitter, honouring ``Retry-After``."""

        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    return min(60.0, float(retry_after))
                except ValueError:
                    pass

        return min(30.0, (2**attempt) * 0.8) + random.uniform(0, 0.5)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort recovery of a JSON object from model output.

    Handles markdown fences, leading prose, and trailing commentary — all of
    which small free models emit despite ``response_format``.
    """

    if not text:
        return None

    candidates: list[str] = []

    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1).strip())

    candidates.append(text.strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Process-wide client (its throttle window must be shared to be effective)."""

    global _client

    if _client is None:
        _client = LLMClient()

    return _client


def reset_llm_client() -> None:
    """Drop the cached client — used by tests and after settings changes."""

    global _client
    _client = None
