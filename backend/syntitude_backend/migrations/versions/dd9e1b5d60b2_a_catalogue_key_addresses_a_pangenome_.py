"""a catalogue key addresses a pangenome, and the species pointer is a default

⭐ **What this enables:** a species holding more than one catalogue at a time — nuna4 beside nuna5,
or a sensitive model beside a less-sensitive one — with the *display* choosing which to show
(David, 2026-09-25). The storage layer already allowed it: every catalogue table is scoped by
`pangenome_id` and every uniqueness constraint is already `(pangenome_id, …)`. What was missing was
a way to **address** one, and a pointer that admitted it was only a default.

⛔ **HAND-WRITTEN, and autogenerate must not be trusted here — it proposed two destructive things.**
1. It emitted the rename as `add_column('default_pangenome_id')` + `drop_column(
   'published_pangenome_id')`. Alembic cannot detect a rename, and that pair silently **discards
   every species' published pointer** — the live site's entire "what do we serve" state, in a
   migration that applies cleanly. It is `alter_column(new_column_name=…)` below.
2. It emitted `catalogue_key` as `NOT NULL` with no default, which cannot apply to a table that
   already has rows. Added nullable, backfilled, *then* constrained.

⚠ Autogenerate also wanted to churn two `projected_*` check constraints. **Those are deliberately
NOT in this migration.** They are a separate pre-existing drift with a different cause: the asked-for
names are 69 and 67 characters, Postgres truncates at 63 and appends a hash, and Alembic compares
against the name it asked for — so the table reports as drifted from its own migration forever. That
is a rename in the *model*, owned by the locus-projection work, and folding it in here would hide
someone else's bug inside an unrelated change.

Revision ID: dd9e1b5d60b2
Revises: 858439e8fd7c
Create Date: 2026-09-25 23:26:46.707664
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = 'dd9e1b5d60b2'
down_revision: str | None = '858439e8fd7c'
branch_labels = None
depends_on = None

#: `{species_key}-{model_key}` — the key a reader addresses a catalogue by, and the same string
#: nuna's exporter writes as `--dset`. ⛔ The separator is a HYPHEN so the keys stay prefix-free:
#: `ecoli` must not match `ecoli_nuna5`, because nuna's payload lookup globs on the key and takes
#: the newest match. No species token contains a hyphen.
_BACKFILL = """
UPDATE pangenome AS p
   SET catalogue_key = s.species_key || '-' || m.model_key
  FROM pathogen_species AS s, nuna_model AS m
 WHERE s.pathogen_species_id = p.pathogen_species_id
   AND m.nuna_model_id = p.nuna_model_id
"""

_OLD_FK = 'fk_pathogen_species__published_pangenome_id__pangenome'
_NEW_FK = 'fk_pathogen_species__default_pangenome_id__pangenome'


def upgrade() -> None:
    # ---- catalogue_key: add nullable, backfill, then constrain -------------------------------
    op.add_column('pangenome', sa.Column('catalogue_key', sa.String(length=64), nullable=True))
    op.execute(_BACKFILL)
    # ⚠ Deliberately NOT COALESCEd to a fallback. A pangenome with no `nuna_model_id` is not
    # addressable and there is no honest key to invent for it, so this raises rather than minting
    # one — a wrong catalogue key is a link that serves the wrong clustering, in silence.
    op.alter_column('pangenome', 'catalogue_key', nullable=False)
    op.create_unique_constraint(op.f('uq_pangenome__catalogue_key'), 'pangenome', ['catalogue_key'])

    # ---- the pointer is renamed, NOT replaced -------------------------------------------------
    # Postgres keeps a constraint's name when its column is renamed, so the FK would be left
    # spelling `published_` against a convention that now says `default_` — permanent drift.
    # RENAME CONSTRAINT keeps the DEFERRABLE INITIALLY DEFERRED it was created with; dropping and
    # recreating it would not, and that deferral is what lets the publish flip and the partition
    # attach share one transaction.
    op.alter_column('pathogen_species', 'published_pangenome_id', new_column_name='default_pangenome_id')
    op.execute(f'ALTER TABLE pathogen_species RENAME CONSTRAINT "{_OLD_FK}" TO "{_NEW_FK}"')


def downgrade() -> None:
    op.execute(f'ALTER TABLE pathogen_species RENAME CONSTRAINT "{_NEW_FK}" TO "{_OLD_FK}"')
    op.alter_column('pathogen_species', 'default_pangenome_id', new_column_name='published_pangenome_id')
    op.drop_constraint(op.f('uq_pangenome__catalogue_key'), 'pangenome', type_='unique')
    op.drop_column('pangenome', 'catalogue_key')
