"""Transport boundaries — HTTP email, the LLM client, and the anti-spam limiter.

Two properties dominate this module:

1. **There is no SMTP anywhere, and there must never be.** Render's free tier —
   the documented deployment target — blocks outbound ports 25, 465 and 587, so an
   SMTP dependency would not fail a test, it would take production down. The scan
   below walks the whole codebase and fails if any of those tokens reappears.
2. **The transport is mocked, the domain is not.** Only ``httpx`` is replaced, and
   only at the boundary, so what is asserted is the real request the provider
   would receive: the URL, the authentication mechanism, and the payload.

Everything is offline: no network, no real sleeping (the 429/503 stubs answer
with ``Retry-After: 0``, which the client honours), and no dependence on the
environment beyond what each test monkeypatches.
"""

import io
import json
import re
import tokenize
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.core.email import PROVIDERS
from app.core.email import EmailMessage
from app.core.email import describe_configuration
from app.core.email import parse_mail_from
from app.core.email import send_email_message
from app.core.email import _html_body
from app.core.exceptions import BadRequestError
from app.core.exceptions import ExternalServiceError
from app.core.exceptions import LLMUnavailableError
from app.core.llm_client import LLMClient
from app.core.llm_client import extract_json_object
from app.core.rate_limit import HONEYPOT_FIELD
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.rate_limit import check_honeypot

TEST_FILE = Path(__file__).resolve()
BACKEND_DIR = TEST_FILE.parents[1]
REPO_ROOT = TEST_FILE.parents[2]

#: Every first-party source tree, located relative to this test file so the scan
#: works regardless of the current working directory.
SOURCE_TREES = (
    BACKEND_DIR / "app",
    BACKEND_DIR / "tests",
    REPO_ROOT / "agents",
    REPO_ROOT / "comparison",
)

TEST_KEY = "test-provider-key"
MAIL_FROM = "Procurement Team <quotes@mg.example.com>"
MAILGUN_DOMAIN_URL = "https://api.mailgun.net/v3/mg.example.com/messages"


# =============================================================== no SMTP, ever
#: Token sequences that would mean an SMTP client had been introduced.
SMTP_TOKENS = (
    "import smtplib",
    "from smtplib",
    "smtpd",
    "SMTP(",
    "starttls",
    "ssl.SMTP",
)

#: An SMTP-ish word followed on the same line by one of the blocked ports.
SMTP_PORT_RE = re.compile(
    r"(?:smtp|mail|email|sendmail)[^\n]{0,40}?\b(?:25|465|587)\b", re.IGNORECASE
)

#: A port passed as an argument, and a host:port pair.
PORT_ARGUMENT_RE = re.compile(r"\bport\s*[=:]\s*(?:25|465|587)\b")
HOST_PORT_RE = re.compile(r"[\w.-]+:(?:25|465|587)\b")


def _code_without_comments_or_strings(text: str) -> str:
    """Blank out comments and string literals, preserving line structure.

    ``app/core/email.py`` legitimately *documents* the blocked ports ("Render's
    free tier blocks outbound SMTP ports 25, 465, and 587"), so prose has to be
    excluded or the guard would fire on its own explanation. Strings are removed
    too — an SMTP host inside a string is already caught by the token scan.
    Line structure is kept so the port checks stay line-scoped.
    """

    lines = text.split("\n")

    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)

        for token in tokens:
            if token.type not in (tokenize.COMMENT, tokenize.STRING):
                continue

            start_row, start_column = token.start
            end_row, end_column = token.end

            for row in range(start_row, end_row + 1):
                line = lines[row - 1]
                first = start_column if row == start_row else 0
                last = end_column if row == end_row else len(line)
                lines[row - 1] = line[:first] + " " * (last - first) + line[last:]
    except (tokenize.TokenError, IndentationError):
        return text

    return "\n".join(lines)


