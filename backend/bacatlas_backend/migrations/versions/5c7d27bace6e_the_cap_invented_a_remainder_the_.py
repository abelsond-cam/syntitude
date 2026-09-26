"""the cap invented a remainder the uncapped payload never had

⛔ **What this fixes.** `members_without_a_neighbourhood` was `member_gene_count − Σ(listed
arrangements)`. On the published page that subtraction is right, because that payload is
**uncapped** — every arrangement ships, so the difference really is *"member genes with no recorded
neighbourhood: no coordinates for the gene, so no window"*. The API caps the listed arrangements at
8, so the same subtraction quietly swept in every member sitting in an arrangement past the cap and
reported it as missing coordinates.

Measured on the loaded catalogues before the fix: **15,912 E. coli member genes over 2,340 loci**
and **10,437 kp member genes over 1,548 loci** would have been described that way.

Storing the total (rather than aggregating per request) keeps the locus view at one statement per
table, which its cost oracle asserts.

Revision ID: 5c7d27bace6e
Revises: 4447f227b6e9
Create Date: 2026-09-05 14:29:58.642301
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '5c7d27bace6e'
down_revision: str | None = '4447f227b6e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ⚠ Three steps, not one. Adding a NOT NULL column with no default to a table holding 33,201
    # rows fails outright, and adding one with a server_default of 0 would leave every existing
    # locus claiming that no member sits in any arrangement — a wrong value that reads as measured.
    op.add_column('locus', sa.Column('arrangement_member_gene_count', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE locus
           SET arrangement_member_gene_count = coalesce(totals.member_genes, 0)
          FROM (SELECT l.locus_id,
                       (SELECT sum(a.member_gene_count)
                          FROM locus_arrangement a
                         WHERE a.locus_id = l.locus_id) AS member_genes
                  FROM locus l) AS totals
         WHERE totals.locus_id = locus.locus_id
        """
    )
    op.alter_column('locus', 'arrangement_member_gene_count', nullable=False)


def downgrade() -> None:
    op.drop_column('locus', 'arrangement_member_gene_count')
