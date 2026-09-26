"""the catalogue dust is O(catalogue) — so it becomes one picture

⭐ The whole-catalogue scatter, pre-rendered per (pangenome, representation). Everything else the
map needs is a handful of numbers; the dust behind them is 889,160 × 4 B at the design target, sent
on every page load to draw a texture no reader reads a value out of.

⛔ The four viewport columns are the contract between the picture and the six dots drawn on top of
it. A client that re-derives the transform puts the focal dot beside its own speck rather than on
it, and the picture still looks like a picture.

Revision ID: d7c2b6e4a915
Revises: c4e9a71d2f80
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd7c2b6e4a915'
down_revision: str | None = 'c4e9a71d2f80'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'locus_map_scatter_sprite',
        sa.Column('locus_map_scatter_sprite_id', sa.Integer(), autoincrement=True, nullable=False),
        # ⚠ BigInteger, because `pangenome.pangenome_id` is — an Integer FK onto a BigInteger PK
        # applies cleanly and then drifts from the models forever.
        sa.Column('pangenome_id', sa.BigInteger(), nullable=False),
        # ⚠ `create_type=False`, and it must be the POSTGRESQL enum to accept that argument. The
        # type already exists from the initial schema; letting this migration emit `CREATE TYPE`
        # again fails the whole upgrade on any database that has ever been built.
        sa.Column(
            'representation',
            postgresql.ENUM('ESM', 'BACFORMER', name='embeddingrepresentation', create_type=False),
            nullable=False,
        ),
        sa.Column('image_png', sa.LargeBinary(), nullable=False),
        sa.Column('image_media_type', sa.String(length=32), nullable=False, server_default='image/png'),
        sa.Column('pixel_size', sa.Integer(), nullable=False),
        # ⛔ The viewport the renderer ACTUALLY used, in the quantised units of map_x/map_y.
        sa.Column('viewport_centre_x', sa.Float(), nullable=False),
        sa.Column('viewport_centre_y', sa.Float(), nullable=False),
        sa.Column('viewport_span', sa.Float(), nullable=False),
        sa.Column('dust_radius_pixels', sa.Float(), nullable=False),
        sa.Column('alpha_per_locus', sa.Float(), nullable=False),
        # ⭐ The honest denominator: a locus with no medoid has no geometry row and no speck, so the
        # catalogue size is NOT what this picture shows.
        sa.Column('plotted_locus_count', sa.Integer(), nullable=False),
        sa.Column('unplotted_locus_count', sa.Integer(), nullable=False),
        # ⚠ sha256 of the bytes, and it is the ETag — an image is cached hard by things we do not
        # control, so a re-render under the same pangenome id must be able to invalidate it.
        sa.Column('content_digest', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ['pangenome_id'],
            ['pangenome.pangenome_id'],
            name=op.f('fk_locus_map_scatter_sprite__pangenome_id__pangenome'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('locus_map_scatter_sprite_id', name=op.f('pk_locus_map_scatter_sprite')),
        sa.UniqueConstraint(
            'pangenome_id',
            'representation',
            name=op.f('uq_locus_map_scatter_sprite__pangenome_id_representation'),
        ),
    )


def downgrade() -> None:
    op.drop_table('locus_map_scatter_sprite')
