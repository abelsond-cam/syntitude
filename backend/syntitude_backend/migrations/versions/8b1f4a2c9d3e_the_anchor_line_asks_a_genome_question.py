"""the anchor line asks a genome question, and only a gene answer was stored

⛔ **What this adds and why it cannot be derived.** When an anchored genome carries no arrangement
at a locus the page has two sentences, and they are different claims (`app.js:1762-1771`):

  * *"… has no gene at this locus — the most common neighbourhood is shown instead"*
  * *"… has no recorded neighbourhood at this locus — the most common is shown instead"*

Only one is ever true, and which one is settled by whether **every genome present reaches an
arrangement**. `coords` is an inner join in the export, so a gene with no coordinates never reaches
a window: measured on the published payloads, **6.26 % of ecoli loci and 3.69 % of kp loci** have at
least one genome counted present and sitting in no arrangement (worst case 64 of 100). At those loci
the first sentence is simply false.

⛔ `arrangement_member_gene_count` cannot answer it. That is a **gene** count, and a genome at ρ > 1
has two genes at one locus — losing one gene's window leaves the genome fully present in an
arrangement while the gene remainder is non-zero. `sum(member_genome_count)` is wrong the other way,
double-counting exactly those genomes, so a locus where every genome is accounted for would report
more genomes than the locus has. The only correct quantity is the **union**, which is what this
stores.

Revision ID: 8b1f4a2c9d3e
Revises: 5c7d27bace6e
Create Date: 2026-09-05 16:52:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '8b1f4a2c9d3e'
down_revision: str | None = '5c7d27bace6e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ⚠ Three steps, as for `arrangement_member_gene_count`: a NOT NULL column with no default fails
    # on a populated table, and a `server_default` of 0 would leave every existing locus claiming
    # that NO genome reaches an arrangement — a wrong value that reads as a measured one, and one
    # that would make the anchor line say "has no recorded neighbourhood" everywhere.
    op.add_column('locus', sa.Column('arrangement_member_genome_count', sa.Integer(), nullable=True))
    # ⛔ `count(DISTINCT g)` over the UNNESTED arrays, never `sum(a.member_genome_count)`.
    op.execute(
        """
        UPDATE locus
           SET arrangement_member_genome_count = coalesce(totals.member_genomes, 0)
          FROM (SELECT l.locus_id,
                       (SELECT count(DISTINCT g)
                          FROM locus_arrangement a,
                               unnest(a.member_genome_ids) AS g
                         WHERE a.locus_id = l.locus_id) AS member_genomes
                  FROM locus l) AS totals
         WHERE totals.locus_id = locus.locus_id
        """
    )
    op.alter_column('locus', 'arrangement_member_genome_count', nullable=False)


def downgrade() -> None:
    op.drop_column('locus', 'arrangement_member_genome_count')
