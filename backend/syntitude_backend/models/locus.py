"""The locus row — a syntolog locus in one pangenome, with everything the card shows.

Wide on purpose: these are scalars the page filters, sorts and prints, and a locus is fetched whole.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base
from syntitude_backend.models.column_types import measurement, nan_guards
from syntitude_backend.models.enumerations import GeneOntologyAgreementVerdict, PrevalenceBand


class Locus(Base):
    """One node of one pangenome."""

    __tablename__ = "locus"
    __table_args__ = (
        UniqueConstraint("pangenome_id", "node_label"),
        UniqueConstraint("pangenome_id", "catalogue_ordinal"),
        Index("ix_locus__pangenome_id__prevalence_band", "pangenome_id", "prevalence_band"),
        Index("ix_locus__pangenome_id__member_genome_count", "pangenome_id", "member_genome_count"),
        Index("ix_locus__pangenome_id__interest_score", "pangenome_id", "interest_score"),
        *nan_guards(
            "syntenic_a5",
            "uniref50_impurity",
            "uniref50_coverage",
            "resolved_threshold",
            "esm_within_medoid_distance",
            "esm_nearest_medoid_distance",
            "bacformer_within_medoid_distance",
            "bacformer_nearest_medoid_distance",
            "embed_within_over_nearest",
            "seqid_coverage",
            "separation_percentile_esm",
            "separation_percentile_bacformer",
            "interest_score",
        ),
    )

    locus_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pangenome_id: Mapped[int] = mapped_column(
        ForeignKey("pangenome.pangenome_id", ondelete="CASCADE"), nullable=False
    )
    pathogen_species_id: Mapped[int] = mapped_column(
        ForeignKey("pathogen_species.pathogen_species_id"), nullable=False
    )

    #: ⛔ **TEXT, always.** Node labels look numeric and are not; read back as int64 they silently
    #: stop matching. This is also the URL hash and the durable identity across a re-export.
    node_label: Mapped[str] = mapped_column(String(64), nullable=False)

    #: `export_payload.node_order`'s index — the dense 0..n-1 position `arr.vec`, `ctx.nid`,
    #: `gaps.a/b`, `map_reps.near` and `.loci` all point at. ⚠ **Payload-local**: a re-export
    #: renumbers every one of them, which is why `node_label` and not this is the durable key.
    catalogue_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

    member_gene_count: Mapped[int] = mapped_column(Integer, nullable=False)
    member_genome_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prevalence_band: Mapped[PrevalenceBand] = mapped_column(nullable=False)

    # ── naming ────────────────────────────────────────────────────────────────────────────────
    #: ⭐ **Materialised at ingest, NOT NULL.** `displayOf` falls through `inferredName` →
    #: `soleArch` → the locus's full Pfam list + the Pfam name table, then `modalProduct` → its full
    #: product list. Computing it per neighbour at request time is the fan-out problem; computing it
    #: once here turns it into a five-column lookup over ~20 ids.
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    #: `bakta_symbol` | `pfam_architecture` | `product` | `label` — so the page can say WHY.
    display_name_source: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name_source_accession: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: ⭐ Also materialised. `bestProduct` reads every product row with counts and a regex built
    #: from the modal symbol; it is not `products[0]`.
    best_product: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The modal REAL Bakta symbol, locus tags stripped. NULL = unnamed (payload `-1`).
    bakta_gene_symbol: Mapped[str | None] = mapped_column(String(128), nullable=True)
    named_member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── UniRef50 ──────────────────────────────────────────────────────────────────────────────
    uniref50_family_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Families holding ≥10 % of labelled members — **the number the card claims with**, while the
    #: list below shows every family.
    uniref50_major_family_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uniref50_labelled_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ⚠ NULL below 5 labelled members — not measured, never 0.
    uniref50_impurity: Mapped[float | None] = measurement()
    uniref50_coverage: Mapped[float | None] = measurement()

    # ── Pfam ──────────────────────────────────────────────────────────────────────────────────
    #: ⛔ Members carrying ANY Pfam-A domain. `member_gene_count − this` is **missing coverage, not
    #: a competing architecture** — the architecture list drops nulls, so without this denominator
    #: the page cannot tell the two apart.
    pfam_annotated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: The TRUE architecture count, which the capped top-N list cannot show.
    pfam_architecture_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ⛔ The audit's own `class_clan` verdict, **read and never re-derived**. The page once
    #: re-derived it by a different rule and disagreed on 2 of 22,624 loci — *"a page that quotes
    #: the report must not be able to contradict it, ever."*
    pfam_concordance_class: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── evidence ──────────────────────────────────────────────────────────────────────────────
    # ⛔⛔ **THE THREE COLUMNS BELOW ARE COMPUTED OVER AT MOST 50 MEMBERS, NOT OVER THE LOCUS.**
    # `accessory_audit.FAMILY_MEMBER_CAP = 50`, longest-first: the within-cluster all-vs-all is
    # quadratic in members, so each cluster is capped to bound the cost. Measured on the published
    # ecoli catalogue, **4,138 of the 12,104 loci that carry a tier sit at that cap** (34.2 %) —
    # their real member counts run to 143 — so for a third of the catalogue `resolved_threshold`
    # is *"the identity at which the 50 longest members first group"*, which is a different and
    # weaker claim than *"at which the members first group"*.
    # ⚠ `member_gene_count` above is NOT affected: it comes from the assignment via
    # `node_membership_profile`, never from the waterfall. Do not fill it from the audit.
    syntenic_a5: Mapped[float | None] = measurement()
    #: `mmseq@0.4`, `pfam_not_alignable`, `esm_homology`, `synteny_only`, … ⚠ `synteny only` names
    #: the EVIDENCE, not a mistake: non-homologous cargo in a genuinely conserved neighbourhood is
    #: what an identity threshold cannot see, and the reason the method exists.
    collapse_tier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collapse_bucket: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: ⚠ Over ≤50 longest members — see the block above.
    resolved_threshold: Mapped[float | None] = measurement()
    seqid_coverage: Mapped[float | None] = measurement()

    # ── embedding geometry ────────────────────────────────────────────────────────────────────
    esm_within_medoid_distance: Mapped[float | None] = measurement()
    esm_nearest_medoid_distance: Mapped[float | None] = measurement()
    bacformer_within_medoid_distance: Mapped[float | None] = measurement()
    bacformer_nearest_medoid_distance: Mapped[float | None] = measurement()
    embed_within_over_nearest: Mapped[float | None] = measurement()
    medoid_genome_id: Mapped[int | None] = mapped_column(ForeignKey("genome.genome_id"), nullable=True)
    medoid_flat_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⭐ Precomputed MIDRANK over **measurable loci only** — not over the catalogue. The card
    #: prints "p12 of 12,104 loci" and both halves of that are assertions. ⚠ Singletons are NULL and
    #: must read *not measurable*, never `0.000`.
    separation_percentile_esm: Mapped[float | None] = measurement()
    separation_percentile_bacformer: Mapped[float | None] = measurement()

    # ── function block ────────────────────────────────────────────────────────────────────────
    cog_annotated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ⛔ A COUNT, never a relation. COG ids are single-valued per gene, so every member set is a
    #: singleton and an agreement ladder could only ever say `single` or `disjoint`. Two COG ids in
    #: one locus is an ordinary consequence of grouping above family level.
    cog_distinct_id_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modal_cog_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ec_annotated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kegg_annotated_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Coverage BEFORE every verdict, against the locus size — a share against the annotated subset
    #: would read 100 % on a locus where one gene in forty carries a label.
    go_annotated_member_count_molecular_function: Mapped[int | None] = mapped_column(Integer, nullable=True)
    go_annotated_member_count_biological_process: Mapped[int | None] = mapped_column(Integer, nullable=True)
    go_annotated_member_count_cellular_component: Mapped[int | None] = mapped_column(Integer, nullable=True)
    go_verdict_molecular_function: Mapped[GeneOntologyAgreementVerdict | None] = mapped_column(nullable=True)
    go_verdict_biological_process: Mapped[GeneOntologyAgreementVerdict | None] = mapped_column(nullable=True)
    go_verdict_cellular_component: Mapped[GeneOntologyAgreementVerdict | None] = mapped_column(nullable=True)

    # ── extent ────────────────────────────────────────────────────────────────────────────────
    #: ⚠ 1-based inclusive, hence `end - start + 1`. The block on the track is drawn
    #: `max(6, len_nt / 10)` px wide, and a NEIGHBOUR's value sets a neighbour block's width.
    median_gene_length_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gene_length_interquartile_range_nt: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── the marginal denominator, kept as an array ────────────────────────────────────────────
    #: `ctx.obs` — member genes for which each of the ten offsets EXISTS, in `OFFSETS` order
    #: `[-5..-1, 1..5]`. Counted **before** the top-N cut, so "and N others" is honest and
    #: `obs < size` exposes contig-edge truncation. An array because a table whose only non-key
    #: column is one integer is a 40× overhead.
    context_observed_member_counts: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)

    #: `arr.tot` — arrangements in TOTAL. ⛔ Never moved by any display cap, and never conflated
    #: with the number listed: the page keys sentences on this.
    total_arrangement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: `render_page.ranking`'s score, precomputed. Drives the landing locus and the example chips,
    #: which were a render-time payload mutation and are now columns behind a verification gate.
    interest_score: Mapped[float | None] = measurement()

    #: The materialised search haystack: symbol + label + every product + every UniRef50 accession,
    #: lowercased. ⚠ Pfam/COG/GO/EC/KEGG are deliberately NOT in it — that is what `app.js` searches
    #: today, and adding them is a product change, not an implementation detail.
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Locus {self.node_label} {self.display_name!r} n={self.member_gene_count}>"
