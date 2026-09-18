FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy lockfile first for better layer caching
COPY pyproject.toml uv.lock ./

# Install only production dependencies, honoring the lockfile
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]