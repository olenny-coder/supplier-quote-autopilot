"""Central LLM factory for the chat agents.

Single place to construct chat models so every agent shares the same
configuration and we can swap providers/models in one spot. Models are
created lazily by callers (not at import time) so the app and test suite
import cleanly without an API key.

**Provider-agnostic.** The base codebase hard-wired OpenAI with no ``base_url``.
This version points at whatever OpenAI-compatible endpoint ``LLM_BASE_URL``
names, so Groq (the default), OpenRouter, and Gemini all work by changing three
environment variables. The call signature is unchanged, so the existing chat,
orchestrator, and PDF-extraction agents are untouched.

The new autopilot features (quote parsing, follow-up drafting, comparison
narrative) do **not** go through LangChain — they use
:mod:`app.core.llm_client`, which is a plain httpx client with rate-limit spacing
and backoff tuned for free tiers. This factory exists for the LangChain-based
chat agents that were already here.
"""

from langchain_openai import ChatOpenAI

from app.core.config import settings

#: Kept as the fallback so an existing .env that only sets OPENAI_API_KEY still
#: behaves as before; LLM_MODEL wins when it is set.
DEFAULT_MODEL = "gpt-4.1-mini"


def resolved_model(model: str | None = None) -> str:
    if model:
        return model
    return settings.LLM_MODEL or DEFAULT_MODEL


def get_llm(
    model: str | None = None,
    temperature: float = 0,
    structured_output=None,
):
    """Build a chat model, optionally bound to a structured-output schema."""

    # The key lives in our Settings (loaded from .env); pass it explicitly since
    # langchain otherwise only reads os.environ. Fall back to None so an unset
    # key surfaces langchain's clear "missing credentials" error at call time.
    llm = ChatOpenAI(
        model=resolved_model(model),
        temperature=temperature,
        api_key=settings.resolved_llm_api_key or None,
        base_url=settings.LLM_BASE_URL or None,
    )

    if structured_output is not None:
        return llm.with_structured_output(structured_output)

    return llm
