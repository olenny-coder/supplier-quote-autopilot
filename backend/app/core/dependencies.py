"""Shared FastAPI dependencies reused across feature routers."""

from typing import Annotated

from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token

# Annotated DB session dependency. Import this in routers instead of
# re-declaring ``Depends(get_db)`` in every feature.
DBSession = Annotated[Session, Depends(get_db)]


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""

    scheme, _, token = header.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def get_current_user(request: Request, db: DBSession):
    """Resolve the authenticated buyer from the ``Authorization: Bearer`` header.

    Imported lazily inside the function to avoid a circular import
    (``app.features.auth.service`` imports this module's ``DBSession``).
    """

    from app.features.auth.service import AuthService

    token = _extract_bearer_token(request)

    if token is None:
        raise UnauthorizedError("Sign in to continue.")

    payload = decode_access_token(token)

    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc

    return AuthService.get_active_user(db=db, user_id=user_id)


CurrentUser = Annotated[object, Depends(get_current_user)]
