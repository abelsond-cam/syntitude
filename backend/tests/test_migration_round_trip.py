"""The migration must build the models exactly, and must be reversible AND re-appliable.

⛔ Three properties, and each was broken on the first attempt — none of which reading the generated
file would have shown:

1. Autogenerate **omitted the circular foreign key** `pathogen_species.published_pangenome_id →
   pangenome`. It can only be created by ALTER after both tables exist, and Alembic dropped that
   edge on the floor. The column is the publish-flip pointer, so without the constraint nothing
   stops it naming a pangenome that does not exist.
2. `downgrade` dropped the tables but **not the eleven ENUM types**, so `downgrade` → `upgrade`
   died on `CREATE TYPE ... already exists`. A migration that cannot be re-applied is not
   reversible.
3. Nothing checks that the migration still matches the models unless something asks — so
   `test_no_drift` does.
"""

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC = BACKEND_ROOT.parent / ".venv/bin/alembic"
PROBE_URL = os.environ.get(
    "SYNTITUDE_MIGRATION_DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('USER', 'postgres')}@localhost:5432/syntitude_migrate_probe",
)

pytestmark = pytest.mark.skipif(not ALEMBIC.exists(), reason="alembic not installed in the venv")


def _alembic(*args):
    return subprocess.run(
        [str(ALEMBIC), *args],
        cwd=BACKEND_ROOT,
        env={**os.environ, "SYNTITUDE_DATABASE_URL": PROBE_URL},
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def probe_engine():
    engine = create_engine(PROBE_URL, future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"migration probe database unavailable: {error}")
    _alembic("downgrade", "base")
    return engine


def _count(engine, sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).scalar_one()


TABLES = "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
ENUM_TYPES = (
    "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
    "WHERE n.nspname='public' AND t.typtype='e'"
)


def test_upgrade_then_downgrade_then_upgrade_again(probe_engine):
    assert _alembic("upgrade", "head").returncode == 0
    after_first = _count(probe_engine, TABLES)
    assert after_first > 20, f"only {after_first} tables after upgrade"

    assert _alembic("downgrade", "base").returncode == 0
    # alembic_version survives a downgrade to base; everything else must not.
    assert _count(probe_engine, TABLES) == 1
    # ⛔ The defect this test exists for: eleven enum types survived here on the first attempt.
    assert _count(probe_engine, ENUM_TYPES) == 0, "downgrade left orphaned enum types"

    second = _alembic("upgrade", "head")
    assert second.returncode == 0, f"re-upgrade failed:\n{second.stderr[-1500:]}"
    assert _count(probe_engine, TABLES) == after_first


def test_the_circular_publish_pointer_foreign_key_exists(probe_engine):
    # ⛔ Autogenerate omitted this. It is the publish-flip pointer.
    _alembic("upgrade", "head")
    with probe_engine.connect() as connection:
        definition = connection.execute(
            text(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = 'pathogen_species' AND c.contype = 'f'"
            )
        ).scalars().all()
    assert any("pangenome" in d and "published_pangenome_id" in d for d in definition), (
        f"the publish-flip pointer has no referential integrity: {definition}"
    )
    # DEFERRABLE is required: the flip and the partition attach share one transaction.
    assert any("DEFERRABLE" in d for d in definition)


def test_the_migration_still_matches_the_models(probe_engine):
    """Autogenerate against the migrated database must find NOTHING to do."""
    _alembic("upgrade", "head")
    result = _alembic("revision", "--autogenerate", "-m", "drift check")
    generated = None
    try:
        assert result.returncode == 0, result.stderr[-1000:]
        for line in result.stdout.splitlines():
            if line.startswith("Generating "):
                generated = Path(line.split("Generating ", 1)[1].split(" ...")[0].strip())
        assert generated and generated.exists(), f"no migration generated:\n{result.stdout}"
        body = generated.read_text()
        upgrade_body = body.split("def upgrade() -> None:")[1].split("def downgrade")[0]
        operations = [
            line.strip()
            for line in upgrade_body.splitlines()
            if line.strip().startswith("op.") or line.strip().startswith("sa.")
        ]
        assert not operations, (
            "the migration has drifted from the models — autogenerate wants:\n  "
            + "\n  ".join(operations)
        )
    finally:
        if generated and generated.exists():
            generated.unlink()