def _iter_source_files() -> list[Path]:
    files: list[Path] = []

    for tree in SOURCE_TREES:
        assert tree.is_dir(), f"source tree is missing: {tree}"

        for path in sorted(tree.rglob("*.py")):
            if {"__pycache__", ".venv", ".pytest_cache"} & set(path.parts):
                continue
            # This file necessarily names the forbidden tokens in its assertions.
            if path.resolve() == TEST_FILE:
                continue
            files.append(path)

    return files


def test_the_scan_actually_finds_the_codebase():
    """A broken path must fail loudly rather than make the guard a no-op."""

    files = _iter_source_files()

    assert len(files) > 50
    assert any(path.name == "email.py" for path in files)
    assert any(path.name == "llm_client.py" for path in files)
    assert any(path.name == "engine.py" for path in files)


def test_no_source_file_imports_or_configures_smtp():
    """SMTP cannot work on the free tier, so its presence is a production outage.

    Render blocks outbound 25/465/587; email is therefore HTTPS-API only, and this
    scan is the guard that keeps it that way.
    """

    scanned = 0

    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()

        for token in SMTP_TOKENS:
            assert token.lower() not in lowered, f"{path} contains {token!r}"

        code = _code_without_comments_or_strings(text)
        scanned += 1

        assert PORT_ARGUMENT_RE.search(code) is None, f"{path} passes an SMTP port"
        assert HOST_PORT_RE.search(code) is None, f"{path} dials an SMTP host:port"
        assert SMTP_PORT_RE.search(code) is None, f"{path} mentions SMTP and a blocked port"

    assert scanned == len(_iter_source_files())


def test_email_module_documents_the_https_only_contract():
    """The reason SMTP is absent has to live next to the code that omits it."""

    source = (BACKEND_DIR / "app" / "core" / "email.py").read_text(encoding="utf-8")

    assert "never SMTP" in source
    assert "blocks outbound SMTP ports" in source
    for endpoint in (
        "https://api.resend.com/emails",
        "https://api.sendgrid.com/v3/mail/send",
        "https://api.mailgun.net/v3/",
        "https://api.brevo.com/v3/smtp/email",
    ):
        assert endpoint in source


# ============================================================ email transport
@dataclass(slots=True)
class _Call:
    url: str
    kwargs: dict = field(default_factory=dict)


class _StubAsyncClient:
    """Minimal stand-in for ``httpx.AsyncClient``.

    Replays canned responses in order and records what would have been sent, so a
    test can assert the exact request the provider would receive.
    """

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.calls: list[_Call] = []

    async def __aenter__(self) -> "_StubAsyncClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url: str, **kwargs):
        self.calls.append(_Call(url=url, kwargs=kwargs))
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


def _install_http(monkeypatch, responses: list[httpx.Response]) -> _StubAsyncClient:
    """Replace ``httpx.AsyncClient`` for the duration of one test."""

    client = _StubAsyncClient(responses)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: client)
    return client


def _install_exploding_http(monkeypatch) -> None:
    """Prove that a code path never opens an HTTP client at all."""

    def explode(*args, **kwargs):
        raise AssertionError("no HTTP client may be constructed on this path")

    monkeypatch.setattr(httpx, "AsyncClient", explode)


PROVIDER_CASES: dict[str, dict] = {
    "resend": {
        "url": "https://api.resend.com/emails",
        "headers": {"Authorization": f"Bearer {TEST_KEY}"},
        "response": httpx.Response(200, json={"id": "resend-msg-1"}),
        "message_id": "resend-msg-1",
    },
    "sendgrid": {
        "url": "https://api.sendgrid.com/v3/mail/send",
        "headers": {"Authorization": f"Bearer {TEST_KEY}"},
        "response": httpx.Response(202, headers={"x-message-id": "sendgrid-msg-1"}),
        "message_id": "sendgrid-msg-1",
    },
    "brevo": {
        "url": "https://api.brevo.com/v3/smtp/email",
        "headers": {"api-key": TEST_KEY},
        "response": httpx.Response(201, json={"messageId": "brevo-msg-1"}),
        "message_id": "brevo-msg-1",
    },
    "mailgun": {
        "url": MAILGUN_DOMAIN_URL,
        # Mailgun authenticates with HTTP basic auth rather than a header.
        "auth": ("api", TEST_KEY),
        "response": httpx.Response(200, json={"id": "mailgun-msg-1"}),
        "message_id": "mailgun-msg-1",
    },
}

