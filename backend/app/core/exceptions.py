"""Domain exception hierarchy and FastAPI handlers.

Services raise these framework-agnostic errors instead of FastAPI's
``HTTPException`` so the domain/service layer stays decoupled from HTTP.
``register_exception_handlers`` translates them into JSON responses at the
edge.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error. Carries the HTTP status used at the edge."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class BadRequestError(AppError):
    status_code = 400
    detail = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Not authenticated"


class ForbiddenError(AppError):
    status_code = 403
    detail = "You do not have access to this resource"


class ConflictError(AppError):
    status_code = 409
    detail = "Resource already exists"


class RateLimitedError(AppError):
    """Too many requests — used by the public form's anti-spam limiter."""

    status_code = 429
    detail = "Too many requests — please try again later."

    def __init__(self, detail: str | None = None, retry_after: int = 60) -> None:
        super().__init__(detail)
        self.retry_after = retry_after


class ExternalServiceError(AppError):
    """An upstream dependency (e.g. the email provider) failed or is unconfigured."""

    status_code = 502
    detail = "Upstream service error"


class LLMUnavailableError(AppError):
    """The configured LLM provider is unreachable, unconfigured, or rate-limited.

    Callers are expected to fall back to the deterministic paths in
    ``agents/`` and ``comparison/`` rather than surfacing this to a buyer.
    """

    status_code = 503
    detail = "The AI provider is unavailable right now."


class InvitationExpiredError(AppError):
    status_code = 410
    detail = "This quote link has expired."


class InvitationAlreadyUsedError(AppError):
    status_code = 409
    detail = "A quote has already been submitted with this link."


def register_exception_handlers(app: FastAPI) -> None:
    """Wire domain errors (and a catch-all) to JSON responses."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        headers = {}

        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)

        if isinstance(exc, UnauthorizedError):
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Flatten pydantic's error list into a single readable ``detail``.

        The base repo's API client shows ``response.data.detail`` verbatim, so a
        plain string keeps every form error readable in the UI.
        """

        problems = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            message = error.get("msg", "Invalid value")
            problems.append(f"{location}: {message}" if location else message)

        return JSONResponse(
            status_code=422,
            content={"detail": "; ".join(problems) or "Invalid request."},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)

        detail = "Internal server error"

        # In production the exception text is not echoed back to the client.
        from app.core.config import settings

        if not settings.is_production:
            detail = f"{type(exc).__name__}: {exc}"

        return JSONResponse(
            status_code=500,
            content={"detail": detail},
        )
