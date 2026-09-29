"""Audit router — read the workspace log, export it as CSV.

Two endpoints, both read-only, both scoped to the authenticated buyer. There is
deliberately no POST (the log is written by the domain services, not by clients)
and no DELETE or PATCH (the whole point of an audit trail is that it cannot be
edited). Both properties are asserted by tests rather than left to this comment.
"""

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.exceptions import BadRequestError
from app.core.mixins import utcnow
from app.features.audit.model import ACTION_LABELS
from app.features.audit.model import ACTOR_TYPES
from app.features.audit.model import ENTITY_TYPES
from app.features.audit.schema import AuditLogResponse
from app.features.audit.service import DEFAULT_PAGE_SIZE
from app.features.audit.service import MAX_PAGE_SIZE
from app.features.audit.service import AuditService

router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
)


def _validate(name: str, value: str | None, allowed: tuple[str, ...]) -> None:
    """Reject a filter value outside the vocabulary.

    A typo would otherwise return an empty page, and an empty audit log reads as
    "nothing has happened" — the most misleading possible answer from this
    endpoint, so it is a 400 instead.
    """

    if value and value not in allowed:
        raise BadRequestError(
            f"Unknown {name} '{value}'. Expected one of: {', '.join(allowed)}."
        )


@router.get(
    "",
    response_model=AuditLogResponse,
)
def list_audit_entries(
    user: CurrentUser,
    db: DBSession,
    action: str | None = Query(
        default=None,
        description=(
            "Filter by action code, e.g. `award.approved`. "
            "`available_actions` lists the codes this workspace has."
        ),
    ),
    entity_type: str | None = Query(
        default=None,
        description="Filter by what the entry is about, e.g. `invitation`.",
    ),
    actor_type: str | None = Query(
        default=None,
        description="`buyer`, `supplier` or `system` (the scheduler).",
    ),
    rfq_id: int | None = Query(
        default=None,
        description="Only entries for one RFQ. Entries for a deleted RFQ keep it.",
    ),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
):
    """The workspace audit log, newest first.

    Every action recorded for this tenant: what was created, changed, sent or
    decided, by whom, and when — including what the scheduler did on the buyer's
    behalf, which is the part a screen-by-screen history cannot show.
    """

    _validate("action", action, tuple(ACTION_LABELS))
    _validate("entity_type", entity_type, ENTITY_TYPES)
    _validate("actor_type", actor_type, ACTOR_TYPES)

    entries, total = AuditService.list_entries(
        db,
        user.id,
        action=action,
        entity_type=entity_type,
        actor_type=actor_type,
        rfq_id=rfq_id,
        limit=limit,
        offset=offset,
    )

    return AuditLogResponse(
        entries=[AuditService.to_response(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
        available_actions=AuditService.available_actions(db, user.id),
        available_rfqs=AuditService.available_rfqs(db, user.id),
    )


@router.get(
    "/export.csv",
)
def export_audit_csv(
    user: CurrentUser,
    db: DBSession,
    action: str | None = None,
    entity_type: str | None = None,
    actor_type: str | None = None,
    rfq_id: int | None = None,
):
    """Download the audit log as CSV, honouring the same filters as the page.

    Oldest first, with a context header naming the workspace, the moment of export
    and the filters applied — because the file is evidence, and evidence that
    cannot say what it is a subset of invites the wrong conclusion.
    """

    _validate("action", action, tuple(ACTION_LABELS))
    _validate("entity_type", entity_type, ENTITY_TYPES)
    _validate("actor_type", actor_type, ACTOR_TYPES)

    csv_text = AuditService.export_csv(
        db,
        user.id,
        buyer_label=user.company_name or user.email,
        action=action,
        entity_type=entity_type,
        actor_type=actor_type,
        rfq_id=rfq_id,
    )

    # The filename carries the workspace id and the date so a buyer who downloads
    # one every month does not end up with `audit-log.csv (7)`.
    filename = f"audit-log-{user.id}-{utcnow().strftime('%Y-%m-%d')}.csv"

    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
