"""Attachment service — supplier file uploads.

Files arrive at a public, token-authenticated endpoint, so this module is where the
trust boundary sits. Three rules:

1. **Validate before writing.** Size, extension, and empty-file checks all run
   before a byte reaches storage.
2. **Never trust a filename.** The storage key is generated
   (``invitations/<id>/<uuid>.<ext>``) and the original name is kept only as
   display metadata, so path traversal is impossible by construction.
3. **Claim-by-key, not by upload.** A submission references attachments by key, and
   :func:`resolve` verifies each key was actually issued to *this* invitation.
   Otherwise a supplier could reference another supplier's file.
"""

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.mixins import utcnow
from app.core.storage import build_storage_key
from app.core.storage import get_storage
from app.core.storage import validate_upload
from app.features.invitation.model import Invitation

logger = logging.getLogger(__name__)

#: In-process registry of issued attachment keys, keyed by invitation.
#:
#: Deliberately in-memory: an upload and the submit that references it happen
#: seconds apart in the same session, and the alternative — a table and a
#: migration — buys durability nobody needs for a file that is dropped unless it
#: is referenced. Orphaned objects are cleaned up by ``prune``.
_ISSUED: dict[int, dict[str, dict]] = {}

MAX_TRACKED_PER_INVITATION = 20


class AttachmentService:
    @staticmethod
    async def store(
        invitation: Invitation,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> dict:
        """Validate and persist one upload, returning its descriptor."""

        validate_upload(filename, len(data), content_type)

        key = build_storage_key(f"invitations/{invitation.id}", filename)

        storage = get_storage()

        await storage.save(key, data, content_type or "application/octet-stream")

        descriptor = {
            "key": key,
            "filename": filename,
            "content_type": content_type or "application/octet-stream",
            "size": len(data),
            "url": storage.url_for(key),
            "uploaded_at": utcnow().isoformat(),
        }

        bucket = _ISSUED.setdefault(invitation.id, {})

        # Keep the registry bounded — an abusive client must not grow it forever.
        if len(bucket) >= MAX_TRACKED_PER_INVITATION:
            oldest = next(iter(bucket))
            bucket.pop(oldest, None)

        bucket[key] = descriptor

        return descriptor

    @staticmethod
    def resolve(
        db: Session,
        invitation: Invitation,
        keys: list[str],
    ) -> list[dict]:
        """Return descriptors for keys issued to this invitation, ignoring others."""

        bucket = _ISSUED.get(invitation.id, {})

        resolved: list[dict] = []

        for key in keys:
            descriptor = bucket.get(key)

            if descriptor is None:
                logger.warning(
                    "Attachment key %s was not issued to invitation %s; ignoring",
                    key,
                    invitation.id,
                )
                continue

            resolved.append(descriptor)

        # A submission with no claimable attachments is fine; it just means the
        # supplier did not attach anything.
        if keys and not resolved:
            raise BadRequestError(
                "The attached file could not be matched to this quote link. "
                "Please upload it again."
            )

        return resolved

    @staticmethod
    async def fetch(invitation_id: int, key: str) -> tuple[bytes, dict]:
        """Read a stored attachment back, checking it belongs to the invitation."""

        descriptor = _ISSUED.get(invitation_id, {}).get(key)

        if descriptor is None:
            raise BadRequestError("Unknown attachment.")

        data = await get_storage().read(key)

        return data, descriptor

    @staticmethod
    async def delete(invitation_id: int, key: str) -> None:
        descriptor = _ISSUED.get(invitation_id, {}).pop(key, None)

        if descriptor is not None:
            await get_storage().delete(key)

    @staticmethod
    def reset() -> None:
        """Clear the registry — used by tests."""

        _ISSUED.clear()

    @staticmethod
    def issued_for(invitation_id: int) -> dict[str, dict]:
        return dict(_ISSUED.get(invitation_id, {}))
