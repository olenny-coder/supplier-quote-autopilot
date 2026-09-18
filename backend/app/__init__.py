"""Backend application package.

The repository keeps three importable top-level packages so the domain logic
stays separated from the HTTP layer (see INTEGRATION_PLAN.md §"module layout"):

    backend/      -> this FastAPI application
    agents/       -> follow-up and quote-parsing logic (+ their prompts)
    comparison/   -> currency/incoterm normalisation, costing, scoring

``agents`` and ``comparison`` are siblings of ``backend`` in the repository, not
children of it, so the repository root is added to ``sys.path`` here. Doing it in
one place means ``import comparison`` works identically under ``uv run pytest``,
``uvicorn``, the Docker image, and Render — with no PYTHONPATH configuration
required from an operator.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
