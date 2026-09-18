"""every genome's locus count is stored because the picker cannot aggregate 412 M rows per keystroke

⭐ `GET /species/{key}/genomes` replaces `meta.genomes` + `anchorSearch` + `GENOME_N`. The page
derived `GENOME_N` on first opening of the anchor box, from a membership index it already held in
memory; a server's equivalent is an aggregation over `gene_locus_membership`, which is ~412 M rows
per pangenome at the 80,000-genome design target. So one row per (pangenome, collection genome),
written by the pangenome layer.

⛔ **Two counts, because they are different facts.** `locus_count` is distinct loci where the genome
has a gene; `arrangement_locus_count` is distinct loci where it sits in some arrangement — exactly
`app.js::genomeCounts`. They differ wherever a gene reached no ±5 window, and on the probe
catalogues that is every genome.

⛔ **`count(DISTINCT locus_id)`, never `count(*)`.** A genome at ρ > 1 has two genes at one locus
and can sit in two of its arrangements; counting rows returns the genome's gene total instead, a
plausible number a little too large (ecoli: 489,146 gene rows against 487,796 present loci; 486,717
arrangement memberships against 485,559 arranged loci).

⚠ **The backfill is this migration's own frozen copy of the ingest statement**
(`ingest_genome_locus_counts.GENOME_LOCUS_COUNT_SELECT`), run for every pangenome that has a
catalogue. A migration must not import code that will keep changing after it; the test
`test_the_stored_counts_are_the_ingest_definition_recomputed` is what holds the two together.

Revision ID: d79a80412308
Revises: d7c2b6e4a915
Create Date: 2026-09-18 10:25:48.986222
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'd79a80412308'
down_revision: str | None = 'd7c2b6e4a915'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pangenome_genome_locus_count',
        # ⚠ BigInteger, because `pangenome.pangenome_id` is — an Integer FK onto a BigInteger PK
        # applies cleanly and then drifts from the models forever.
        sa.Column('pangenome_id', sa.BigInteger(), nullable=False),
        sa.Column('genome_id', sa.Integer(), nullable=False),
        sa.Column('locus_count', sa.Integer(), nullable=False),
        sa.Column('arrangement_locus_count', sa.Integer(), nullable=False),
        # ⛔ A genome cannot sit in an arrangement where it has no gene.
        sa.CheckConstraint(
            'arrangement_locus_count >= 0 AND arrangement_locus_count <= locus_count',
            name=op.f('ck_pangenome_genome_locus_count__arranged_within_present'),
        ),
        sa.ForeignKeyConstraint(
            ['genome_id'],
            ['genome.genome_id'],
            name=op.f('fk_pangenome_genome_locus_count__genome_id__genome'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['pangenome_id'],
            ['pangenome.pangenome_id'],
            name=op.f('fk_pangenome_genome_locus_count__pangenome_id__pangenome'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('pangenome_id', 'genome_id', name=op.f('pk_pangenome_genome_locus_count')),
    )
    op.create_index(
        'ix_pangenome_genome_locus_count__genome_id',
        'pangenome_genome_locus_count',
        ['genome_id'],
        unique=False,
    )
    # ⭐ The backfill. One row per COLLECTION member — a genome that contributed no gene gets zeros
    # rather than no row, or the picker would silently lose it — and only for pangenomes that have a
    # catalogue, which is when the pangenome layer writes these rows on a fresh ingest.
    op.execute(
        """
        INSERT INTO pangenome_genome_locus_count
               (pangenome_id, genome_id, locus_count, arrangement_locus_count)
        SELECT p.pangenome_id,
               member.genome_id,
               coalesce(present.locus_count, 0),
               coalesce(arranged.arrangement_locus_count, 0)
          FROM pangenome p
          JOIN genome_collection_membership member
            ON member.genome_collection_id = p.genome_collection_id
          LEFT JOIN (SELECT pangenome_id, genome_id, count(DISTINCT locus_id) AS locus_count
                       FROM gene_locus_membership
                      GROUP BY pangenome_id, genome_id) present
            ON present.pangenome_id = p.pangenome_id AND present.genome_id = member.genome_id
          LEFT JOIN (SELECT a.pangenome_id,
                            arranged_genome_id AS genome_id,
                            count(DISTINCT a.locus_id) AS arrangement_locus_count
                       FROM locus_arrangement a
                      CROSS JOIN LATERAL unnest(a.member_genome_ids) AS arranged_genome_id
                      GROUP BY a.pangenome_id, arranged_genome_id) arranged
            ON arranged.pangenome_id = p.pangenome_id AND arranged.genome_id = member.genome_id
         WHERE EXISTS (SELECT 1 FROM locus l WHERE l.pangenome_id = p.pangenome_id)
        """
    )


def downgrade() -> None:
    op.drop_index('ix_pangenome_genome_locus_count__genome_id', table_name='pangenome_genome_locus_count')
    op.drop_table('pangenome_genome_locus_count')
