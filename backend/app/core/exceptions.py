"""Domain exception hierarchy and FastAPI handlers.

Services raise these framework-agnostic errors instead of FastAPI's
``HTTPException`` so the domain/service layer stays decoupled from HTTP.
``register_exception_handlers`` translates them into JSON responses at the
edge.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


class ExternalServiceError(AppError):
    """An upstream dependency (e.g. the email provider) failed or is unconfigured."""

    status_code = 502
    detail = "Upstream service error"


def register_exception_handlers(app: FastAPI) -> None:
    """Wire domain errors (and a catch-all) to JSON responses."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )
