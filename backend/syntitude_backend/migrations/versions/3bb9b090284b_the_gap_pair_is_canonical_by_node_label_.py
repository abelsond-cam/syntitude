"""the gap pair is canonical by node_label, and EC is a set

Two corrections the initial schema got wrong, both found by measurement rather than by review.

1. `intergenic_gap` was keyed `(low, high)` with `CHECK (low <= high)` on the surrogate locus ids.
   The canonical order is by `node_label`, which is TEXT: `intergenic.gene_adjacencies` sorts the
   pair with `left <= right` on the node ids. A numeric CHECK on ids imposes a SECOND, different
   canonicalisation that is perfectly satisfiable — so the schema would look correct while holding
   a third of the pairs the other way round. Renamed to `a`/`b`, and the ordering is asserted at
   ingest against the labels.

   Measured on the two published catalogues: ecoli 7,379 of 22,838 gaps (32.3 %) and kp 6,108 of
   20,544 (29.7 %) have `a > b` by payload index while 100 % are label-sorted.

2. `gene_functional_annotation.ec_number` was `String(32)`. Bakta's `ec` is a comma-joined
   sorted-unique SET built exactly like `go` — measured over 40 probe genomes, 8,660 of 70,477
   non-null values (12.3 %) carry more than one term, up to 4 terms and **39 characters**. The
   column would have raised on 12 % of its rows, or truncated them silently. Now an array, like
   `gene_ontology_terms`, which also makes the reverse query indexable.

⭐ Both renames are REAL renames, not the drop-and-add autogenerate proposed. There is no data in
any deployment yet, so the difference is invisible today — and at 80,000 genomes `gene_functional_
annotation` is ~406 M rows, where dropping a column to add it back is a table rewrite and a data
loss. The habit is the point; the `USING string_to_array` cast is what a rename of a retyped column
actually costs.

Revision ID: 3bb9b090284b
Revises: 167f47ef6e68
Create Date: 2026-09-04 19:21:14.925548
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

#: ⛔ Every explicit constraint/index name here is wrapped in `op.f()`. Without it Alembic runs the
#: name through `CONSTRAINT_NAMING_CONVENTION` a SECOND time, and `ck_%(table_name)s__%(constraint_
#: name)s` turns `ck_intergenic_gap__flanking_pair_is_sorted` into
#: `ck_intergenic_gap__ck_intergenic_gap__flanking_pair_is_sorted` — a name no database holds.
#: `op.f` marks a string as already-final, which is why autogenerate emits it everywhere.

revision: str = '3bb9b090284b'
down_revision: str | None = '167f47ef6e68'
branch_labels = None
depends_on = None

_OLD_UNIQUE = op.f('uq_intergenic_gap__pangenome_id_flanking_locus_id_low_f_2e90')
_NEW_UNIQUE = op.f('uq_intergenic_gap__pangenome_id_flanking_locus_id_a_flanking_locus_id_b')


def upgrade() -> None:
    # ---- (2) EC becomes a set, PRESERVING the values already stored --------------------------
    # `string_to_array(NULL, ',')` is NULL, so a not-annotated gene stays not-annotated rather
    # than becoming `{}` — which under this schema's own rule is a different claim.
    op.execute(
        "ALTER TABLE gene_functional_annotation "
        "ALTER COLUMN ec_number TYPE varchar[] USING string_to_array(ec_number, ',')"
    )
    op.alter_column('gene_functional_annotation', 'ec_number', new_column_name='ec_numbers')

    # ---- (1) the gap pair is renamed, and its constraints follow ------------------------------
    # Constraints and indexes are dropped FIRST: Postgres renames them automatically with the
    # column, to names that no longer match the convention, and a later migration referring to the
    # convention's name would then fail on a database that had taken this path.
    op.drop_constraint(_OLD_UNIQUE, 'intergenic_gap', type_='unique')
    op.drop_constraint(op.f('ck_intergenic_gap__flanking_pair_is_sorted'), 'intergenic_gap', type_='check')
    op.drop_index(op.f('ix_intergenic_gap__flanking_locus_id_low'), table_name='intergenic_gap')
    op.drop_index(op.f('ix_intergenic_gap__flanking_locus_id_high'), table_name='intergenic_gap')
    op.drop_constraint(op.f('fk_intergenic_gap__flanking_locus_id_low__locus'), 'intergenic_gap', type_='foreignkey')
    op.drop_constraint(op.f('fk_intergenic_gap__flanking_locus_id_high__locus'), 'intergenic_gap', type_='foreignkey')

    op.alter_column('intergenic_gap', 'flanking_locus_id_low', new_column_name='flanking_locus_id_a')
    op.alter_column('intergenic_gap', 'flanking_locus_id_high', new_column_name='flanking_locus_id_b')

    op.create_index(op.f('ix_intergenic_gap__flanking_locus_id_a'), 'intergenic_gap', ['flanking_locus_id_a'])
    op.create_index(op.f('ix_intergenic_gap__flanking_locus_id_b'), 'intergenic_gap', ['flanking_locus_id_b'])
    op.create_unique_constraint(
        _NEW_UNIQUE, 'intergenic_gap', ['pangenome_id', 'flanking_locus_id_a', 'flanking_locus_id_b']
    )
    op.create_foreign_key(
        op.f('fk_intergenic_gap__flanking_locus_id_a__locus'), 'intergenic_gap', 'locus',
        ['flanking_locus_id_a'], ['locus_id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        op.f('fk_intergenic_gap__flanking_locus_id_b__locus'), 'intergenic_gap', 'locus',
        ['flanking_locus_id_b'], ['locus_id'], ondelete='CASCADE',
    )
    op.create_check_constraint(
        op.f('ck_intergenic_gap__flanking_pair_is_two_distinct_loci'), 'intergenic_gap',
        'flanking_locus_id_a <> flanking_locus_id_b',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_intergenic_gap__flanking_pair_is_two_distinct_loci'), 'intergenic_gap', type_='check')
    op.drop_constraint(op.f('fk_intergenic_gap__flanking_locus_id_b__locus'), 'intergenic_gap', type_='foreignkey')
    op.drop_constraint(op.f('fk_intergenic_gap__flanking_locus_id_a__locus'), 'intergenic_gap', type_='foreignkey')
    op.drop_constraint(_NEW_UNIQUE, 'intergenic_gap', type_='unique')
    op.drop_index(op.f('ix_intergenic_gap__flanking_locus_id_b'), table_name='intergenic_gap')
    op.drop_index(op.f('ix_intergenic_gap__flanking_locus_id_a'), table_name='intergenic_gap')

    op.alter_column('intergenic_gap', 'flanking_locus_id_a', new_column_name='flanking_locus_id_low')
    op.alter_column('intergenic_gap', 'flanking_locus_id_b', new_column_name='flanking_locus_id_high')

    op.create_index(op.f('ix_intergenic_gap__flanking_locus_id_low'), 'intergenic_gap', ['flanking_locus_id_low'])
    op.create_index(op.f('ix_intergenic_gap__flanking_locus_id_high'), 'intergenic_gap', ['flanking_locus_id_high'])
    op.create_unique_constraint(
        _OLD_UNIQUE, 'intergenic_gap', ['pangenome_id', 'flanking_locus_id_low', 'flanking_locus_id_high']
    )
    op.create_foreign_key(
        op.f('fk_intergenic_gap__flanking_locus_id_low__locus'), 'intergenic_gap', 'locus',
        ['flanking_locus_id_low'], ['locus_id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        op.f('fk_intergenic_gap__flanking_locus_id_high__locus'), 'intergenic_gap', 'locus',
        ['flanking_locus_id_high'], ['locus_id'], ondelete='CASCADE',
    )
    # ⚠ The CHECK this restores is the one this migration exists to remove, and a database holding
    # correctly label-ordered pairs will FAIL to satisfy it on ~32 % of rows. That is the honest
    # outcome: the old schema could not represent the data, and a downgrade that silently reordered
    # the pairs to fit would corrupt them.
    op.create_check_constraint(
        op.f('ck_intergenic_gap__flanking_pair_is_sorted'), 'intergenic_gap',
        'flanking_locus_id_low <= flanking_locus_id_high',
    )

    # ⚠ Lossy by construction: a multi-term EC set is re-joined with commas, which is what the old
    # column held, and any value over 32 characters then violates the length it is cast back to.
    op.alter_column('gene_functional_annotation', 'ec_numbers', new_column_name='ec_number')
    op.execute(
        "ALTER TABLE gene_functional_annotation "
        "ALTER COLUMN ec_number TYPE varchar(32) USING array_to_string(ec_number, ',')"
    )
    op.alter_column('gene_functional_annotation', 'ec_number', type_=sa.String(length=32))
