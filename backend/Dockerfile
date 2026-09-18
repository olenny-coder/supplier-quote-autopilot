# ---------------------------------------------------------------------------
# Backend image for Supplier Quote Autopilot.
#
# BUILD CONTEXT IS THE REPOSITORY ROOT, not this directory:
#
#     docker build -f backend/Dockerfile .
#
# Why: the repository keeps three importable top-level packages that the backend
# depends on (`backend/`, `agents/`, `comparison/` — see INTEGRATION_PLAN.md).
# They must land as siblings inside the image, exactly as they sit in the repo,
# so `app/__init__.py`'s sys.path bootstrap resolves `import agents` and
# `import comparison` with no environment configuration.
#
#   /app/backend/    FastAPI application  (WORKDIR)
#   /app/agents/     quote-parser + follow-up agents
#   /app/comparison/ landed-cost and scoring engine
# ---------------------------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

RUN pip install --no-cache-dir uv

# Copy the lockfile first so dependency installation is cached across code changes.
COPY backend/pyproject.toml backend/uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

# Application code plus the two sibling domain packages.
COPY backend/ /app/backend/
COPY agents/ /app/agents/
COPY comparison/ /app/comparison/

RUN uv sync --frozen --no-dev

# Belt and braces: the sys.path bootstrap in app/__init__.py already handles this,
# but an explicit PYTHONPATH means a future refactor cannot silently break imports.
ENV PYTHONPATH=/app/backend

EXPOSE 8000

# Render's free tier spins the service down after 15 idle minutes, so the
# healthcheck also serves as the UptimeRobot target documented in the README.
HEALTHCHECK --interval=60s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8).status == 200 else 1)"

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