MESSAGE = EmailMessage(
    to_email="priya@acme.example",
    subject="Quote for RFQ-2026-001",
    body="Please find our price attached.",
    to_name="Priya Sharma",
)


def _configure_provider(monkeypatch, provider: str) -> None:
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", provider)
    monkeypatch.setattr(settings, "EMAIL_API_KEY", TEST_KEY)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "EMAIL_API_URL", "")
    monkeypatch.setattr(settings, "MAIL_FROM", MAIL_FROM)


def test_the_provider_registry_covers_the_documented_http_providers():
    assert set(PROVIDERS) == {"resend", "sendgrid", "brevo", "mailgun"}
    # "console" short-circuits before the registry is consulted.
    assert "console" not in PROVIDERS


async def test_the_console_provider_logs_and_opens_no_connection(monkeypatch):
    """The default backend must short-circuit for real, not send quietly."""

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", TEST_KEY)
    _install_exploding_http(monkeypatch)

    result = await send_email_message(MESSAGE)

    assert result.provider == "console"
    assert result.status == "logged"
    assert result.sent is True


@pytest.mark.parametrize("provider", sorted(PROVIDER_CASES))
async def test_each_provider_is_driven_over_http(provider, monkeypatch):
    """URL, authentication mechanism and payload, per provider."""

    case = PROVIDER_CASES[provider]
    _configure_provider(monkeypatch, provider)
    client = _install_http(monkeypatch, [case["response"]])

    result = await send_email_message(MESSAGE)

    assert len(client.calls) == 1
    call = client.calls[0]

    # (a) the provider's own endpoint
    assert call.url == case["url"]

    # (b) the key travels the way that provider expects
    if "headers" in case:
        for header, value in case["headers"].items():
            assert call.kwargs["headers"][header] == value
    else:
        assert call.kwargs["auth"] == case["auth"]

    # (c) recipient, subject and body all reach the provider
    payload = json.dumps(
        call.kwargs.get("json") or call.kwargs.get("data") or {}, default=str
    )
    assert MESSAGE.to_email in payload
    assert MESSAGE.subject in payload
    assert MESSAGE.body in payload

    assert result.provider == provider
    assert result.status == "sent"
    assert result.message_id == case["message_id"]


@pytest.mark.parametrize("provider", sorted(PROVIDER_CASES))
async def test_a_provider_rejection_surfaces_the_provider_text(provider, monkeypatch):
    """A 4xx is the provider telling us why; that text must reach the operator."""

    _configure_provider(monkeypatch, provider)
    _install_http(monkeypatch, [httpx.Response(422, json={"message": "sender not verified"})])

    with pytest.raises(ExternalServiceError) as excinfo:
        await send_email_message(MESSAGE)

    message = str(excinfo.value)

    assert "HTTP 422" in message
    assert "sender not verified" in message


async def test_an_unknown_provider_names_the_valid_options(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "pigeon")
    _install_exploding_http(monkeypatch)

    with pytest.raises(ExternalServiceError) as excinfo:
        await send_email_message(MESSAGE)

    message = str(excinfo.value)

    assert "pigeon" in message
    for option in ("console", "resend", "sendgrid", "brevo", "mailgun"):
        assert option in message


