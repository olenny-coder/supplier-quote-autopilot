"""Public form router — the supplier-facing, login-free API.

Everything under ``/public`` is authenticated by the invitation token in the URL
and nothing else. The three hazards are handled explicitly:

* **Enumeration** — a bad token returns the same 404 everywhere, and short tokens
  are rejected before a database round-trip.
* **Spam** — honeypot, then a per-IP and per-token sliding window, then an
  optional CAPTCHA. Order matters: the free checks run first.
* **Abuse of uploads** — files are validated before being written and are matched
  back to the invitation that was issued the key.
"""

from fastapi import APIRouter
from fastapi import File
from fastapi import Request
from fastapi import UploadFile
from fastapi import Response

from app.core.config import settings
from app.core.dependencies import DBSession
from app.core.exceptions import BadRequestError
from app.core.exceptions import RateLimitedError
from app.core.rate_limit import check_honeypot
from app.core.rate_limit import client_ip
from app.core.rate_limit import get_rate_limiter
from app.core.rate_limit import verify_captcha
from app.features.attachment.service import AttachmentService
from app.features.invitation.schema import InvitationPreview
from app.features.invitation.service import InvitationService
from app.features.public_form.schema import AttachmentUploadResponse
from app.features.public_form.schema import LinkStatusResponse
from app.features.public_form.schema import PublicQuoteResponse
from app.features.public_form.schema import PublicQuoteSubmit
from app.features.public_form.service import PublicFormService

router = APIRouter(
    prefix="/public",
    tags=["Public form"],
)


def _enforce_rate_limit(request: Request, token: str, *, weight: int = 1) -> None:
    """Per-IP and per-token sliding windows.

    Both keys are checked because they catch different abuse: one attacker hitting
    many links is caught by IP, and one widely-shared link being hammered is caught
    by token.
    """

    limiter = get_rate_limiter()

    ip = client_ip(request)

    for key, limit, window in (
        (f"ip:{ip}:min", settings.PUBLIC_RATE_LIMIT_PER_MINUTE, 60),
        (f"ip:{ip}:hour", settings.PUBLIC_RATE_LIMIT_PER_HOUR, 3600),
        (f"token:{token[:12]}:hour", settings.PUBLIC_RATE_LIMIT_PER_HOUR, 3600),
    ):
        for _ in range(weight):
            allowed, retry_after = limiter.check(key, limit, window)

            if not allowed:
                raise RateLimitedError(
                    "Too many submissions from this connection. Please wait a "
                    "moment and try again.",
                    retry_after=retry_after,
                )

    limiter.prune_all()


@router.get(
    "/invitations/{rfq_id}/{token}",
    response_model=InvitationPreview,
)
def get_invitation_preview(
    rfq_id: int,
    token: str,
    request: Request,
    db: DBSession,
):
    """Everything the supplier's form needs to render, and nothing more.

    Notably absent: the RFQ's other quotes, the other suppliers, and any buyer
    financial data. The token grants the right to answer one question, not to read
    the buyer's workspace.
    """

    _enforce_rate_limit(request, token, weight=1)

    invitation, rfq = PublicFormService.load_invitation(db=db, token=token)

    if invitation.rfq_id != rfq_id:
        # The RFQ id in the URL is presentational. A mismatch means the URL was
        # edited or the RFQ moved, either way the link is not trustworthy.
        raise BadRequestError(
            "This quote link does not match the request it points to."
        )

    return InvitationService.build_preview(invitation, rfq)


@router.get(
    "/invitations/{rfq_id}/{token}/status",
    response_model=LinkStatusResponse,
)
def get_link_status(
    rfq_id: int,
    token: str,
    db: DBSession,
):
    """Cheap poll so a supplier can leave the confirmation page open."""

    invitation, _ = PublicFormService.peek(db=db, token=token)

    from datetime import UTC
    from datetime import datetime

    expires_at = invitation.expires_at
    now = datetime.now(UTC)

    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    return LinkStatusResponse(
        status=invitation.status,
        opened=invitation.view_count > 0,
        submitted=invitation.quote is not None,
        is_expired=expires_at is not None and expires_at <= now,
        expires_at=expires_at.isoformat() if expires_at is not None else None,
    )


@router.post(
    "/invitations/{rfq_id}/{token}/attachments",
    response_model=AttachmentUploadResponse,
    status_code=201,
)
async def upload_attachment(
    rfq_id: int,
    token: str,
    request: Request,
    db: DBSession,
    file: UploadFile = File(...),
):
    """Upload one spec sheet or brochure and get back the key to submit with."""

    _enforce_rate_limit(request, token, weight=1)

    invitation, rfq = PublicFormService.peek(db=db, token=token)

    InvitationService.assert_usable(invitation, rfq)

    data = await file.read()

    descriptor = await AttachmentService.store(
        invitation,
        filename=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )

    return AttachmentUploadResponse(
        key=descriptor["key"],
        filename=descriptor["filename"],
        content_type=descriptor["content_type"],
        size=descriptor["size"],
        url=descriptor["url"],
    )


@router.post(
    "/invitations/{rfq_id}/{token}/quote",
    response_model=PublicQuoteResponse,
    status_code=201,
)
async def submit_quote(
    rfq_id: int,
    token: str,
    payload: PublicQuoteSubmit,
    request: Request,
    db: DBSession,
):
    """Submit (or amend) a quote. No login, no account, no signature-up."""

    # ---- 1. anti-spam, cheapest first -------------------------------------
    check_honeypot(payload.company_website)

    # The honeypot already failed fast for bots; real work gets the full budget.
    _enforce_rate_limit(request, token, weight=1)

    await verify_captcha(payload.captcha_token, remote_ip=client_ip(request))

    # ---- 2. resolve the link ----------------------------------------------
    invitation, rfq = PublicFormService.peek(db=db, token=token)

    InvitationService.assert_usable(invitation, rfq)

    if invitation.rfq_id != rfq_id:
        raise BadRequestError(
            "This quote link does not match the request it points to."
        )

    # ---- 3. ingest ---------------------------------------------------------
    return await PublicFormService.submit(
        db=db,
        invitation=invitation,
        rfq=rfq,
        payload=payload,
    )


@router.get("/config")
def public_config():
    """Non-secret form configuration, so the SPA is not built with secrets baked in."""

    from app.core.rate_limit import describe_configuration as describe_spam

    provider = (settings.CAPTCHA_PROVIDER or "none").lower()

    return {
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "allowed_upload_extensions": list(settings.ALLOWED_UPLOAD_EXTENSIONS),
        "captcha": {
            "provider": provider,
            "site_key": (
                settings.CAPTCHA_SITE_KEY
                if provider not in {"", "none", "off", "disabled"}
                else None
            ),
        },
        "spam_protection": describe_spam(),
    }


@router.get(
    "/attachments/{rfq_id}/{token}/{key:path}",
)
async def download_attachment(
    rfq_id: int,
    token: str,
    key: str,
    db: DBSession,
):
    """Serve an uploaded file back to the supplier who uploaded it.

    When the storage backend has a public CDN in front of it this route is unused;
    it exists so a private bucket still works without signed-URL plumbing.
    """

    invitation, _ = PublicFormService.peek(db=db, token=token)

    data, descriptor = await AttachmentService.fetch(invitation.id, key)

    return Response(
        content=data,
        media_type=descriptor.get("content_type", "application/octet-stream"),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{descriptor.get("filename", "attachment")}"'
            ),
            "Cache-Control": "private, max-age=300",
        },
    )
