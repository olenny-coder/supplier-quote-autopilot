"""Test configuration.

The suite runs against a temporary SQLite database so it needs no services, and it
pins the environment *before* ``app.core.config`` is imported — settings are read
once at import time, so any test that changed them afterwards would be testing a
different application than the one that boots in production.

What is pinned, and why:

* ``DATABASE_URL`` — a file-backed SQLite database. A file rather than
  ``:memory:`` because FastAPI runs sync endpoints in a worker thread, and an
  in-memory SQLite database is not shared across connections.
* ``EMAIL_PROVIDER=console`` — no email leaves the test run. The console backend
  also lets tests assert on what *would* have been sent.
* ``LLM_API_KEY=""`` — the suite exercises the deterministic fallback paths, so it
  is fast, offline, and reproducible. The LLM paths are tested by injecting a fake
  completer, never a real provider.
* ``SCHEDULER_ENABLED=false`` — the scheduler is driven explicitly via
  ``run_scheduler`` in tests, so a background timer would only add nondeterminism.
* ``SCHEDULER_SECRET`` — set so the cron endpoint's authentication can be tested.
"""

import os
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="sqa-tests-"))
TEST_DB_PATH = TEST_DIR / "test.db"

os.environ.update(
    {
        "ENV": "test",
        "DATABASE_URL": f"sqlite:///{TEST_DB_PATH.as_posix()}",
        "SECRET_KEY": "test-secret-key-not-for-production",
        "EMAIL_PROVIDER": "console",
        "EMAIL_API_KEY": "",
        "RESEND_API_KEY": "",
        "OPENAI_API_KEY": "",
        "LLM_API_KEY": "",
        "LLM_ENABLED": "false",
        "STORAGE_BACKEND": "local",
        "UPLOAD_DIR": (TEST_DIR / "uploads").as_posix(),
        "SCHEDULER_ENABLED": "false",
        "SCHEDULER_SECRET": "test-scheduler-secret",
        "AUTO_SEND_FOLLOWUPS": "false",
        "CAPTCHA_PROVIDER": "none",
        "PUBLIC_RATE_LIMIT_PER_MINUTE": "20",
        "PUBLIC_RATE_LIMIT_PER_HOUR": "60",
        "BACKEND_URL": "http://testserver",
        "FRONTEND_URL": "http://localhost:5173",
        "PUBLIC_FORM_URL": "http://localhost:5174",
        "ALLOWED_ORIGINS": "*",
        "FOLLOWUP_INTERVALS_HOURS": "72,168",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.core.rate_limit import reset_rate_limiter  # noqa: E402
from app.features.attachment.service import AttachmentService  # noqa: E402

# Importing the app registers every route and, via app.models, every table.
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """A clean database for every test."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def _reset_process_state():
    """In-process caches must not leak between tests."""

    reset_rate_limiter()
    AttachmentService.reset()

    yield

    reset_rate_limiter()
    AttachmentService.reset()


@pytest.fixture(scope="function")
def client(db_session):
    """A TestClient sharing the test's database session.

    The lifespan is deliberately *not* run: schema creation happens in a fixture,
    and the background scheduler must not start during tests.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def strict_client(db_session):
    """Like ``client`` but lets application exceptions propagate to the test."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class FakeCompleter:
    """Stands in for :class:`app.core.llm_client.LLMClient.chat_json`.

    Records the prompts it was given so tests can assert that grounding context
    reached the model, without any network call.
    """

    def __init__(self, responses=None, fail: bool = False):
        self.responses = list(responses or [])
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, system: str, user: str):
        self.calls.append((system, user))

        if self.fail:
            raise RuntimeError("simulated provider outage")

        if not self.responses:
            return None

        response = self.responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


@pytest.fixture
def fake_completer():
    return FakeCompleter
