"""Thin wrapper around the HTTP email transport for supplier emails.

The supplier-mail agent only drafts; the actual delivery happens here once the
buyer confirms. Kept in the chat feature slice since that's its only caller.

Delegates to :mod:`app.core.email`, which is HTTPS-only — the base codebase called
Resend's SDK directly, which made the provider non-swappable and gave the app a
hard dependency on one vendor. The ``send_email`` signature is unchanged.
"""

from app.core.email import EmailResult
from app.core.email import send_email as _send_email

__all__ = ["EmailResult", "send_email"]


async def send_email(to_email: str, subject: str, body: str) -> str:
    """Send an email and return the provider message id.

    Raises ``ExternalServiceError`` when email isn't configured or the send
    fails, so the edge surfaces a clean message to the UI.
    """

    result = await _send_email(to_email=to_email, subject=subject, body=body)

    return result.message_id
