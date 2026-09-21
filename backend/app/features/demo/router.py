"""Demo router — one read-only endpoint.

Every route here is a ``GET`` and nothing else. That is the whole enforcement of
"you can look, but you cannot run a live request through": a request that would
change state has no route to arrive at, so no token, cookie or query parameter can
turn the demo into a write. There is no database session in this feature either, so
even a bug here cannot reach a row.

Rate-limited on the same per-IP windows as the rest of the unauthenticated surface,
because this endpoint is readable by anyone who finds the URL.
"""

from fastapi import APIRouter
from fastapi import Request

from app.core.config import settings
from app.core.rate_limit import client_ip
from app.core.rate_limit import get_rate_limiter
from app.core.exceptions import RateLimitedError
from app.features.demo.workspace import DISCLAIMER
from app.features.demo.workspace import get_workspace

router = APIRouter(
    prefix="/demo",
    tags=["Demo"],
)


@router.get(
    "/workspace",
    summary="The read-only demo workspace",
)
def get_demo_workspace(request: Request) -> dict:
    """A complete sample tender: RFQs, quotes, the scored comparison, follow-ups.

    No credentials, no database, and nothing that can be written to. The payload is
    a committed snapshot generated from the demo seed — see
    :mod:`app.features.demo.workspace` for why it is a file rather than a query.
    """

    limiter = get_rate_limiter()

    ip = client_ip(request)

    for key, limit, window in (
        (f"demo:ip:{ip}:min", settings.PUBLIC_RATE_LIMIT_PER_MINUTE, 60),
        (f"demo:ip:{ip}:hour", settings.PUBLIC_RATE_LIMIT_PER_HOUR, 3600),
    ):
        allowed, retry_after = limiter.check(key, limit, window)

        if not allowed:
            raise RateLimitedError(
                "Too many demo requests from this connection. Please wait a moment.",
                retry_after=retry_after,
            )

    limiter.prune_all()

    workspace = get_workspace()

    # The disclaimer is served rather than duplicated in the front end, so the two
    # cannot disagree about what the demo does and does not do.
    return {**workspace, "disclaimer": DISCLAIMER}
