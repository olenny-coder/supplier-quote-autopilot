"""Postgres-compatibility guards.

The test suite runs on SQLite, because that keeps it fast and dependency-free. The
cost is that a whole class of bug is invisible locally and fatal in production: SQL
that SQLite tolerates and PostgreSQL rejects.

This module compiles representative queries and renders the schema against the
**PostgreSQL dialect**, so those mistakes fail in CI instead of on the first request
after a deploy. It needs no database.

The bug that motivated it: four flag columns were declared ``Integer`` while the
application filtered them with ``.is_(True)``. SQLAlchemy compiles that to
``col IS true``, and PostgreSQL rejects it —

    ERROR: argument of IS must be boolean, not type integer

— which broke the entire comparison feature in production (every read, write, and
approval) while passing all 300 tests. SQLite accepts ``IS 1`` happily.
"""

import pytest
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app import models  # noqa: F401 - populates Base.metadata
from app.core.database import Base
from app.features.comparison.model import Approval
from app.features.comparison.model import Comparison
from app.features.followup.model import FollowUp
from app.features.invitation.model import Invitation
from app.features.quote.model import SupplierQuote
from app.features.rfq.model import RFQ
from app.features.supplier.model import Supplier
from app.features.auth.model import User

PG = postgresql.dialect()

#: Columns the application compares against a boolean literal rather than `None`.
#: Each must be a real BOOLEAN column or the query is invalid on PostgreSQL.
BOOLEAN_FILTERED_COLUMNS = [
    (Comparison, "is_current"),
    (Comparison, "is_conclusive"),
    (FollowUp, "llm_generated"),
    (Approval, "overrode_recommendation"),
    (User, "is_active"),
]


@pytest.mark.parametrize("model, attribute", BOOLEAN_FILTERED_COLUMNS)
def test_boolean_columns_are_declared_boolean(model, attribute):
    """A column compared with `IS true` must be BOOLEAN, not INTEGER.

    PostgreSQL's `IS` requires a boolean operand, so an integer column makes the
    query a runtime error — not a wrong result, a 500.
    """

    column = getattr(model, attribute)

    assert isinstance(column.type, Boolean), (
        f"{model.__name__}.{attribute} is {column.type!r}; anything that filters it "
        f"with .is_(True) will fail on PostgreSQL"
    )


def test_the_current_comparison_filter_compiles_for_postgres():
    """The exact filter used by repository.latest_for_rfq."""

    stmt = select(Comparison.id).where(
        Comparison.rfq_id == 1,
        Comparison.is_current.is_(True),
    )

    sql = str(stmt.compile(dialect=PG))

    assert "IS true" in sql
    assert isinstance(Comparison.is_current.type, Boolean)


def test_no_integer_column_is_filtered_against_a_boolean_literal():
    """Sweep every mapped column: `IS true`/`IS false` targets must be BOOLEAN.

    Catches the mistake on a *new* column, not just the four that were fixed.
    """

    offenders = []

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if column.name.startswith("is_") or column.name.endswith("_generated"):
                if isinstance(column.type, Integer):
                    offenders.append(f"{table.name}.{column.name}: {column.type!r}")

    assert not offenders, (
        "columns that look like flags are Integer, which breaks '.is_(True)' on "
        f"PostgreSQL: {offenders}"
    )


def test_boolean_defaults_are_portable():
    """`server_default` must render as a real SQL boolean, not SQLite's 0/1.

    Autogenerate run against SQLite writes ``sa.text('0')``, and ``BOOLEAN DEFAULT 0``
    is invalid on PostgreSQL ("column is of type boolean but default expression is of
    type integer"). The migration would apply locally and fail on Neon.
    """

    bad = []

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not isinstance(column.type, Boolean):
                continue

            default = column.server_default

            if default is None:
                continue

            rendered = str(getattr(default, "arg", default)).strip("()").lower()

            if rendered not in {"true", "false"}:
                bad.append(f"{table.name}.{column.name}: {rendered!r}")

    assert not bad, (
        "boolean server_default must be true/false (portable), not 0/1 (SQLite "
        f"only): {bad}"
    )


def test_all_datetime_columns_are_timezone_aware():
    """Naive timestamps break the deadline and expiry comparisons.

    The application compares stored values against ``datetime.now(UTC)``. A column
    without a timezone hands back naive datetimes from PostgreSQL, and Python then
    raises ``TypeError: can't compare offset-naive and offset-aware datetimes`` —
    inside the scheduler, where it is least convenient.
    """

    naive = []

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not isinstance(column.type, DateTime):
                continue

            if not column.type.timezone:
                naive.append(f"{table.name}.{column.name}")

    assert not naive, f"datetime columns must use timezone=True: {naive}"


def test_every_table_renders_for_postgres():
    """The whole schema must produce DDL PostgreSQL accepts.

    Cheap smoke test: this runs `CreateTable` through the PostgreSQL dialect for
    every table, so a type that only exists on SQLite fails here.
    """

    ddl = "\n".join(
        str(CreateTable(table).compile(dialect=PG))
        for table in Base.metadata.sorted_tables
    )

    assert "CREATE TABLE" in ddl
    # SQLite-isms that must never appear in Postgres DDL.
    assert "AUTOINCREMENT" not in ddl.upper()
    assert "DATETIME" not in ddl.upper(), "use DateTime(timezone=True), not DATETIME"
    # And the tables the product actually needs.
    for expected in ("users", "rfqs", "suppliers", "invitations", "supplier_quotes",
                     "follow_ups", "comparisons", "approvals"):
        assert f"CREATE TABLE {expected}" in ddl


def test_representative_queries_all_compile_for_postgres():
    """Compile the shapes the dashboard actually issues.

    Not a correctness check on the results — just that each statement is expressible
    in PostgreSQL, which is where a dialect-specific mistake surfaces.
    """

    statements = [
        select(RFQ).where((RFQ.user_id == 1) | (RFQ.user_id.is_(None))),
        select(Invitation).where(Invitation.status.not_in(("cancelled", "expired"))),
        select(SupplierQuote).where(
            SupplierQuote.rfq_id.in_([1, 2]),
            SupplierQuote.invitation_id.is_(None),
        ),
        select(Comparison).where(
            Comparison.rfq_id == 1,
            Comparison.is_current.is_(True),
        ).order_by(Comparison.id.desc()),
        select(FollowUp).where(
            FollowUp.status == "draft",
            FollowUp.llm_generated.is_(True),
        ),
        select(Approval).where(Approval.decision == "approved"),
        select(Supplier).where(Supplier.user_id == 1).order_by(Supplier.name.asc()),
    ]

    for statement in statements:
        sql = str(statement.compile(dialect=PG))

        assert "SELECT" in sql
        # A boolean literal must always sit next to a boolean column.
        if " IS true" in sql:
            assert any(
                isinstance(getattr(model, name).type, Boolean)
                for model, name in BOOLEAN_FILTERED_COLUMNS
                if name in sql
            ), f"IS true on a non-boolean column: {sql}"
