"""Thin wrapper around Resend for sending supplier emails.

The supplier-mail agent only drafts; the actual delivery happens here once the
buyer confirms. Kept in the chat feature slice since that's its only caller.
"""

import asyncio

import resend

from app.core.config import settings
from app.core.exceptions import ExternalServiceError


def _send_sync(to_email: str, subject: str, body: str) -> str:
    resend.api_key = settings.RESEND_API_KEY

    result = resend.Emails.send(
        {
            "from": settings.MAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
    )

    # Resend returns {"id": "..."} on success.
    return (result or {}).get("id", "")


async def send_email(to_email: str, subject: str, body: str) -> str:
    """Send an email via Resend; returns the provider message id.

    Raises ``ExternalServiceError`` when email isn't configured or the send
    fails, so the edge surfaces a clean message to the UI.
    """

    if not settings.RESEND_API_KEY:
        raise ExternalServiceError(
            "Email isn't configured yet — set RESEND_API_KEY in the backend .env."
        )

    # resend's SDK is synchronous; offload so we don't block the event loop.
    try:
        return await asyncio.to_thread(_send_sync, to_email, subject, body)
    except Exception as exc:  # noqa: BLE001 - normalize any SDK/HTTP error
        raise ExternalServiceError(f"Failed to send email: {exc}") from exc
