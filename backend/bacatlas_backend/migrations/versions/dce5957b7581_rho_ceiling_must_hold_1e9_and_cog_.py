"""rho_ceiling must hold 1e9, and COG categories are a set

Two defects an adversarial re-read of the source mappings surfaced, both verified against Postgres
and the real parquets rather than reasoned about.

1. `nuna_model_step.rho_ceiling` was `Numeric(12, 4)` — 8 digits left of the point. **Step 2's
   ceiling is the literal `1e9`** (`nuna_pipeline.py:410` passes the string; CLAUDE.md's table says
   *"ρ OFF (ceiling 1e9)"*), which needs 10. Confirmed by asking Postgres:
   `SELECT CAST(1e9 AS numeric(12,4))` raises `numeric field overflow`. Ingesting the step 2 of
   EVERY multi-step model would have failed. Widened to `Numeric(18, 4)`.

2. `gene_functional_annotation.cog_category` was a scalar `String(16)`. Bakta writes the COG
   functional categories **concatenated** — `CP`, `DZ`, `EFG` — and measured over 40 probe genomes
   **14,812 of 129,865 non-null values (11.4 %) carry more than one letter**, up to 4. It FITS in
   the scalar, which is exactly why the error would have been silent: `WHERE cog_category = 'C'`
   then misses every gene categorised `CO`/`CP`/`CR`, and a per-category census under-counts by
   11.4 %. It is the same set-in-a-string trap `ec` and `go` are modelled around.

⭐ Both renames are real renames with data-preserving casts, not autogenerate's drop-and-add.
`regexp_split_to_array(cog_category, '')` is what turns the concatenated letters into the set they
always were.

Revision ID: dce5957b7581
Revises: a92d77dbc4c5
Create Date: 2026-09-04 20:03:58.766144
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'dce5957b7581'
down_revision: str | None = 'a92d77dbc4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ⛔ Widened, not recreated: at 80,000 genomes the sibling tables make a rewrite expensive, and
    # a widening of a numeric is a catalogue change rather than a table scan.
    op.alter_column(
        "nuna_model_step", "rho_ceiling",
        existing_type=sa.Numeric(precision=12, scale=4), type_=sa.Numeric(precision=18, scale=4),
        existing_nullable=True,
    )
    # `regexp_split_to_array(NULL, '')` is NULL, so a gene with no COG stays *not annotated* rather
    # than becoming `{}` — which under this schema's own rule is a different claim.
    op.execute(
        "ALTER TABLE gene_functional_annotation "
        "ALTER COLUMN cog_category TYPE varchar[] USING regexp_split_to_array(cog_category, '')"
    )
    op.alter_column("gene_functional_annotation", "cog_category", new_column_name="cog_categories")


def downgrade() -> None:
    # ⚠ Lossy in the same way the forward cast is faithful: the letters are re-concatenated, which
    # is what the scalar column always held.
    op.alter_column("gene_functional_annotation", "cog_categories", new_column_name="cog_category")
    op.execute(
        "ALTER TABLE gene_functional_annotation "
        "ALTER COLUMN cog_category TYPE varchar(16) USING array_to_string(cog_category, '')"
    )
    # ⚠ This restores a width that cannot hold 1e9 — the defect this migration exists to remove. A
    # database holding a step-2 row will fail here, which is the honest outcome: the old column
    # could not represent the value, and silently truncating it would corrupt the model definition.
    op.alter_column(
        "nuna_model_step", "rho_ceiling",
        existing_type=sa.Numeric(precision=18, scale=4), type_=sa.Numeric(precision=12, scale=4),
        existing_nullable=True,
    )
