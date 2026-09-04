"""The neighbourhood map: per-representation projection, per-locus geometry, and the null baseline."""

from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base
from syntitude_backend.models.enumerations import EmbeddingRepresentation

#: The 15 upper-triangle slots among the focal locus (0) and its five nearest (1–5), in the order
#: `catalogue_map.COS6_PAIRS` writes them: (0,1),(0,2),…,(0,5),(1,2),…,(4,5).
#: ⛔ **This ordering is a CONTRACT.** Reorder it on one side only and every stored payload is
#: silently mislabelled, with a picture that still looks like a picture. The API resolves the
#: triangle into a 6×6 matrix server-side so the contract stops being two-sided at all.
COS6_PAIRS = tuple((a, b) for a in range(6) for b in range(a + 1, 6))
NEAREST_NEIGHBOUR_COUNT = 5

#: `x`/`y` sentinel for a locus with no medoid. ⛔ NOT −1, and not `0,0` — the origin is a PLACE, in
#: the middle of the map, so an absent position needs a value outside the ±32,500 range.
NOWHERE_SENTINEL = -32768


class LocusMapProjection(Base):
    """One (pangenome, representation) projection — the scale that inverts the quantisation.

    ⭐ **Both representations ship, and they disagree about which loci are confusable** — which is
    the point: ESM is homology, Bacformer is context, and the tabs deliberately pick different loci.
    """

    __tablename__ = "locus_map_projection"
    __table_args__ = (UniqueConstraint("pangenome_id", "representation"),)

    locus_map_projection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pangenome_id: Mapped[int] = mapped_column(
        ForeignKey("pangenome.pangenome_id", ondelete="CASCADE"), nullable=False
    )
    representation: Mapped[EmbeddingRepresentation] = mapped_column(nullable=False)

    #: What actually ran — `umap-learn(cosine)`, `cuML-UMAP(cosine)`. Distinct from the metric it
    #: was ASKED for: Euclidean and cosine give the same ordering on unit vectors, so nothing in the
    #: picture could reveal a mismatch.
    projection_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_metric: Mapped[str | None] = mapped_column(String(32), nullable=True)
    neighbour_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=NEAREST_NEIGHBOUR_COUNT)

    scale_centre_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_centre_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_span: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: min/max over every locus, precomputed — `mapData().extent` was an O(n) pass at boot.
    extent_min_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extent_min_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extent_max_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extent_max_y: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⭐ Bumped whenever `COS6_PAIRS` changes. Without it a reorder is undetectable and every stored
    #: triangle is quietly mislabelled.
    cos6_pair_order_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    cosine_scale_factor: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    source_csv_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: The random-pair baseline. ⚠ Without it a cosine has no meaning: ESM's random pairs sit at
    #: ~0.645 and Bacformer's at ~0.065, so the same "inter" reads oppositely in the two.
    null_bin_lower_edge: Mapped[float | None] = mapped_column(Float, nullable=True)
    null_bin_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    null_bin_counts: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    null_mean_cosine: Mapped[float | None] = mapped_column(Float, nullable=True)


class LocusEmbeddingGeometry(Base):
    """One locus's position and its local six-point geometry, per representation."""

    __tablename__ = "locus_embedding_geometry"
    __table_args__ = (UniqueConstraint("locus_id", "representation"),)

    locus_embedding_geometry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    locus_id: Mapped[int] = mapped_column(ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False)
    representation: Mapped[EmbeddingRepresentation] = mapped_column(nullable=False)

    #: `NOWHERE_SENTINEL` where the locus has no medoid.
    map_x: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    map_y: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    #: The five nearest OTHER loci, as `catalogue_ordinal`, `-1` where absent.
    #: ⛔ **Slots are not ranks.** A `-1` drops that locus AND its slot; the surviving slot indices
    #: are what address `cos6`. Reading by rank instead draws one locus's distances on another —
    #: and the picture still looks like a picture.
    nearest_locus_ordinals: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)

    #: 15 upper-triangle cosines × `cosine_scale_factor`, in `COS6_PAIRS` order.
    #: ⭐ This is the WHOLE local view: the page turns these into a 6×6 Euclidean matrix
    #: (`√(2−2cos)`) and solves classical MDS on it, per locus, on demand — so "these loci" is a
    #: real fit of those six, not a crop of a global one. The gene UMAP died because a crop was
    #: exactly what it was: six nearest loci spanned a median 18.5 % of the map.
    pairwise_cosine_scaled: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
