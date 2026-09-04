"""Alembic environment.

Two things this file decides, and both are deliberate:

⛔ **The database URL comes from the environment, never from `alembic.ini`.** That file is
committed; a URL carries credentials.

⛔ **`target_metadata` is imported via `syntitude_backend.models`**, which imports every model
module. A model not reachable from there is invisible to autogenerate, and the migration it writes
silently omits that table — surfacing much later as a missing relation on one endpoint.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import syntitude_backend.models  # noqa: F401  (registers every table on the metadata)
from syntitude_backend.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("SYNTITUDE_DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "SYNTITUDE_DATABASE_URL is not set. Alembic refuses to guess a database it is about to "
        "alter — see syntitude_backend/migrations/env.py."
    )
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live connection — for review, or for a DBA to apply."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # ⚠ Without this, a column whose TYPE changed produces an empty migration and the
            # divergence is invisible until a value fails to fit.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