async def test_an_http_provider_without_a_key_fails_before_any_request(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    _install_exploding_http(monkeypatch)

    with pytest.raises(ExternalServiceError) as excinfo:
        await send_email_message(MESSAGE)

    assert "EMAIL_API_KEY" in str(excinfo.value)


async def test_the_legacy_resend_key_is_still_honoured(monkeypatch):
    """A base-repo deployment that only sets RESEND_API_KEY keeps working."""

    _configure_provider(monkeypatch, "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "legacy-resend-key")
    client = _install_http(monkeypatch, [PROVIDER_CASES["resend"]["response"]])

    await send_email_message(MESSAGE)

    assert client.calls[0].kwargs["headers"]["Authorization"] == "Bearer legacy-resend-key"


async def test_a_network_failure_is_reported_as_an_upstream_problem(monkeypatch):
    """httpx errors must not leak out of the transport boundary."""

    _configure_provider(monkeypatch, "resend")

    class _Boom(_StubAsyncClient):
        async def post(self, url, **kwargs):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _Boom([]))

    with pytest.raises(ExternalServiceError) as excinfo:
        await send_email_message(MESSAGE)

    assert "Could not reach the resend email API" in str(excinfo.value)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Procurement Team <quotes@acme.com>", ("Procurement Team", "quotes@acme.com")),
        ("quotes@acme.com", ("", "quotes@acme.com")),
        ("Supplier Quote Autopilot <onboarding@resend.dev>", ("Supplier Quote Autopilot", "onboarding@resend.dev")),
    ],
)
def test_parse_mail_from(raw, expected):
    assert parse_mail_from(raw) == expected


def test_html_body_escapes_markup_from_the_supplier():
    """A supplier's notes are untrusted input rendered in an email."""

    html = _html_body("<script>alert('xss')</script>\n\nSecond paragraph")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<p>" in html
    assert "Second paragraph" in html


def test_html_body_turns_the_quote_link_into_a_hyperlink():
    """The supplier opens this part on a phone; a flat URL means select-and-copy.

    The link is on its own line in the plain-text body so it is tappable in a mail
    client that only renders text. The HTML part is where it can be a real anchor,
    and that is what a supplier actually taps.
    """

    body = (
        "Submit your quote here — no account or sign-up needed:\n"
        "https://supplier-quote-form.vercel.app/quote/1/aBcDeF-123\n"
        "\n"
        "Thank you."
    )

    html = _html_body(body)

    assert (
        '<a href="https://supplier-quote-form.vercel.app/quote/1/aBcDeF-123"'
        in html
    )
    assert ">https://supplier-quote-form.vercel.app/quote/1/aBcDeF-123</a>" in html

    # The plain-text body is still the source of truth for the visible wording.
    assert "Submit your quote here" in html
    assert "Thank you." in html


def test_a_query_string_survives_linkification():
    """`&` is escaped to `&amp;` first, which is correct in both href and text."""

    html = _html_body("See https://example.com/a?b=1&c=2 now.")

    assert 'href="https://example.com/a?b=1&amp;c=2"' in html
    # A raw ampersand in the href would be an invalid entity reference.
    assert "b=1&c=2" not in html


def test_prose_punctuation_is_not_swallowed_by_the_link():
    for body, expected_href in (
        ("Open https://example.com/x. Then reply.", "https://example.com/x"),
        ("The link (https://example.com/x) works.", "https://example.com/x"),
        ('Open "https://example.com/x" today.', "https://example.com/x"),
    ):
        html = _html_body(body)

        assert f'href="{expected_href}"' in html, body
        # The punctuation itself must still be in the prose, outside the anchor.
        assert "</a>" in html
        assert f"{expected_href}</a>" in html


def test_only_http_schemes_become_links():
    """A javascript: URL in a supplier's notes must never be clickable."""

    html = _html_body("javascript:alert(1) and https://example.com/ok")

    assert "javascript:" in html
    assert 'href="javascript:' not in html

    # The legitimate link on the same line still works.
    assert 'href="https://example.com/ok"' in html


def test_linkification_runs_after_escaping_so_it_cannot_be_used_to_inject():
    """A URL-shaped string inside a tag is escaped text, not a link."""

    html = _html_body('<img src=x onerror=alert(1)> https://example.com/ok')

    assert "<img" not in html
    assert "&lt;img" in html
    assert 'href="https://example.com/ok"' in html


