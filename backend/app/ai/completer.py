"""Bridge between the pure agent packages and the configured LLM provider.

``agents/quote_parser`` and ``agents/followup`` accept an LLM as a plain async
callable so they stay free of provider SDKs. This module is that callable: it
wraps :class:`app.core.llm_client.LLMClient` and returns ``None`` when no provider
is configured, which is the signal both packages use to stay on their
deterministic path.
"""

import logging
from typing import Any

from app.core.config import settings
from app.core.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def llm_available() -> bool:
    """True when a provider is configured and enabled.

    Checked before starting a batch so the scheduler can decide once, up front,
    whether to attempt LLM work at all — rather than making fifty doomed calls.
    """

    return settings.llm_configured() and get_llm_client().configured


async def complete_json(system: str, user: str) -> dict[str, Any] | None:
    """JSON completion, or ``None`` when the LLM is unavailable.

    Never raises: callers treat ``None`` as "use the fallback". An exhausted free
    tier degrades the product to its deterministic path, it does not break it.
    """

    client = get_llm_client()

    if not client.configured:
        return None

    try:
        return await client.chat_json(system, user)
    except Exception as exc:  # noqa: BLE001 - the LLM is optional by design
        logger.warning("LLM completion unavailable, using fallback: %s", exc)
        return None


def get_completer():
    """Return the completer callable, or ``None`` when no provider is configured."""

    if not llm_available():
        return None

    return complete_json


def llm_status() -> dict[str, object]:
    """Non-secret provider summary for ``/health``."""

    client = get_llm_client()

    return {
        "enabled": settings.LLM_ENABLED,
        "configured": client.configured,
        "provider": client.provider_name(),
        "base_url": client.base_url,
        "model": client.model,
        "requests_per_minute": client.requests_per_minute,
        "max_concurrency": settings.LLM_MAX_CONCURRENCY,
        "max_retries": client.max_retries,
        "calls_made": client.calls_made,
    }
