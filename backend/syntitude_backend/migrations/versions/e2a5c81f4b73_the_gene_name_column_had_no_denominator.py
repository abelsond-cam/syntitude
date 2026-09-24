"""the gene name column had no denominator

The cross-tab's symbol column says a family's **modal** gene name and how many **distinct** names it
holds, and neither can say how many of its genes were named at all. A family of 9 genes of which 2
carry `rfbX` reports `distinct_real_symbol_count = 1` — one distinct name — which the card draws
with no marker, and a reader reads as nine genes agreeing. Measured on kp locus 3992 (97 genes, 7
named, called `mviN` on a vote of 5 to 2), whose card said exactly that to its owner.

`pfam_annotated_member_count`, one column to its right, has carried this denominator since the first
schema for the same reason — *missing evidence is not different evidence*. This is that column for
the one beside it.

⚠ **NULLABLE, with no server default.** A default would write `0` into every existing row, and `0`
here means *the family's genes were looked at and none was named* — a measured zero. NULL means the
row predates the column. The catalogue re-ingest that lands with this migration rewrites every row,
so no NULL survives it in a loaded database.

Revision ID: e2a5c81f4b73
Revises: b41f7c9e2a08
Create Date: 2026-09-24 10:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'e2a5c81f4b73'
down_revision: str | None = 'b41f7c9e2a08'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'locus_uniref_family_crosstab',
        sa.Column('named_member_count', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('locus_uniref_family_crosstab', 'named_member_count')
