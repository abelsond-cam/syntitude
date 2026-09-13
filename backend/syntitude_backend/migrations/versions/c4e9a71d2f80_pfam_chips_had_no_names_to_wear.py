"""pfam chips had no names to wear

The locus card chips each Pfam architecture with the family's **short name** (`Sigma70_r2`) and
links it to the **InterPro** entry, which is the integrated record a reader following a domain
actually wants. Neither reaches the database today: `locus_annotation_entry` stores architectures as
comma-joined accessions with `term_name` NULL, so a chip could only say `PF00126`.

The published page joins `pfam_names.tsv.gz` at render time — a vendored public reference, ~24k
families. This is the table version of that join, so the API can resolve it server-side and the page
does not carry an 833 kB reference to render one chip.

⚠ Global, not per pangenome: a Pfam family is the same family in every species and model.

Revision ID: c4e9a71d2f80
Revises: 8b1f4a2c9d3e
Create Date: 2026-09-13 10:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e9a71d2f80'
down_revision: str | None = '8b1f4a2c9d3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pfam_family',
        # ⛔ Version-stripped, exactly as `pfam_reference` strips it. An annotation carrying
        # `PF00126.29` must be cut at the dot before lookup or it silently misses.
        sa.Column('pfam_accession', sa.String(length=16), nullable=False),
        # ⚠ NOT NULL with an empty-string default throughout: the vendored reader PADS short rows
        # rather than skipping them, so "" means the table had no value — and a NULL here would
        # invite the `null`-vs-empty confusion this schema spends its effort avoiding elsewhere.
        sa.Column('short_name', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('interpro_accession', sa.String(length=16), nullable=False, server_default=''),
        sa.Column('interpro_name', sa.Text(), nullable=False, server_default=''),
        # ⚠ A clanless family has '' here, and that is NOT an identity: only ~46 % of families are
        # in a clan, so treating '' as a shared clan would make any two clanless families look like
        # the same superfamily — the common case, not the corner.
        sa.Column('clan_accession', sa.String(length=16), nullable=False, server_default=''),
        sa.Column('clan_name', sa.String(length=128), nullable=False, server_default=''),
        sa.PrimaryKeyConstraint('pfam_accession', name=op.f('pk_pfam_family')),
    )
    op.create_index(
        op.f('ix_pfam_family__interpro_accession'), 'pfam_family', ['interpro_accession'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_pfam_family__interpro_accession'), table_name='pfam_family')
    op.drop_table('pfam_family')
