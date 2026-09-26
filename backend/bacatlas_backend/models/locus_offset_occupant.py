"""The MARGINAL ±5 view — one candidate at one position, reduced independently.

⛔ **Not the same thing as `locus_arrangement`, and not per gene.** One row says "at −1, locus 1726
sits there in 71 of 97 member genes". Those modes need not co-occur in any genome: read
left-to-right the marginal is a gene order nothing has. It is the bar under each track block; the
track itself comes from the joint view.

⭐ **Rows, not an array, and indexed in BOTH directions.** This is the locus adjacency graph, and it
is queried both ways — "who is at L's +1" and "at whose −1 does L appear". An array would make the
second a full scan.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base

#: The signed-offset vocabulary. ⛔ `0` is deliberately absent — it is the focal locus.
SIGNED_OFFSETS = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)


class LocusOffsetOccupant(Base):
    """One candidate neighbour at one signed offset of one locus."""

    __tablename__ = "locus_offset_occupant"
    __table_args__ = (
        UniqueConstraint("locus_id", "signed_offset", "rank_within_offset"),
        # The forward query: who sits at this locus's +1.
        Index("ix_locus_offset_occupant__locus_id__signed_offset", "locus_id", "signed_offset"),
        # ⭐ The reverse query, which is why this block is rows: at whose −1 does L appear.
        Index("ix_locus_offset_occupant__neighbour_locus_id", "neighbour_locus_id"),
        CheckConstraint(
            "signed_offset BETWEEN -5 AND 5 AND signed_offset <> 0",
            name="signed_offset_excludes_zero",
        ),
    )

    locus_offset_occupant_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    locus_id: Mapped[int] = mapped_column(ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False)
    pangenome_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: ⚠ **Strand-oriented**, by `syntology.flank_windows`: `-1` means one gene upstream *in the
    #: focal gene's direction of transcription*, on either strand. A gene inverted relative to its
    #: neighbours therefore reads as discordant — deliberate, not a bug. A reader who assumes
    #: coordinate order gets a plausible wrong answer.
    signed_offset: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rank_within_offset: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    neighbour_locus_id: Mapped[int] = mapped_column(
        ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False
    )
    member_gene_count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: How many of those are transcribed the same way as the focal gene — the arrow direction.
    same_strand_member_count: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<LocusOffsetOccupant {self.locus_id}@{self.signed_offset} -> {self.neighbour_locus_id}>"
