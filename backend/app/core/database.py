"""Database engine and session factory.

Kept on **sync** SQLAlchemy + ``psycopg`` 3, which is what this codebase already
inherited (see INTEGRATION_PLAN.md assumption A1). The workload is small
request-scoped CRUD, ``psycopg`` 3 speaks to Neon's pooled endpoint natively, and
a sync session stays usable from both ``def`` and ``async def`` endpoints because
FastAPI runs ``def`` handlers in a threadpool. All genuinely latency-bound I/O
(LLM, email, object storage) is async elsewhere.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    """Pool settings tuned for Neon.

    Neon closes idle connections when a compute scales to zero, so
    ``pool_pre_ping`` plus a short ``pool_recycle`` avoid handing a dead socket
    to a request. SQLite (used by the test suite) rejects pool sizing args.
    """

    if settings.DATABASE_URL.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}

    return {
        "pool_pre_ping": True,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    }


engine = create_engine(
    settings.DATABASE_URL,
    **_engine_kwargs(),
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    # expire_on_commit is left at SQLAlchemy's default (True) on purpose. The
    # tempting `False` avoids a re-SELECT after every commit, but it also keeps
    # *cached relationship collections* alive — so a long-lived session (the
    # scheduler sweep, the seed script, a multi-step request) can read
    # `rfq.quotes` or `invitation.quote` and get a stale snapshot from before its
    # own inserts. That produced two real bugs during development: a comparison
    # that scored one quote out of three, and a follow-up that skipped a supplier
    # whose quote it could not see. Correctness first; the extra SELECT is cheap.
    expire_on_commit=True,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
