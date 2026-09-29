"""Audit service — write the log, read it back, export it.

The writer is the interesting half. It is called from the domain services rather
than from a middleware or a decorator, for one reason: only the service knows what
the action *meant*. An HTTP-level log can say ``POST /rfqs/12/invitations``
returned 201; it cannot say that four suppliers were invited, which RFQ they were
invited to, or that one of the four was already in the directory. It also cannot
see the scheduler at all, which acts inside the web process without a request —
and the scheduler's reminders are exactly the kind of action a buyer needs to be
able to account for.

The cost of that choice is that the call sites have to pass a sentence and an
actor. That is the price of a log worth reading, and it keeps the wording next to
the code that knows the facts.
"""

import csv
from datetime import datetime
from io import StringIO
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mixins import utcnow
from app.features.audit.model import ACTION_LABELS
from app.features.audit.model import AuditEntry
from app.features.audit.model import label_for
from app.features.audit.schema import AuditActionOption
from app.features.audit.schema import AuditEntryResponse
from app.features.audit.schema import AuditRFQOption
from app.features.auth.model import User
from app.features.rfq.model import RFQ

#: Rows returned when the caller does not say. Large enough that the first page is
#: the whole of a typical workspace's history, small enough that a workspace with
#: years of scheduler reminders cannot return a 40 MB JSON response.
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

#: The export is not paged, so it needs its own ceiling. A CSV is for a human or a
#: spreadsheet, and neither wants a million rows; the newest 20 000 are the ones
#: that matter, and the file itself says so when it truncates.
MAX_EXPORT_ROWS = 20_000

#: CSV column order. Written for a spreadsheet: when, who, what, and the reference
#: a buyer would search on, before the free text.
CSV_HEADERS = [
    "Timestamp (UTC)",
    "Action",
    "Action code",
    "Actor",
    "Actor type",
    "RFQ number",
    "Item",
    "Entity",
    "Entity ID",
    "Summary",
    "Detail",
]