def test_describe_configuration_states_the_transport_honestly(monkeypatch):
    _configure_provider(monkeypatch, "brevo")

    described = describe_configuration()

    assert described["smtp_used"] is False
    assert described["transport"] == "https-api"
    assert described["provider"] == "brevo"
    assert described["configured"] is True
    assert described["from"] == MAIL_FROM


# ================================================================ LLM client
def _completion(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _retryable(status_code: int, **kwargs) -> httpx.Response:
    """A retryable failure that asks to be retried immediately.

    ``Retry-After: 0`` is honoured by the client, which keeps these tests instant
    without mocking out the clock.
    """

    return httpx.Response(status_code, headers={"retry-after": "0"}, **kwargs)


def _llm_client(monkeypatch, **overrides) -> LLMClient:
    monkeypatch.setattr(settings, "LLM_ENABLED", True)

    params = {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": TEST_KEY,
        "model": "test-model",
        "requests_per_minute": 1000,
        "max_concurrency": 2,
        "max_retries": 2,
        "timeout": 5.0,
    }
    params.update(overrides)

    return LLMClient(**params)


async def test_an_empty_api_key_is_unconfigured_and_says_what_to_set(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    _install_exploding_http(monkeypatch)

    client = LLMClient(base_url="https://api.groq.com/openai/v1", api_key="")

    assert client.configured is False

    with pytest.raises(LLMUnavailableError) as excinfo:
        await client.chat([{"role": "user", "content": "hi"}])

    message = str(excinfo.value)
    for variable in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        assert variable in message


async def test_a_disabled_llm_is_unconfigured_even_with_a_key(monkeypatch):
    """LLM_ENABLED=false is the switch that keeps a deployment offline-safe."""

    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    _install_exploding_http(monkeypatch)

    client = LLMClient(
        base_url="https://api.groq.com/openai/v1", api_key=TEST_KEY, model="test-model"
    )

    assert client.configured is False

    with pytest.raises(LLMUnavailableError):
        await client.chat([{"role": "user", "content": "hi"}])


async def test_429_and_5xx_are_retried_and_the_call_then_succeeds(monkeypatch):
    """Free-tier throttling is a routine event, not a failure to surface."""

    client = _llm_client(monkeypatch, max_retries=2)
    stub = _install_http(
        monkeypatch,
        [
            _retryable(429, json={"error": "rate limited"}),
            _retryable(503, json={"error": "overloaded"}),
            httpx.Response(200, json=_completion("hello from the model")),
        ],
    )

    content = await client.chat([{"role": "user", "content": "hi"}])

    assert content == "hello from the model"
    assert len(stub.calls) == 3  # two failures then the success
    assert client.calls_made == 3

    # The request is a normal OpenAI-compatible chat completion.
    sent = stub.calls[0].kwargs
    assert sent["json"]["model"] == "test-model"
    assert sent["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert sent["headers"]["Authorization"] == f"Bearer {TEST_KEY}"
    assert stub.calls[0].url == "https://api.groq.com/openai/v1/chat/completions"


async def test_a_persistent_500_raises_after_max_retries_plus_one_attempts(monkeypatch):
    client = _llm_client(monkeypatch, max_retries=2)
    stub = _install_http(monkeypatch, [_retryable(500, json={"error": "server error"})])

    with pytest.raises(LLMUnavailableError) as excinfo:
        await client.chat([{"role": "user", "content": "hi"}])

    assert len(stub.calls) == 3
    assert "after 3 attempts" in str(excinfo.value)


async def test_a_bad_key_is_not_retried(monkeypatch):
    """Retrying an authentication failure only burns the free-tier quota."""

    client = _llm_client(monkeypatch, max_retries=2)
    stub = _install_http(
        monkeypatch, [httpx.Response(401, json={"error": {"message": "invalid api key"}})]
    )

    with pytest.raises(LLMUnavailableError) as excinfo:
        await client.chat([{"role": "user", "content": "hi"}])

    assert len(stub.calls) == 1
    assert "HTTP 401" in str(excinfo.value)
    assert "invalid api key" in str(excinfo.value)


async def test_chat_json_asks_for_a_json_object_and_returns_it(monkeypatch):
    client = _llm_client(monkeypatch)
    stub = _install_http(
        monkeypatch,
        [httpx.Response(200, json=_completion('```json\n{"subject": "hi"}\n```'))],
    )

    parsed = await client.chat_json("system prompt", "user prompt")

    assert parsed == {"subject": "hi"}
    assert stub.calls[-1].kwargs["json"]["response_format"] == {"type": "json_object"}


async def test_chat_json_raises_when_the_model_returns_prose(monkeypatch):
    client = _llm_client(monkeypatch)
    _install_http(
        monkeypatch,
        [httpx.Response(200, json=_completion("I am sorry, I cannot help with that."))],
    )

    with pytest.raises(LLMUnavailableError) as excinfo:
        await client.chat_json("system prompt", "user prompt")

    assert "JSON object" in str(excinfo.value)


async def test_an_unexpected_response_shape_is_reported_not_leaked(monkeypatch):
    client = _llm_client(monkeypatch)
    _install_http(monkeypatch, [httpx.Response(200, json={"unexpected": True})])

    with pytest.raises(LLMUnavailableError) as excinfo:
        await client.chat([{"role": "user", "content": "hi"}])

    assert "Unexpected LLM response shape" in str(excinfo.value)


@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("https://api.groq.com/openai/v1", "groq"),
        ("https://openrouter.ai/api/v1", "openrouter"),
        ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini"),
        ("https://api.example.com/v1", "custom"),
    ],
)
def test_provider_name_recognises_the_presets(base_url, expected):
    assert LLMClient(base_url=base_url, api_key=TEST_KEY).provider_name() == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"subject": "hi", "body": "there"}', {"subject": "hi", "body": "there"}),
        ('```json\n{"subject": "hi"}\n```', {"subject": "hi"}),
        ("```\n{\"subject\": \"hi\"}\n```", {"subject": "hi"}),
        ('Sure! Here is the JSON: {"subject": "hi"} — hope that helps.', {"subject": "hi"}),
        ('{"nested": {"a": 1}} trailing prose', {"nested": {"a": 1}}),
        ("no object here at all", None),
        ("", None),
    ],
)
def test_extract_json_object_recovers_a_model_object(text, expected):
    assert extract_json_object(text) == expected


