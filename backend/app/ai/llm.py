"""Central LLM factory.

Single place to construct chat models so every agent shares the same
configuration and we can swap providers/models in one spot. Models are
created lazily by callers (not at import time) so the app and test suite
import cleanly without an ``OPENAI_API_KEY``.
"""

from langchain_openai import ChatOpenAI

from app.core.config import settings

DEFAULT_MODEL = "gpt-4.1-mini"


def get_llm(
    model: str = DEFAULT_MODEL,
    temperature: float = 0,
    structured_output=None,
):
    """Build a chat model, optionally bound to a structured-output schema."""

    # The key lives in our Settings (loaded from .env); pass it explicitly since
    # langchain otherwise only reads os.environ. Fall back to None so an unset
    # key surfaces langchain's clear "missing credentials" error at call time.
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY or None,
    )

    if structured_output is not None:
        return llm.with_structured_output(structured_output)

    return llm