class AuditService:
    # ------------------------------------------------------------------ writing
    @staticmethod
    def record(
        db: Session,
        *,
        user_id: int | None,
        action: str,
        entity_type: str,
        summary: str,
        entity_id: int | None = None,
        actor_type: str = "buyer",
        actor_label: str | None = None,
        rfq: RFQ | None = None,
        rfq_id: int | None = None,
        rfq_number: str | None = None,
        item_name: str | None = None,
        detail: dict[str, Any] | None = None,
        commit: bool = False,
    ) -> AuditEntry | None:
        """Append one entry and return it.

        Never raises on its own account, and never rolls back the caller's work:
        with the default ``commit=False`` the row is only added to the session (the
        session has ``autoflush=False``), so it rides along with the caller's own
        commit. A failure to write an audit line must not fail the action it
        describes — a buyer who cannot invite a supplier because the log is full has
        been made worse off by the audit trail, which is the opposite of the point.

        ``user_id`` is ``None`` for actions with no workspace behind them (the seed
        script run against a database with no accounts). Those are skipped rather
        than written with a null tenant, because the log is scoped by workspace and
        an entry no workspace can read is noise.

        ``rfq`` expands into the three snapshot columns. Pass ``rfq_id``,
        ``rfq_number`` and ``item_name`` explicitly instead when the RFQ row has
        already been deleted — which is what ``RFQService.delete`` does, and the
        reason those columns exist at all.
        """

        if user_id is None:
            return None

        entry = AuditEntry(
            user_id=user_id,
            rfq_id=rfq.id if rfq is not None else rfq_id,
            # Snapshotted, not joined — see the model docstring.
            rfq_number=(rfq.rfq_number if rfq is not None else rfq_number),
            item_name=(rfq.item_name if rfq is not None else item_name),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_label=actor_label or AuditService._default_actor_label(db, user_id),
            summary=summary,
            detail=detail or None,
        )

        db.add(entry)

        if commit:
            db.commit()
            db.refresh(entry)

        return entry

    @staticmethod
    def _default_actor_label(db: Session, user_id: int) -> str:
        """The buyer's company, falling back to the account email.

        ``db.get`` hits the session's identity map first, so this is usually free:
        the request that triggered the action already loaded the current user.
        """

        user = db.get(User, user_id)

        if user is None:
            return "Buyer account"

        return user.company_name or user.email

    @staticmethod
    def actor_for(user: User | None) -> tuple[str, str]:
        """``(actor_type, actor_label)`` for a request-scoped user."""

        if user is None:
            return "system", "Scheduler"

        return "buyer", (user.company_name or user.email)

    # ------------------------------------------------------------------ reading
    @staticmethod
    def _filters(
        user_id: int,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        actor_type: str | None = None,
        rfq_id: int | None = None,
    ) -> list:
        """The WHERE clauses every read shares, so the page and the export agree."""

        clauses = [AuditEntry.user_id == user_id]

        if action:
            clauses.append(AuditEntry.action == action)

        if entity_type:
            clauses.append(AuditEntry.entity_type == entity_type)

        if actor_type:
            clauses.append(AuditEntry.actor_type == actor_type)

        if rfq_id is not None:
            clauses.append(AuditEntry.rfq_id == rfq_id)

        return clauses

    @staticmethod
    def list_entries(
        db: Session,
        user_id: int,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        actor_type: str | None = None,
        rfq_id: int | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> tuple[list[AuditEntry], int]:
        """Newest first, plus the total matching the same filters."""

        clauses = AuditService._filters(
            user_id,
            action=action,
            entity_type=entity_type,
            actor_type=actor_type,
            rfq_id=rfq_id,
        )

        stmt = (
            select(AuditEntry)
            .where(*clauses)
            # `id` breaks ties inside a second, and ties are common: one request
            # can write three entries with the same timestamp, and without the
            # second key their order is whatever the planner returns.
            .order_by(AuditEntry.created_at.desc(), AuditEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )

        entries = list(db.scalars(stmt).all())

        total = db.scalar(
            select(func.count(AuditEntry.id)).where(*clauses)
        )

        return entries, int(total or 0)

    @staticmethod
    def available_actions(db: Session, user_id: int) -> list[AuditActionOption]:
        """The actions this workspace has actually seen, most frequent first."""

        stmt = (
            select(AuditEntry.action, func.count(AuditEntry.id))
            .where(AuditEntry.user_id == user_id)
            .group_by(AuditEntry.action)
            .order_by(func.count(AuditEntry.id).desc(), AuditEntry.action.asc())
        )

        return [
            AuditActionOption(
                action=row[0],
                label=label_for(row[0]),
                count=int(row[1]),
            )
            for row in db.execute(stmt).all()
        ]

    @staticmethod
    def available_rfqs(db: Session, user_id: int, limit: int = 200) -> list[AuditRFQOption]:
        """The RFQs this workspace has entries for, newest first.

        Grouped off the log rather than off ``rfqs`` on purpose: the filter should
        offer the RFQs that can actually return something, including a deleted one
        whose entries survive.
        """

        stmt = (
            select(
                AuditEntry.rfq_id,
                AuditEntry.rfq_number,
                AuditEntry.item_name,
                func.max(AuditEntry.id).label("latest"),
            )
            .where(AuditEntry.user_id == user_id, AuditEntry.rfq_id.is_not(None))
            .group_by(AuditEntry.rfq_id, AuditEntry.rfq_number, AuditEntry.item_name)
            .order_by(func.max(AuditEntry.id).desc())
            .limit(limit)
        )

        return [
            AuditRFQOption(rfq_id=row[0], rfq_number=row[1], item_name=row[2])
            for row in db.execute(stmt).all()
        ]

    @staticmethod
    def to_response(entry: AuditEntry) -> AuditEntryResponse:
        return AuditEntryResponse(
            id=entry.id,
            created_at=entry.created_at,
            action=entry.action,
            action_label=label_for(entry.action),
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            rfq_id=entry.rfq_id,
            rfq_number=entry.rfq_number,
            item_name=entry.item_name,
            actor_type=entry.actor_type,
            actor_label=entry.actor_label,
            summary=entry.summary,
            detail=entry.detail,
        )

    # ----------------------------------------------------------------- exporting
    @staticmethod
    def export_csv(
        db: Session,
        user_id: int,
        *,
        buyer_label: str,
        action: str | None = None,
        entity_type: str | None = None,
        actor_type: str | None = None,
        rfq_id: int | None = None,
        now: datetime | None = None,
    ) -> str:
        """The whole filtered log as CSV, oldest first.

        Oldest first, unlike the page: a printed or filed audit trail is read as a
        narrative from the beginning. The response is capped at
        :data:`MAX_EXPORT_ROWS` and the last line says so when it truncates — a
        silently short audit export is worse than a labelled one.
        """

        clauses = AuditService._filters(
            user_id,
            action=action,
            entity_type=entity_type,
            actor_type=actor_type,
            rfq_id=rfq_id,
        )

        total = int(
            db.scalar(select(func.count(AuditEntry.id)).where(*clauses)) or 0
        )

        stmt = (
            select(AuditEntry)
            .where(*clauses)
            .order_by(AuditEntry.created_at.asc(), AuditEntry.id.asc())
            .limit(MAX_EXPORT_ROWS)
        )

        entries = list(db.scalars(stmt).all())

        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")

        # A context block, for the same reason the comparison export has one: the
        # file gets emailed around and has to explain itself out of context.
        writer.writerow(["Supplier Quote Autopilot — audit log export"])
        writer.writerow(["Workspace", buyer_label])
        writer.writerow(["Exported", (now or utcnow()).isoformat()])
        writer.writerow(["Entries", total])
        writer.writerow(
            [
                "Filters",
                ", ".join(
                    f"{name}={value}"
                    for name, value in (
                        ("action", action or "all"),
                        ("entity_type", entity_type or "all"),
                        ("actor_type", actor_type or "all"),
                        ("rfq_id", rfq_id if rfq_id is not None else "all"),
                    )
                ),
            ]
        )
        writer.writerow([])

        writer.writerow(CSV_HEADERS)

        for entry in entries:
            writer.writerow(
                [
                    entry.created_at.isoformat() if entry.created_at else "",
                    label_for(entry.action),
                    entry.action,
                    entry.actor_label,
                    entry.actor_type,
                    entry.rfq_number or "",
                    entry.item_name or "",
                    entry.entity_type,
                    entry.entity_id if entry.entity_id is not None else "",
                    entry.summary,
                    _detail_text(entry.detail),
                ]
            )

        if total > len(entries):
            writer.writerow([])
            writer.writerow(
                [
                    f"Truncated: showing the oldest {len(entries)} of {total} "
                    f"matching entries. Narrow the filters (or the date range) to "
                    f"export the rest."
                ]
            )

        writer.writerow([])
        writer.writerow(
            [
                "Append-only record: entries are never edited or removed "
                "individually, and each row is written at the moment the action "
                "happened.",
            ]
        )

        return buffer.getvalue()


def _detail_text(detail: dict[str, Any] | None) -> str:
    """Flatten the small detail dict into one spreadsheet cell.

    ``key=value`` pairs joined by a pipe, rather than dumping JSON: a buyer reading
    the CSV in Excel should be able to read this column without a parser, and the
    values here are short scalars by construction.

    Nested values get rendered rather than repr'd, because the two shapes that
    actually occur are both unreadable as Python literals: an edit is stored as
    ``{"changed": {"item_name": {"from": …, "to": …}}}``, which becomes
    ``changed=item_name: old -> new``, and a list becomes a comma-separated run
    rather than a bracketed one.
    """

    if not detail:
        return ""

    return " | ".join(f"{key}={_render_detail(value)}" for key, value in detail.items())


def _render_detail(value: Any) -> str:
    if isinstance(value, dict):
        if {"from", "to"} <= set(value):
            return f"{value['from']} -> {value['to']}"

        return ", ".join(
            f"{key}: {_render_detail(item)}" for key, item in value.items()
        )

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)

    return str(value)


#: Re-exported so callers can validate a filter without importing the model.
__all__ = [
    "ACTION_LABELS",
    "AuditService",
    "DEFAULT_PAGE_SIZE",
    "MAX_EXPORT_ROWS",
    "MAX_PAGE_SIZE",
]
