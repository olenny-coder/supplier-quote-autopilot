"""Send one tiny request to the configured LLM provider and report the result.

The question this answers is "I pasted my API key — is it working?". That is not
the same as "is a key present": a valid-looking key fails for at least four
distinct reasons, and each one needs a different fix.

    uv run python -m scripts.check_llm

Deliberately uses the real client (``app.core.llm_client``) rather than a fresh
httpx call, so it exercises the same retry, throttling and JSON handling the
application uses. A green result here means the app's AI features will work.
"""

import sys

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError
from app.core.llm_client import get_llm_client

PROBE_SYSTEM = "You reply with JSON only. No prose, no markdown fences."
PROBE_USER = 'Return exactly {"ok": true, "vendor": "<your model name>"} and nothing else.'


def main() -> int:
    client = get_llm_client()

    print()
    print("=" * 74)
    print("  LLM provider check")
    print("=" * 74)
    print()
    print(f"  base URL      {client.base_url}")
    print(f"  model         {client.model}")
    print(f"  provider      {client.provider_name()}")
    print(f"  api key       {'set (' + str(len(client.api_key)) + ' chars, ending ' + client.api_key[-4:] + ')' if client.api_key else 'NOT SET'}")
    print(f"  enabled       {settings.LLM_ENABLED}")
    print(f"  rate limit    {client.requests_per_minute}/min, {settings.LLM_MAX_CONCURRENCY} concurrent, {client.max_retries} retries")
    print()

    if not settings.LLM_ENABLED:
        print("  LLM_ENABLED is false, so no request was made.")
        print("  Set LLM_ENABLED=true in backend/.env and restart the API.")
        print()
        return 1

    if not client.api_key:
        print("  No API key configured. This is not an error — the app runs fine")
        print("  without one, using deterministic fallbacks for parsing, follow-up")
        print("  drafting and the comparison narrative.")
        print()
        print("  To enable the AI features:")
        print("    1. Get a free key:  https://console.groq.com  (no credit card)")
        print("    2. In backend/.env set:   LLM_API_KEY=gsk_your_key_here")
        print("    3. Restart the API:       dev.cmd stop   then   dev.cmd")
        print()
        return 0

    print("  Sending one probe request...")

    try:
        payload = _probe(client)
    except LLMUnavailableError as exc:
        _explain_failure(str(exc))
        return 1

    print()
    print("=" * 74)
    print("  OK - the provider answered and returned valid JSON")
    print("=" * 74)
    print()
    print(f"  response      {payload}")
    print(f"  calls made    {client.calls_made}")
    print()
    print("  The AI features are live: quote parsing, follow-up drafting and the")
    print("  comparison narrative will use this model. Restart the API if you have")
    print("  not already, then look for 'AI drafting   ON' in the dev.cmd output.")
    print()

    return 0


def _probe(client) -> dict:
    """One completion, run on a private event loop so this stays a plain script."""

    import asyncio

    return asyncio.run(client.chat_json(PROBE_SYSTEM, PROBE_USER, max_tokens=64))


def _explain_failure(message: str) -> None:
    """Turn a provider error into the specific thing the operator should change.

    Providers all report these as opaque 4xx strings, and the two most common
    causes — a revoked key and a retired model id — look almost identical in a log
    but need completely different fixes. Model ids genuinely do get retired:
    Groq shut down ``llama-3.3-70b-versatile`` on 2026-08-16.
    """

    print()
    print("=" * 74)
    print("  FAILED")
    print("=" * 74)
    print()
    print(f"  {message}")
    print()

    lowered = message.lower()

    if "model_not_found" in lowered or "does not exist" in lowered or "not found" in lowered:
        print("  This is a MODEL problem, not a key problem.")
        print("  The model id in LLM_MODEL is not available on your provider. Model")
        print("  ids get retired — providers shut them down on a schedule, and the")
        print("  old id then fails every request.")
        print()
        print("  Fix: copy a current id from the provider's model list and set it")
        print("  as LLM_MODEL in backend/.env, then restart the API.")
        print()
        print("    Groq        https://console.groq.com/docs/models")
        print("    Deprecations https://console.groq.com/docs/deprecations")
        print("    OpenRouter  https://openrouter.ai/models?max_price=0")
        print("    Gemini      https://ai.google.dev/gemini-api/docs/models")
        print()
        print("  Known-good Groq id at the time of writing:  openai/gpt-oss-120b")
    elif "401" in lowered or "invalid_api_key" in lowered or "unauthorized" in lowered:
        print("  This is a KEY problem.")
        print("  Check LLM_API_KEY in backend/.env: no quotes, no spaces, and the")
        print("  whole key copied (Groq keys start with 'gsk_'). If you regenerated")
        print("  the key in the console, the old one stopped working immediately.")
    elif "429" in lowered or "rate" in lowered:
        print("  The provider is rate limiting you. The client already backs off and")
        print("  retries, so this usually means the free-tier quota for the minute or")
        print("  the day is spent. Wait and retry, or lower")
        print("  LLM_REQUESTS_PER_MINUTE to match your tier.")
    elif "json" in lowered:
        print("  The provider answered but not with a JSON object. Some models need")
        print("  JSON mode explicitly, and some small models cannot produce it at all.")
        print("  Try a larger model — Groq's openai/gpt-oss-120b supports JSON mode.")
    else:
        print("  Check connectivity, the base URL, and that the key belongs to the")
        print("  provider named in LLM_BASE_URL.")

    print()


if __name__ == "__main__":
    sys.exit(main())