# ------------------------------------------------- reasoning-model token budget
def test_a_reasoning_model_is_told_to_think_briefly(monkeypatch):
    """The default free model is a *reasoning* model, and that broke every LLM call.

    The defect: ``openai/gpt-oss-120b`` emits a reasoning trace before its answer.
    Left at the provider's default trace length, Groq's free tier rejected the
    request outright — HTTP 400 ``json_validate_failed``, "max completion tokens
    reached before generating a valid document" — so quote parsing, follow-up
    drafting and comparison summaries all fell back to their deterministic paths.
    Nothing failed loudly; the product just quietly stopped using the model.
    """

    monkeypatch.setattr(settings, "LLM_REASONING_EFFORT", "low")

    client = LLMClient(api_key=TEST_KEY, model="openai/gpt-oss-120b")

    payload = client.build_payload(
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=1024,
        json_mode=False,
    )

    assert payload["reasoning_effort"] == "low"


def test_a_non_reasoning_model_is_not_sent_reasoning_effort(monkeypatch):
    """An unconditional parameter would 400 the cheaper model someone switched to."""

    monkeypatch.setattr(settings, "LLM_REASONING_EFFORT", "low")

    for model in ("llama-3.3-70b-versatile", "gemini-2.0-flash", "meta-llama/llama-4-scout"):
        client = LLMClient(api_key=TEST_KEY, model=model)

        payload = client.build_payload(
            [{"role": "user", "content": "hi"}],
            temperature=0.0,
            max_tokens=1024,
            json_mode=True,
        )

        assert "reasoning_effort" not in payload, model
        assert payload["response_format"] == {"type": "json_object"}


