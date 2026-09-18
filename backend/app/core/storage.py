"""Attachment storage: local filesystem in dev, S3-compatible in production.

Render's free tier has **no persistent disk**, so production must use object
storage. Any S3-compatible service works — Cloudflare R2, Backblaze B2, or Neon
Object Storage — configured with ``STORAGE_BACKEND=s3`` plus the ``S3_*``
variables.

Storage keys are always ``<scope>/<uuid><ext>``: caller-supplied names never
reach the filesystem, which removes path traversal as a category of bug. The
original filename is preserved separately, in the attachment record.
"""

import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


class StorageBackend(Protocol):
    """Minimal contract both backends satisfy."""

    async def save(self, key: str, data: bytes, content_type: str) -> None: ...

    async def read(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def url_for(self, key: str) -> str: ...


# --------------------------------------------------------------------- helpers
def build_storage_key(scope: str, filename: str) -> str:
    """``('invitations/42', 'Spec Sheet.PDF') -> 'invitations/42/9f3c....pdf'``."""

    safe_scope = "/".join(
        _SAFE_SEGMENT_RE.sub("-", part) for part in scope.split("/") if part
    )
    suffix = Path(filename or "").suffix.lower()
    suffix = _SAFE_SEGMENT_RE.sub("", suffix)

    return f"{safe_scope}/{uuid.uuid4().hex}{suffix}"


def validate_upload(filename: str, size_bytes: int, content_type: str | None) -> None:
    """Reject oversized files and unexpected extensions before anything is written."""

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    if size_bytes <= 0:
        raise BadRequestError("The uploaded file is empty.")

    if size_bytes > max_bytes:
        raise BadRequestError(
            f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit."
        )

    suffix = Path(filename or "").suffix.lower()

    if not suffix:
        raise BadRequestError("The uploaded file needs a filename with an extension.")

    if suffix not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_UPLOAD_EXTENSIONS)
        raise BadRequestError(f"Unsupported file type '{suffix}'. Allowed: {allowed}.")

    if content_type and content_type.startswith("text/html"):
        raise BadRequestError("HTML uploads are not accepted.")


# ----------------------------------------------------------------------- local
class LocalStorage:
    """Filesystem backend for development and single-container deployments."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.UPLOAD_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()

        # Defensive: build_storage_key already sanitises, but a resolved-path
        # check means no future caller can escape the root either.
        if not str(candidate).startswith(str(self.root)):
            raise BadRequestError("Invalid storage key.")

        return candidate

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(path.write_bytes, data)

    async def read(self, key: str) -> bytes:
        path = self._path(key)

        if not path.exists():
            raise ExternalServiceError("Attachment not found in storage.")

        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)

        if path.exists():
            await asyncio.to_thread(path.unlink)

    def url_for(self, key: str) -> str:
        return f"{settings.BACKEND_URL.rstrip('/')}/files/{key}"


# -------------------------------------------------------------------------- S3
class S3Storage:
    """Any S3-compatible object store (R2 / B2 / Neon Object Storage / AWS)."""

    def __init__(self) -> None:
        if not settings.S3_BUCKET:
            raise ExternalServiceError(
                "STORAGE_BACKEND=s3 requires S3_BUCKET and S3 credentials."
            )

        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on extras
            raise ExternalServiceError(
                "boto3 is not installed; add it or use STORAGE_BACKEND=local."
            ) from exc

        self.bucket = settings.S3_BUCKET

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
        )

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )

    async def read(self, key: str) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self.bucket,
            Key=key,
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self.bucket,
            Key=key,
        )

    def url_for(self, key: str) -> str:
        if settings.S3_PUBLIC_BASE_URL:
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"

        # No public domain configured: serve through the backend proxy so a
        # private bucket still works without signed-URL plumbing.
        return f"{settings.BACKEND_URL.rstrip('/')}/files/{key}"


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend

    if _backend is None:
        if settings.STORAGE_BACKEND.lower() == "s3":
            _backend = S3Storage()
        else:
            _backend = LocalStorage()

    return _backend


def reset_storage() -> None:
    global _backend
    _backend = None
