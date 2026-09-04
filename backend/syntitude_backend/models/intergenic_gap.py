"""Intergenic regions — a property of an ADJACENCY, not of a position.

⛔ Keyed on the **sorted pair** of flanking loci, which is what makes the whole block additive:
nothing is inserted into any sequence, so the offsets, the marginal and the joint views are all
untouched. Sorted, because the track is drawn in the focal gene's reading frame and a neighbourhood
may be mirrored — an ordered key would miss on half of them.

⚠ **Three things this is not.** A gap is not a locus — no cluster, no embedding, not in the locus
count, not walkable. Its length is a **median over genomes that disagree**, not a distance. And the
page draws gaps only where an arrangement is selected: without one the track shows each position's
marginal mode, and two marginal modes need not be neighbours in any genome, so the space between
them is not an observed gap.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base
from syntitude_backend.models.column_types import measurement, nan_guards


class IntergenicGap(Base):
    """The region between two adjacent loci, summarised over the genomes that carry the adjacency."""

    __tablename__ = "intergenic_gap"
    __table_args__ = (
        UniqueConstraint(
            "pangenome_id", "flanking_locus_id_low", "flanking_locus_id_high"
        ),
        Index("ix_intergenic_gap__flanking_locus_id_low", "flanking_locus_id_low"),
        Index("ix_intergenic_gap__flanking_locus_id_high", "flanking_locus_id_high"),
        CheckConstraint(
            "flanking_locus_id_low <= flanking_locus_id_high", name="flanking_pair_is_sorted"
        ),
        *nan_guards("length_variance_score"),
    )

    intergenic_gap_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pangenome_id: Mapped[int] = mapped_column(
        ForeignKey("pangenome.pangenome_id", ondelete="CASCADE"), nullable=False
    )
    flanking_locus_id_low: Mapped[int] = mapped_column(
        ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False
    )
    flanking_locus_id_high: Mapped[int] = mapped_column(
        ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False
    )

    observed_genome_count: Mapped[int] = mapped_column(Integer, nullable=False)

    #: ⛔ **SIGNED. Negative means the two genes OVERLAP** — 18.8 % of adjacent pairs do, at a median
    #: of −4 bases (a shared stop/start codon). Clamping this at zero made *abuts exactly* and
    #: *overlaps by 190 bases* the same number and threw the question away before the page saw it.
    median_signed_length_nt: Mapped[int] = mapped_column(Integer, nullable=False)

    #: ⛔ `q1 == q3` does NOT mean every genome agrees — it means the MIDDLE HALF does. `[1,1,1,1,100]`
    #: has an interquartile range of zero, and an earlier page reported that shape as "identical in
    #: every genome". Only `mn == mx` certifies the strong claim, which is why both pairs exist.
    #: ⚠ Absent means NOT MEASURED, never a spread of zero.
    quartile1_signed_length_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quartile3_signed_length_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_signed_length_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_signed_length_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⛔ **NULL = not measured; 0.0 = every genome agrees.** The payload's sparse `vi`/`vd`/`vmd`
    #: triple existed only because a JSON array cannot be sparse, and there "absent" meant
    #: agreement. Stored densely the meaning INVERTS, so it is spelled out here: white on the track
    #: has to mean "identical in every genome", never "small".
    length_variance_score: Mapped[float | None] = measurement()
    modal_length_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Distinct named features seen in it — the coverage behind the capped list below.
    distinct_named_feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class IntergenicGapFeature(Base):
    """A named non-coding feature observed inside a gap, in some number of genomes.

    Editorial rules recorded as data, decided from the cohort census (job 34060534):
    `crispr-repeat`/`crispr-spacer` fold into the `CRISPR` array containing them at ingest;
    `regulatory_region` is kept in `genome_noncoding_feature` and off the track (50.7 % sit inside a
    CDS); `gap` rows never arrive, being bookkeeping dropped at the parser.
    """

    __tablename__ = "intergenic_gap_feature"
    __table_args__ = (UniqueConstraint("intergenic_gap_id", "rank_within_gap"),)

    intergenic_gap_feature_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intergenic_gap_id: Mapped[int] = mapped_column(
        ForeignKey("intergenic_gap.intergenic_gap_id", ondelete="CASCADE"), nullable=False
    )
    rank_within_gap: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    feature_label: Mapped[str] = mapped_column(String(256), nullable=False)
    feature_type: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_genome_count: Mapped[int] = mapped_column(Integer, nullable=False)
