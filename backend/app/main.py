"""FastAPI application entry point.

Wiring, lifespan, and health. Everything else lives in a feature slice.

Notable behaviours:

* ``Base.metadata.create_all`` runs at startup (kept from the base codebase) so
  ``docker compose up`` and a first Render boot work with zero manual steps.
  Alembic is the authority thereafter — see ``alembic/`` and the README.
* The follow-up scheduler starts as a background task and is cancelled on
  shutdown. It is also drivable over HTTP for an external cron, because Render's
  free tier spins the service down after 15 idle minutes.
* ``/health`` is the UptimeRobot target and reports the dependency status without
  ever raising, so a cold Neon compute reads as ``degraded`` rather than as an
  outage.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import models  # noqa: F401 - registers every table on Base.metadata
from app.ai.completer import llm_status
from app.core.config import DEV_SECRET_KEY
from app.core.config import settings
from app.core.database import Base
from app.core.database import engine
from app.core.email import describe_configuration as describe_email
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import describe_configuration as describe_spam
from app.core.storage import get_storage
from app.features.auth.router import router as auth_router
from app.features.chat.router import router as chat_router
from app.features.comparison.router import router as comparison_router
from app.features.dashboard.router import router as dashboard_router
from app.features.followup.router import internal_router
from app.features.followup.router import router as followup_router
from app.features.followup.scheduler import runner as scheduler_runner
from app.features.invitation.router import router as invitation_router
from app.features.public_form.router import router as public_form_router
from app.features.quote.router import router as quote_router
from app.features.rfq.router import router as rfq_router
from app.features.supplier.router import router as supplier_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def _warn_about_configuration() -> None:
    """Fail loudly in the logs about the settings that silently break production."""

    if settings.is_production:
        if settings.SECRET_KEY == DEV_SECRET_KEY:
            logger.error(
                "SECRET_KEY is still the development default. Anyone can mint a "
                "valid session token. Set SECRET_KEY before going live."
            )
        if "*" in settings.ALLOWED_ORIGINS:
            logger.warning(
                "ALLOWED_ORIGINS is '*' in production. Set it to your frontend and "
                "public-form origins."
            )
        if not settings.SCHEDULER_SECRET:
            logger.warning(
                "SCHEDULER_SECRET is unset, so POST /internal/scheduler/tick is "
                "disabled. Follow-ups will only run while the service is awake."
            )

    if not settings.llm_configured():
        logger.warning(
            "No LLM provider configured (LLM_API_KEY is empty). Quote parsing, "
            "follow-up drafting, and comparison summaries will use their "
            "deterministic fallbacks. See README 4-Free LLM provider."
        )

    if settings.STORAGE_BACKEND == "local" and settings.is_production:
        logger.warning(
            "STORAGE_BACKEND=local in production. Render's free tier has no "
            "persistent disk, so uploads will be lost on the next deploy. "
            "Use STORAGE_BACKEND=s3."
        )

    if settings.EMAIL_PROVIDER == "console" and settings.is_production:
        logger.warning(
            "EMAIL_PROVIDER=console in production: no email will actually be sent."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_about_configuration()

    try:
        Base.metadata.create_all(bind=engine)
    except Exception:  # noqa: BLE001 - a cold Neon compute should not stop boot
        logger.exception(
            "Could not create tables at startup. If the database is cold this is "
            "expected; otherwise run 'alembic upgrade head'."
        )

    scheduler_runner.start()

    try:
        yield
    finally:
        await scheduler_runner.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description=(
        "Supplier Quote Autopilot — run RFQs, collect quotes through tokenized "
        "public forms, chase the gaps automatically, and compare quotes on landed "
        "cost with a weighted score.\n\n"
        "**Authentication.** Buyer endpoints take `Authorization: Bearer <jwt>` "
        "from `POST /auth/login`. The `/public/*` endpoints take no credentials: "
        "they are authenticated by the invitation token in the URL.\n\n"
        "**Guardrails.** Nothing is ever auto-awarded. The comparison endpoint "
        "recommends; `POST /rfqs/{id}/comparison/approve` is the only path to an "
        "award, and it requires an authenticated human and a written reason."
    ),
    openapi_tags=[
        {"name": "Auth", "description": "Buyer accounts and sessions."},
        {"name": "RFQs", "description": "Requests for quotation."},
        {"name": "Suppliers", "description": "The buyer's supplier directory."},
        {"name": "Invitations", "description": "Tokenized form links per supplier."},
        {"name": "Quotes", "description": "Quotes from every source."},
        {
            "name": "Public form",
            "description": "Supplier-facing. No auth beyond the URL token.",
        },
        {"name": "Follow-ups", "description": "Reminder drafts, approvals, and log."},
        {
            "name": "Comparison",
            "description": "Normalized cost comparison, scoring, and award approval.",
        },
        {"name": "Dashboard", "description": "Aggregated workspace summary."},
        {"name": "Chat", "description": "AI procurement assistant."},
        {"name": "Internal", "description": "Shared-secret cron endpoints."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

register_exception_handlers(app)

# ---- buyer API -------------------------------------------------------------
app.include_router(auth_router)
app.include_router(rfq_router)
app.include_router(supplier_router)
app.include_router(invitation_router)
app.include_router(quote_router)
app.include_router(followup_router)
app.include_router(comparison_router)
app.include_router(dashboard_router)
app.include_router(chat_router)

# ---- public (token-authenticated) ------------------------------------------
app.include_router(public_form_router)

# ---- internal (shared secret) ----------------------------------------------
app.include_router(internal_router)


@app.get("/health", tags=["Internal"])
def health_check():
    """Liveness + dependency status.

    Always returns 200 so UptimeRobot's ping counts as "up" and keeps the free
    instance warm; the ``status`` field carries the real picture. Pinging every
    14 minutes is what avoids Render's 15-minute spin-down — see the README.
    """

    database_ok = True
    database_error = None

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health must never raise
        database_ok = False
        database_error = type(exc).__name__

    storage_backend = settings.STORAGE_BACKEND

    try:
        get_storage()
        storage_ok = True
    except Exception as exc:  # noqa: BLE001
        storage_ok = False
        storage_backend = f"{storage_backend} (misconfigured: {type(exc).__name__})"

    llm = llm_status()
    email = describe_email()

    degraded = not database_ok or not storage_ok

    return JSONResponse(
        status_code=200,
        content={
            "status": "degraded" if degraded else "ok",
            "message": "Server is running",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENV,
            "database": {
                "connected": database_ok,
                "error": database_error,
                # A cold Neon compute returns an error on the first attempt and
                # succeeds on the next; this field tells the reader which it was.
                "note": (
                    "Neon scales to zero after 5 idle minutes; the first request "
                    "after that is slow."
                ),
            },
            "storage": {"backend": storage_backend, "ok": storage_ok},
            "llm": llm,
            "email": email,
            "spam_protection": describe_spam(),
            "scheduler": {
                "enabled": settings.SCHEDULER_ENABLED,
                "running": scheduler_runner.running,
                "interval_minutes": settings.SCHEDULER_INTERVAL_MINUTES,
                "external_tick_enabled": bool(settings.SCHEDULER_SECRET),
                "auto_send_followups": settings.AUTO_SEND_FOLLOWUPS,
                "intervals_hours": settings.FOLLOWUP_INTERVALS_HOURS,
            },
        },
    )


@app.get("/files/{key:path}", tags=["Internal"])
def serve_file(key: str):
    """Storage proxy used when the object store has no public CDN domain."""

    import asyncio

    from fastapi import Response

    from app.core.storage import get_storage as _storage

    storage = _storage()

    if storage.__class__.__name__ == "LocalStorage":
        # Local files are written under UPLOAD_DIR and are only meant for dev.
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")

    try:
        data = asyncio.run(storage.read(key))
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found") from exc

    return Response(content=data, media_type="application/octet-stream")
