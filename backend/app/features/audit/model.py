"""The workspace audit log — an append-only record of what actually happened.

Why this table exists next to a database full of domain tables
--------------------------------------------------------------
Every other table answers "what is the current state?". None of them answers
"who changed it, and when?" — and for a procurement decision that is the question
that gets asked afterwards: when was this RFQ issued, when did the supplier
actually submit (as opposed to when the row was last written), who approved the
award, was the recommended supplier overridden, was the supplier chased, and how
many times. Those facts are scattered across ``rfqs``, ``invitations``, ``quotes``,
``comparisons``, ``approvals`` and ``follow_ups``, and each of those rows is
overwritten as the state moves on: a resubmitted quote replaces the first one, and
the ``invitations`` row keeps only the latest status.

So this is a log, not a state table. One row per thing that happened, written at
the moment it happened, never updated afterwards.

Two properties are load-bearing and both are enforced rather than promised:

* **Append-only.** A SQLAlchemy ``before_update`` listener raises, so no code path
  — present or future, accidental or deliberate — can rewrite history. There is
  also no endpoint that deletes an entry. The rows are removed only when the
  workspace itself is, through the ``User`` relationship's delete cascade, which is
  the one deletion that is supposed to take the log with it.
* **Self-contained.** ``rfq_id`` is a stored reference, **not a foreign key**, and
  the RFQ number, item name, actor label and summary are snapshotted onto the row.
  So the entry that says "RFQ-2026-8F3A21C4 was deleted" survives the RFQ it
  describes, and a log exported after the fact is still readable without joining to
  rows that no longer exist. An audit trail that goes blank when the thing it audits
  is deleted is not an audit trail.

That second point is worth spelling out, because the obvious design is wrong in two
ways at once. A foreign key with ``ON DELETE SET NULL`` would *rewrite a column of
this row* when an unrelated row is deleted — mutation of history, which is the one
thing the table promises not to do — and it would behave differently on the two
engines: PostgreSQL clears the reference while SQLite, which only enforces foreign
keys when they are switched on (they are not here), leaves it pointing at an id that
no longer exists. A plain indexed integer behaves identically everywhere and cannot
be touched by another table's lifecycle. The cost is that nothing at the database
level stops a dangling ``rfq_id``; the snapshot columns are what make that harmless,
and they are on every entry precisely for this reason.

What is deliberately *not* here: request/response bodies, attachments, prices, or
anything else that would turn a change log into a second copy of the data. The
``detail`` JSON column holds small, specific facts — the fields that changed, the
award decision, the number of suppliers imported — never whole objects.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin

#: Every action the log can hold, as ``code -> label``. Ordered by the workflow it
#: describes rather than alphabetically, so the filter dropdown on the audit page
#: reads as the sequence a buyer would actually follow. A code that is not in here
#: still records and still exports; it just falls back to its raw code, because a
#: missing label must never be a reason to drop the entry.
ACTION_LABELS: dict[str, str] = {
    "rfq.created": "RFQ created",
    "rfq.updated": "RFQ changed",
    "rfq.closed": "RFQ closed",
    "rfq.deleted": "RFQ deleted",
    "supplier.created": "Supplier added",
    "supplier.updated": "Supplier changed",
    "supplier.deleted": "Supplier removed",
    "supplier.imported": "Suppliers imported from CSV",
    "invitation.created": "Supplier invited",
    "invitation.sent": "Invitation emailed",
    "invitation.resent": "Invitation resent",
    "invitation.withdrawn": "Invitation withdrawn",
    "invitation.deleted": "Invitation deleted",
    "invitation.expired": "Invitation expired",
    "quote.submitted": "Quote submitted by supplier",
    "quote.amended": "Quote amended by supplier",
    "quote.recorded": "Quote entered by you",
    "quote.updated": "Quote changed",
    "quote.deleted": "Quote deleted",
    "comparison.run": "Comparison scored",
    "award.approved": "Award approved",
    "award.rejected": "Award rejected",
    "award.deferred": "Award deferred",
    "followup.drafted": "Follow-up drafted",
    "followup.approved": "Follow-up approved",
    "followup.rejected": "Follow-up discarded",
    "followup.sent": "Follow-up sent",
    "followup.failed": "Follow-up failed to send",
    "followup.manual": "Follow-up sent by you",
}

#: Who caused the action. A buyer does not share a workspace with anyone else in
#: this MVP, so "buyer" always means the workspace owner; "supplier" means the
#: unauthenticated holder of an invitation link, and "system" means the scheduler
#: acting on the buyer's configured policy.
ACTOR_TYPES = ("buyer", "supplier", "system")

#: What the entry is about. Kept separate from ``action`` so "everything that
#: happened to this invitation" is a filter, and "everything the scheduler did" is
#: a different one that crosses entity types.
ENTITY_TYPES = (
    "rfq",
    "supplier",
    "invitation",
    "quote",
    "comparison",
    "approval",
    "followup",
    "user",
)


def label_for(action: str) -> str:
    """The buyer-facing label for an action code."""

    return ACTION_LABELS.get(action, action)


class AuditEntry(TimestampMixin, Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    #: The tenant this entry belongs to. Deleting the account deletes its log —
    #: there is no account-deletion feature today, but the cascade is the honest
    #: declaration of ownership.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The RFQ this concerns, when there is one. Stored as a plain integer rather
    #: than a foreign key — see the module docstring: a constraint here would let
    #: an unrelated delete mutate this row, and the two engines disagree about it.
    rfq_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    #: Snapshots, so an export stays readable after the RFQ is gone. See the module
    #: docstring — this is the difference between a log and a join.
    rfq_number: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    item_name: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    actor_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="buyer",
        server_default="buyer",
        index=True,
    )

    #: Who, in words, at the time — the buyer's company, the supplier's name, or
    #: "Scheduler". Snapshotted rather than joined so renaming a supplier does not
    #: silently rewrite who did something last year.
    #:
    #: Python-side default only, with no ``server_default``: the service always
    #: resolves a label before inserting, and an empty-string server default is a
    #: construct Alembic compares inconsistently across engines, which made
    #: ``alembic check`` report a phantom migration.
    actor_label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )

    #: One sentence a buyer can read without context. Written by the caller, which
    #: is the only place that knows what the action meant.
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    #: Small, specific facts: the fields that changed, the decision, the import
    #: counts. Never a copy of the record itself.
    detail: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    owner = relationship("User", back_populates="audit_entries")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<AuditEntry id={self.id} action={self.action!r} "
            f"actor={self.actor_type!r}>"
        )


@event.listens_for(AuditEntry, "before_update")
def _refuse_update(mapper, connection, target) -> None:  # noqa: ARG001
    """History is not editable. See the module docstring.

    A guard rather than a convention, because the failure mode is silent: an
    ``UPDATE`` that rewrites an actor or a timestamp would leave a log that still
    looks complete and is wrong. Nothing in the codebase updates these rows, and
    this listener is what keeps that true.
    """

    raise RuntimeError(
        "Audit entries are append-only and cannot be updated. Write a new entry "
        "instead — see app/features/audit/model.py."
    )
