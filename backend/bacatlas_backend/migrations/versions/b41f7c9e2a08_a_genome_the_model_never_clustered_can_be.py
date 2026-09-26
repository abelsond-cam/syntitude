"""a genome the model never clustered can be placed on its loci, and changes nothing else

⭐ Two tables for "View your own genomes" (David, 2026-09-22). A reader's genome is placed on the
published loci by its genes' nearest modelled neighbours in Bacformer space, and **nothing that
already exists is touched**: no `gene_locus_membership` row, no `genome_collection_membership`, no
`locus_arrangement.member_genome_ids`, no `pangenome_genome_locus_count`. The publish gate, the
column audit and the parity suites keep meaning what they meant.

⛔ **Additive by construction, and that is the design.** A projected genome is not a member of the
collection. Every count on the page — prevalence, bands, census, marginals, arrangement genome
counts, the picker — stays the modelled 100, and the no-count-change test asserts that the shell, an
unanchored locus and the genome list are byte-identical before and after `--stage projection`.

⚠ **Four counts on `projected_genome` that are NOT the same number**, because merging any two makes
the page claim something it cannot support: the genome's genes; the genes placed; the genes with no
Bacformer vector at all (past its 6,000-protein cut, so no placement); and the genes alone on their
contig, which have a placement but no ±5 window. The last is an absence of observation, not a
neighbourhood that matched nothing.

⚠ **`available_neighbour_count` rides beside `agreeing_neighbour_count` deliberately.** A locus with
*m* modelled genes can supply at most min(n, m) of the n checkers, so the raw agreement is bounded by
locus size: measured on the first ten genomes, contested is 0.39 % at loci with ≥ 10 modelled genes,
42.6 % below that, and 96.3 % at singletons. Storing the denominator means a serialiser cannot report
the numerator alone.

Revision ID: b41f7c9e2a08
Revises: d79a80412308
Create Date: 2026-09-23 11:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b41f7c9e2a08'
down_revision: str | None = 'd79a80412308'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'projected_genome',
        sa.Column('pangenome_id', sa.BigInteger(), nullable=False),
        # ⚠ Integer, not BigInteger: `genome.genome_id` is Integer and a foreign key must
        # match its target's type exactly.
        sa.Column('genome_id', sa.Integer(), nullable=False),
        # ⛔ The sentence a reader is owed, stored beside the rows: a placement is ONE
        # nearest-neighbour hop, not the model's CPM chain.
        sa.Column('rule_label', sa.Text(), nullable=False),
        sa.Column('neighbours_searched', sa.Integer(), nullable=False),
        sa.Column('neighbours_reported', sa.Integer(), nullable=False),
        sa.Column('representation', sa.String(length=32), nullable=False, server_default='bacformer'),
        sa.Column('source_file_path', sa.Text(), nullable=False),
        sa.Column('source_sha256', sa.String(length=64), nullable=True),
        # ⚠ Must equal pangenome.assignment_sha256 — a projection computed against a different
        # assignment names loci that mean something else, and the ingest refuses it by name.
        sa.Column('assignment_sha256', sa.String(length=64), nullable=True),
        sa.Column('nuna_git_sha', sa.String(length=64), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('gene_count', sa.Integer(), nullable=False),
        sa.Column('placed_gene_count', sa.Integer(), nullable=False),
        sa.Column('gene_without_vector_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gene_without_window_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('contested_gene_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('distinct_locus_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('multi_copy_locus_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('window_matched_gene_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('nearest_cosine_median', sa.Float(), nullable=True),
        sa.Column('nearest_cosine_fifth_percentile', sa.Float(), nullable=True),
        sa.Column('nearest_cosine_minimum', sa.Float(), nullable=True),
        sa.CheckConstraint('placed_gene_count >= 0', name=op.f('ck_projected_genome__placed_gene_count_is_not_negative')),
        sa.CheckConstraint(
            'neighbours_reported <= neighbours_searched',
            name=op.f('ck_projected_genome__neighbours_reported_within_neighbours_searched'),
        ),
        # ⚠ `<> 'NaN'`, never `col = col`: Postgres defines NaN = NaN as TRUE, so the IEEE-754
        # self-inequality check passes every NaN — the exact failure this guard exists to catch.
        sa.CheckConstraint(
            "nearest_cosine_median IS NULL OR nearest_cosine_median <> 'NaN'::double precision",
            name=op.f('ck_projected_genome__nearest_cosine_median_is_not_nan'),
        ),
        sa.CheckConstraint(
            "nearest_cosine_fifth_percentile IS NULL OR nearest_cosine_fifth_percentile <> 'NaN'::double precision",
            name=op.f('ck_projected_genome__nearest_cosine_fifth_percentile_is_not_nan'),
        ),
        sa.CheckConstraint(
            "nearest_cosine_minimum IS NULL OR nearest_cosine_minimum <> 'NaN'::double precision",
            name=op.f('ck_projected_genome__nearest_cosine_minimum_is_not_nan'),
        ),
        sa.ForeignKeyConstraint(
            ['pangenome_id'],
            ['pangenome.pangenome_id'],
            name=op.f('fk_projected_genome__pangenome_id__pangenome'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['genome_id'],
            ['genome.genome_id'],
            name=op.f('fk_projected_genome__genome_id__genome'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('pangenome_id', 'genome_id', name=op.f('pk_projected_genome')),
    )
    op.create_index(op.f('ix_projected_genome__pangenome_id'), 'projected_genome', ['pangenome_id'])

    op.create_table(
        'projected_gene_placement',
        sa.Column('pangenome_id', sa.BigInteger(), nullable=False),
        # ⚠ Integer, not BigInteger: `genome.genome_id` is Integer and a foreign key must
        # match its target's type exactly.
        sa.Column('genome_id', sa.Integer(), nullable=False),
        sa.Column('flat_index', sa.Integer(), nullable=False),
        # ⚠ NOT NULL: every gene is placed. There is no novelty status and no row meaning "nowhere"
        # (David, 2026-09-22) — a nullable locus would invite a threshold back in.
        sa.Column('locus_id', sa.BigInteger(), nullable=False),
        sa.Column('nearest_cosine', sa.Float(), nullable=True),
        sa.Column('agreeing_neighbour_count', sa.SmallInteger(), nullable=False),
        sa.Column('available_neighbour_count', sa.SmallInteger(), nullable=False),
        sa.Column('placed_summed_cosine', sa.Float(), nullable=True),
        # The runner-up is ABSENT, not zero, when all n checkers sit in the placed locus.
        sa.Column('runner_up_locus_id', sa.BigInteger(), nullable=True),
        sa.Column('runner_up_summed_cosine', sa.Float(), nullable=True),
        sa.Column('is_contested', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('copy_ordinal', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('copies_at_locus', sa.SmallInteger(), nullable=False, server_default='1'),
        # ⚠ NULL here means the gene is ALONE ON ITS CONTIG — no window exists. That is not the same
        # as a window matching no arrangement, which is a present vector with a null match.
        sa.Column('neighbour_slot_codes', sa.ARRAY(sa.Integer()), nullable=True),
        sa.Column('matched_locus_arrangement_id', sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            'agreeing_neighbour_count >= 0',
            name=op.f('ck_projected_gene_placement__agreeing_neighbour_count_is_not_negative'),
        ),
        sa.CheckConstraint(
            "nearest_cosine IS NULL OR nearest_cosine <> 'NaN'::double precision",
            name=op.f('ck_projected_gene_placement__nearest_cosine_is_not_nan'),
        ),
        sa.CheckConstraint(
            "placed_summed_cosine IS NULL OR placed_summed_cosine <> 'NaN'::double precision",
            name=op.f('ck_projected_gene_placement__placed_summed_cosine_is_not_nan'),
        ),
        sa.CheckConstraint(
            "runner_up_summed_cosine IS NULL OR runner_up_summed_cosine <> 'NaN'::double precision",
            name=op.f('ck_projected_gene_placement__runner_up_summed_cosine_is_not_nan'),
        ),
        sa.ForeignKeyConstraint(
            ['pangenome_id', 'genome_id'],
            ['projected_genome.pangenome_id', 'projected_genome.genome_id'],
            name=op.f('fk_projected_gene_placement__projected_genome'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['genome_id', 'flat_index'],
            ['gene.genome_id', 'gene.flat_index'],
            name=op.f('fk_projected_gene_placement__gene'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['locus_id'],
            ['locus.locus_id'],
            name=op.f('fk_projected_gene_placement__locus_id__locus'),
            ondelete='CASCADE',
        ),
        # SET NULL, not CASCADE: losing the runner-up must not delete the placement it qualifies.
        sa.ForeignKeyConstraint(
            ['runner_up_locus_id'],
            ['locus.locus_id'],
            name=op.f('fk_projected_gene_placement__runner_up_locus_id__locus'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['matched_locus_arrangement_id'],
            ['locus_arrangement.locus_arrangement_id'],
            name=op.f('fk_projected_gene_placement__matched_locus_arrangement_id__locus_arrangement'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint(
            'pangenome_id', 'genome_id', 'flat_index', name=op.f('pk_projected_gene_placement')
        ),
    )
    # ⭐ The hot path: "what has this projected genome placed at this locus", one index scan beside
    # the arrangements, so the anchored locus view stays inside its statement budget.
    op.create_index(
        op.f('ix_projected_gene_placement__pangenome_id__locus_id'),
        'projected_gene_placement',
        ['pangenome_id', 'locus_id'],
    )
    op.create_index(
        op.f('ix_projected_gene_placement__locus_id__genome_id'),
        'projected_gene_placement',
        ['locus_id', 'genome_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_projected_gene_placement__locus_id__genome_id'), table_name='projected_gene_placement')
    op.drop_index(
        op.f('ix_projected_gene_placement__pangenome_id__locus_id'), table_name='projected_gene_placement'
    )
    op.drop_table('projected_gene_placement')
    op.drop_index(op.f('ix_projected_genome__pangenome_id'), table_name='projected_genome')
    op.drop_table('projected_genome')
