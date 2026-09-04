"""Per-locus annotation lists, and the UniRef50 cross-tab that earns its own table."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base
from syntitude_backend.models.enumerations import AnnotationKind


class LocusAnnotationEntry(Base):
    """One (locus, vocabulary, term) row, in rank order.

    Rows rather than an array because **the reverse query is real** — "which loci carry COG0450" —
    and because rank order is then a column rather than a position.
    """

    __tablename__ = "locus_annotation_entry"
    __table_args__ = (
        UniqueConstraint("locus_id", "annotation_kind", "rank_within_locus"),
        Index("ix_locus_annotation_entry__locus_id__annotation_kind", "locus_id", "annotation_kind"),
        Index("ix_locus_annotation_entry__annotation_kind__term_value", "annotation_kind", "term_value"),
    )

    locus_annotation_entry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    locus_id: Mapped[int] = mapped_column(ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False)

    annotation_kind: Mapped[AnnotationKind] = mapped_column(nullable=False)
    rank_within_locus: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    term_value: Mapped[str] = mapped_column(String(256), nullable=False)
    #: The name, joined in at ingest from the vendored table. ⚠ Joined into the ROW that uses it,
    #: not shipped as a lookup table — which is what makes the render-time `attach_*` mutation (five
    #: days of pages with no accession names) structurally impossible.
    term_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_gene_count: Mapped[int] = mapped_column(Integer, nullable=False)

    #: 0/1/2 — molecular function / biological process / cellular component. Non-NULL only for
    #: `gene_ontology_slim`, so one list serves all three namespaces.
    #: ⛔ GO ids here are **SLIM CLASSES, not raw terms**. GO is a DAG: a term and its own child
    #: share nothing, so compared raw they read as `disjoint`. Folded onto `goslim_metagenomics`,
    #: chosen by measurement — it folds 97.0 % of this cohort against `goslim_generic`'s 60.1 %.
    gene_ontology_namespace: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class LocusUnirefFamilyCrosstab(Base):
    """One (locus, UniRef50 family) row — what that family's OWN genes look like.

    Its own table because it carries five columns the other vocabularies do not, and a shared table
    would make all five nullable for six other kinds.

    **Why the join exists.** Before it, the page had a family-count list and a symbol-count list in
    two cards, and the correspondence was left to the reader. On `ybeF` the families split 63/33 and
    the symbols 63/35 — close enough to read as a correspondence, and not one anything asserted.
    """

    __tablename__ = "locus_uniref_family_crosstab"
    __table_args__ = (
        UniqueConstraint("locus_id", "rank_within_locus"),
        Index("ix_locus_uniref_family_crosstab__uniref50_accession", "uniref50_accession"),
    )

    locus_uniref_family_crosstab_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    locus_id: Mapped[int] = mapped_column(ForeignKey("locus.locus_id", ondelete="CASCADE"), nullable=False)
    rank_within_locus: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    #: ⚠ A UniRef50 accession has **no name anywhere** — hence `modal_bakta_product` below, which is
    #: descriptive only and is that family's modal product *within this locus*.
    uniref50_accession: Mapped[str] = mapped_column(String(64), nullable=False)
    member_gene_count: Mapped[int] = mapped_column(Integer, nullable=False)

    modal_bakta_product: Mapped[str | None] = mapped_column(Text, nullable=True)
    modal_pfam_architecture: Mapped[str | None] = mapped_column(String(512), nullable=True)
    #: How many of THIS FAMILY's genes carry any domain — so an unannotated family reads as
    #: unannotated rather than as one with a different architecture.
    pfam_annotated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⚠ Must be computed from the frame `real_gene_names` has ALREADY filtered. Bakta emits a
    #: genome-private locus tag (`AAOCBP_22210`) where it has no symbol; those are unique per
    #: genome, so a family holding them would report `distinct_real_symbol_count = 1` and read as
    #: unanimous.
    modal_bakta_gene_symbol: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: ⚠ A COUNT, not a list. The page shows the modal plus "+N"; it cannot name the others and must
    #: not appear to. Showing the modal alone would let a family that is itself split read as agreed
    #: — the exact failure this cross-tab exists to expose.
    distinct_real_symbol_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
