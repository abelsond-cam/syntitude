"""Engine, session and the declarative base — plus the constraint naming convention.

⛔ The ``naming_convention`` is the load-bearing part of this module, and it has to be here
before the first migration rather than after. Without it Postgres invents constraint names,
Alembic autogenerate produces a different name on each developer's machine, and a migration
that drops a constraint by name works for whoever wrote it and fails for everyone else. With
it, ``ck_pangenome__exclusivity_token_agrees`` is the same string everywhere, forever.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from syntitude_backend.configuration import Configuration

#: `%(column_0_N_name)s` truncates rather than overflowing Postgres' 63-byte identifier limit,
#: which is what silently collides two constraint names on wide tables.
CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s__%(column_0_N_name)s",
    "uq": "uq_%(table_name)s__%(column_0_N_name)s",
    "ck": "ck_%(table_name)s__%(constraint_name)s",
    "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base carrying the shared metadata and its naming convention."""

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTION)


class Database:
    """One engine and one session factory per application, built from a `Configuration`."""

    def __init__(self, configuration: Configuration) -> None:
        self.engine = create_engine(
            configuration.database_url,
            echo=configuration.sql_echo,
            future=True,
            # Read-only service: connections are long-lived and idle-heavy behind gunicorn,
            # so recycle before a proxy or Postgres decides to drop one under us.
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A session scoped to one request or one unit of work.

        There is no ``commit`` here on purpose: this service never writes on a request path
        (ingest opens its own sessions), so a request that somehow dirtied the session should
        roll back rather than quietly persist.
        """
        session = self.session_factory()
        try:
            yield session
            session.rollback()
        finally:
            session.close()
