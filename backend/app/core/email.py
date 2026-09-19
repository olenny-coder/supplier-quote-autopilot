"""Transactional email over HTTPS APIs — never SMTP.

**Why this module exists.** Render's free tier blocks outbound SMTP ports 25,
465, and 587. Any design that opens an SMTP connection simply does not work
there. This module therefore only ever speaks HTTPS to a provider's REST API and
offers four providers plus a console backend:

    console   — development: the message is logged, nothing is sent
    resend    — https://api.resend.com/emails
    sendgrid  — https://api.sendgrid.com/v3/mail/send
    mailgun   — https://api.mailgun.net/v3/<domain>/messages
    brevo     — https://api.brevo.com/v3/smtp/email

Adding a provider means adding one ``_send_*`` function and one dict entry.

There is deliberately **no** ``smtplib`` import anywhere in this codebase;
``tests/test_email.py`` asserts that so a future change cannot reintroduce it.
"""

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from dataclasses import field
from email.utils import parseaddr

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_MAILGUN_DOMAIN_RE = re.compile(r"@([^>\s]+)")

DEFAULT_TIMEOUT = 20.0


@dataclass(slots=True)
class EmailMessage:
    """A message ready to hand to a provider."""

    to_email: str
    subject: str
    body: str
    to_name: str | None = None
    reply_to: str | None = None
    attachments: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class EmailResult:
    provider: str
    status: str
    message_id: str = ""
    detail: str = ""

    @property
    def sent(self) -> bool:
        return self.status in {"sent", "logged"}


def parse_mail_from(value: str) -> tuple[str, str]:
    """Split ``"Name <addr@host>"`` into ``(name, addr)``."""

    name, address = parseaddr(value)

    if not address:
        return "", value.strip()

    return name, address


def _html_body(body: str) -> str:
    """Wrap a plain-text body in minimal HTML, with bare URLs as real links.

    Deliberately not a templating engine: escaping the text and preserving line
    breaks keeps the plain-text body as the single source of truth, so the two
    representations cannot drift. The only transformation beyond escaping is
    linkifying ``http(s)`` URLs, because a supplier reading the HTML part on a
    phone should be able to tap the quote link rather than select and copy it.
    """

    escaped = _linkify(html.escape(body))
    paragraphs = [
        f"<p>{block.replace(chr(10), '<br />')}</p>"
        for block in escaped.split("\n\n")
        if block.strip()
    ]

    return (
        "<div style=\"font-family:system-ui,-apple-system,'Segoe UI',sans-serif;"
        'font-size:15px;line-height:1.55;color:#0f172a">'
        + "".join(paragraphs)
        + "</div>"
    )


#: A bare ``http(s)`` URL inside already-escaped text.
#:
#: Written for escaped text, which is why it is not the obvious ``\S+``. After
#: escaping, an ampersand has become either ``&amp;`` — part of a real query
#: string, and wanted — or the start of some other entity such as ``&quot;``,
#: which would be the *prose* around the URL and must stop the match. Allowing
#: ``&amp;`` explicitly while excluding a bare ``&`` distinguishes the two.
_URL_RE = re.compile(r"https?://(?:[^\s<>\"'&]|&amp;)+")

#: Punctuation that ends a sentence far more often than it ends a URL.
_TRAILING_PUNCTUATION = ".,;:!?)]}\u201d"


def _linkify(escaped_text: str) -> str:
    """Turn bare URLs into anchors, preserving the surrounding text verbatim.

    Runs on the **escaped** text on purpose: the URL is already HTML-safe, so the
    same string is correct in both the ``href`` and the visible link text, and no
    second escaping step can disagree with the first.

    Only ``http`` and ``https`` are matched. A ``javascript:`` URL in a supplier's
    name or notes therefore cannot become a clickable link.
    """

    def replace(match: re.Match[str]) -> str:
        url = match.group(0)
        trailing = ""

        while url and url[-1] in _TRAILING_PUNCTUATION:
            trailing = url[-1] + trailing
            url = url[:-1]

        if not url:
            return match.group(0)

        return (
            f'<a href="{url}" style="color:#1d4ed8;text-decoration:underline;'
            f'word-break:break-all">{url}</a>{trailing}'
        )

    return _URL_RE.sub(replace, escaped_text)


# ---------------------------------------------------------------- provider send
async def _send_resend(client: httpx.AsyncClient, message: EmailMessage) -> EmailResult:
    sender = settings.MAIL_FROM
    response = await client.post(
        settings.EMAIL_API_URL or "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resolved_email_api_key}"},
        json={
            "from": sender,
            "to": [message.to_email],
            "subject": message.subject,
            "text": message.body,
            "html": _html_body(message.body),
            **({"reply_to": message.reply_to} if message.reply_to else {}),
        },
        timeout=DEFAULT_TIMEOUT,
    )
    _raise_for_provider_error(response, "Resend")

    return EmailResult("resend", "sent", (response.json() or {}).get("id", ""))


async def _send_sendgrid(
    client: httpx.AsyncClient, message: EmailMessage
) -> EmailResult:
    name, address = parse_mail_from(settings.MAIL_FROM)

    response = await client.post(
        settings.EMAIL_API_URL or "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {settings.resolved_email_api_key}"},
        json={
            "personalizations": [
                {
                    "to": [
                        {
                            "email": message.to_email,
                            **({"name": message.to_name} if message.to_name else {}),
                        }
                    ]
                }
            ],
            "from": {"email": address, **({"name": name} if name else {})},
            "subject": message.subject,
            "content": [
                {"type": "text/plain", "value": message.body},
                {"type": "text/html", "value": _html_body(message.body)},
            ],
        },
        timeout=DEFAULT_TIMEOUT,
    )
    _raise_for_provider_error(response, "SendGrid")

    # SendGrid returns 202 with no body; the message id is in a header.
    return EmailResult("sendgrid", "sent", response.headers.get("x-message-id", ""))


