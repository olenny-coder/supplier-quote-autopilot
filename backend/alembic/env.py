"""Alembic environment.

Two decisions worth knowing about:

1. **The database URL comes from the application settings, not from
   ``alembic.ini``.** Migrations must target the same database the app talks to,
   and there must be exactly one place that decides which that is.

2. **Migrations use ``DATABASE_URL_DIRECT``.** On Neon the pooled endpoint
   (``-pooler`` in the hostname) runs PgBouncer in transaction mode, which
   Alembic's DDL transactions and its advisory-lock-free ``alembic_version``
   bookkeeping do not tolerate reliably. The direct string is the supported path.
   Locally ``DATABASE_URL_DIRECT`` is unset and this falls back to
   ``DATABASE_URL``, so the same command works in every environment.

Also note ``render_as_batch``: SQLite (used by the test suite and by anyone
running migrations locally without Postgres) cannot ``ALTER TABLE`` freely, so
batch mode rewrites tables instead. It is a no-op on Postgres.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy import pool

from app import models  # noqa: F401 - registers every model on Base.metadata
from app.core.config import settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

#: Applied to every migration. SQLite needs batch mode for ALTER TABLE; Postgres
#: ignores it, so one codebase serves both.
BATCH_MODE = settings.migration_database_url.startswith("sqlite")


def get_url() -> str:
    return settings.migration_database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of applying it (``alembic upgrade head --sql``)."""

    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=BATCH_MODE,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations to a live database."""

    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=BATCH_MODE,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