def test_setting_the_effort_to_empty_sends_the_parameter_at_all(monkeypatch):
    """The documented escape hatch for an endpoint that rejects the field."""

    monkeypatch.setattr(settings, "LLM_REASONING_EFFORT", "")

    client = LLMClient(api_key=TEST_KEY, model="openai/gpt-oss-120b")

    payload = client.build_payload(
        [{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_tokens=1024,
        json_mode=False,
    )

    assert "reasoning_effort" not in payload


def test_the_json_budget_is_large_enough_for_a_trace_plus_an_answer():
    """A tight budget is what turned a reasoning trace into a hard provider error."""

    import inspect

    default = (
        inspect.signature(LLMClient.chat_json).parameters["max_tokens"].default
    )

    assert default >= 4096


# ============================================================== rate limiting
def test_the_sliding_window_allows_the_limit_then_denies_with_a_retry_after():
    limiter = SlidingWindowRateLimiter()

    assert limiter.check("1.2.3.4", limit=2, window_seconds=60) == (True, 0)
    assert limiter.check("1.2.3.4", limit=2, window_seconds=60) == (True, 0)

    allowed, retry_after = limiter.check("1.2.3.4", limit=2, window_seconds=60)

    assert allowed is False
    assert retry_after > 0  # the caller is told when to try again
    assert retry_after <= 61


def test_keys_are_counted_independently():
    limiter = SlidingWindowRateLimiter()

    assert limiter.check("a", limit=1, window_seconds=60)[0] is True
    assert limiter.check("a", limit=1, window_seconds=60)[0] is False
    # A second client must not be punished for the first one's traffic.
    assert limiter.check("b", limit=1, window_seconds=60)[0] is True


def test_reset_clears_a_key():
    limiter = SlidingWindowRateLimiter()
    limiter.check("1.2.3.4", limit=1, window_seconds=60)

    limiter.reset("1.2.3.4")

    assert limiter.check("1.2.3.4", limit=1, window_seconds=60) == (True, 0)


def test_reset_without_a_key_clears_every_bucket():
    limiter = SlidingWindowRateLimiter()
    limiter.check("a", limit=1, window_seconds=60)
    limiter.check("b", limit=1, window_seconds=60)

    limiter.reset()

    assert limiter.check("a", limit=1, window_seconds=60) == (True, 0)
    assert limiter.check("b", limit=1, window_seconds=60) == (True, 0)


def test_prune_all_drops_stale_buckets():
    """The bucket dict is in-process memory and must not grow without bound."""

    limiter = SlidingWindowRateLimiter()
    limiter.check("stale", limit=5, window_seconds=60)
    limiter.check("fresh", limit=5, window_seconds=60)

    # A negative window makes every existing bucket count as stale, so the test
    # does not have to wait for real time to pass.
    limiter.prune_all(window_seconds=-1)

    assert "stale" not in limiter._buckets
    assert "fresh" not in limiter._buckets
    # Pruning is a no-op for correctness: the key simply starts a fresh window.
    assert limiter.check("stale", limit=5, window_seconds=60) == (True, 0)


def test_prune_all_keeps_live_buckets():
    limiter = SlidingWindowRateLimiter()
    limiter.check("live", limit=5, window_seconds=60)

    limiter.prune_all(window_seconds=3600)

    assert len(limiter._buckets["live"].hits) == 1


def test_a_zero_limit_disables_limiting():
    limiter = SlidingWindowRateLimiter()

    for _ in range(5):
        assert limiter.check("k", limit=0, window_seconds=60) == (True, 0)


@pytest.mark.parametrize("value", ["", None, "   "])
def test_the_honeypot_accepts_an_empty_field(value):
    """The hidden field is empty for every human and every honest client."""

    assert check_honeypot(value) is None


def test_the_honeypot_rejects_a_filled_field():
    with pytest.raises(BadRequestError):
        check_honeypot("http://spam.example")


def test_the_honeypot_field_name_is_the_one_the_form_renders():
    assert HONEYPOT_FIELD == "company_website"