async def _send_mailgun(
    client: httpx.AsyncClient, message: EmailMessage
) -> EmailResult:
    # Mailgun's endpoint is per-domain, so the domain is taken from MAIL_FROM
    # rather than added as a fifth variable that could disagree with it.
    domain_match = _MAILGUN_DOMAIN_RE.search(settings.MAIL_FROM)

    if not domain_match:
        raise ExternalServiceError(
            "Mailgun needs a sending domain: set MAIL_FROM to an address on your "
            "Mailgun domain, e.g. 'Procurement <quotes@mg.example.com>'."
        )

    domain = domain_match.group(1)

    url = settings.EMAIL_API_URL or f"https://api.mailgun.net/v3/{domain}/messages"

    response = await client.post(
        url,
        auth=("api", settings.resolved_email_api_key),
        data={
            "from": settings.MAIL_FROM,
            "to": message.to_email,
            "subject": message.subject,
            "text": message.body,
            "html": _html_body(message.body),
        },
        timeout=DEFAULT_TIMEOUT,
    )
    _raise_for_provider_error(response, "Mailgun")

    return EmailResult("mailgun", "sent", (response.json() or {}).get("id", ""))


async def _send_brevo(client: httpx.AsyncClient, message: EmailMessage) -> EmailResult:
    name, address = parse_mail_from(settings.MAIL_FROM)

    response = await client.post(
        settings.EMAIL_API_URL or "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": settings.resolved_email_api_key,
            "accept": "application/json",
        },
        json={
            "sender": {"email": address, **({"name": name} if name else {})},
            "to": [
                {
                    "email": message.to_email,
                    **({"name": message.to_name} if message.to_name else {}),
                }
            ],
            "subject": message.subject,
            "textContent": message.body,
            "htmlContent": _html_body(message.body),
        },
        timeout=DEFAULT_TIMEOUT,
    )
    _raise_for_provider_error(response, "Brevo")

    return EmailResult("brevo", "sent", (response.json() or {}).get("messageId", ""))


def _raise_for_provider_error(response: httpx.Response, provider: str) -> None:
    if response.status_code >= 400:
        raise ExternalServiceError(
            f"{provider} rejected the email (HTTP {response.status_code}): "
            f"{response.text[:300]}"
        )


PROVIDERS = {
    "resend": _send_resend,
    "sendgrid": _send_sendgrid,
    "mailgun": _send_mailgun,
    "brevo": _send_brevo,
}


# -------------------------------------------------------------------- public API
async def send_email_message(message: EmailMessage) -> EmailResult:
    """Deliver one message. Raises ``ExternalServiceError`` on failure."""

    provider = (settings.EMAIL_PROVIDER or "console").lower().strip()

    if provider == "console":
        logger.info(
            "\n"
            "────────── EMAIL (console backend, not actually sent) ──────────\n"
            "To:      %s\n"
            "Subject: %s\n"
            "----------------------------------------------------------------\n"
            "%s\n"
            "────────────────────────────────────────────────────────────────",
            f"{message.to_name} <{message.to_email}>" if message.to_name else message.to_email,
            message.subject,
            message.body,
        )
        return EmailResult("console", "logged", "console")

    if provider not in PROVIDERS:
        raise ExternalServiceError(
            f"Unknown EMAIL_PROVIDER '{provider}'. "
            f"Use one of: console, {', '.join(sorted(PROVIDERS))}."
        )

    if not settings.resolved_email_api_key:
        raise ExternalServiceError(
            f"EMAIL_PROVIDER={provider} requires EMAIL_API_KEY. "
            "Set it in the environment (see .env.example)."
        )

    async with httpx.AsyncClient() as client:
        try:
            return await PROVIDERS[provider](client, message)
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Could not reach the {provider} email API: {exc}"
            ) from exc


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    to_name: str | None = None,
    reply_to: str | None = None,
) -> EmailResult:
    """Backwards-compatible convenience wrapper used by the chat feature."""

    return await send_email_message(
        EmailMessage(
            to_email=to_email,
            subject=subject,
            body=body,
            to_name=to_name,
            reply_to=reply_to,
        )
    )


async def send_email_sync_compat(to_email: str, subject: str, body: str) -> str:
    """Old ``mailer.send_email`` contract: returns the provider message id."""

    result = await send_email(to_email=to_email, subject=subject, body=body)
    return result.message_id


def describe_configuration() -> dict[str, object]:
    """Non-secret summary for ``/health`` so a bad provider is diagnosable."""

    provider = (settings.EMAIL_PROVIDER or "console").lower().strip()

    return {
        "provider": provider,
        "configured": settings.email_configured(),
        "transport": "https-api",
        "smtp_used": False,
        "from": settings.MAIL_FROM,
    }


async def send_batch(messages: list[EmailMessage]) -> list[EmailResult]:
    """Send several messages, replacing provider failures with a failed result.

    Used by the follow-up scheduler, where one supplier's bounced address must
    not abort the whole run. Individual senders that need the error should call
    :func:`send_email_message` directly.
    """

    results: list[EmailResult] = []

    for message in messages:
        try:
            results.append(await send_email_message(message))
        except ExternalServiceError as exc:
            logger.warning("Batch email to %s failed: %s", message.to_email, exc)
            results.append(
                EmailResult(
                    provider=settings.EMAIL_PROVIDER,
                    status="failed",
                    detail=str(exc),
                )
            )

        # Small gap keeps us inside free-tier per-second limits.
        await asyncio.sleep(0.2)

    return results
