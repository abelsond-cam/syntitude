"""ORM rows → plain dicts. **No ORM object escapes a serialiser.**

⛔ **A slot is `null` plus an `absence_reason`, never a bare `-1`.** `occ(code)` is deleted: that
packed form is exactly where the "−1 means five different things" trap lives, and a serialiser that
mapped every `-1` to `null` would be right twice and destroy three meanings.

⛔ **Every remainder is its own named field, one per sentence.** `observed_not_listed` is a
*display* cut; `members_without_an_observation` is *missing data* (a contig end);
`arrangements_not_listed` is what the arrangement cap left out; `members_in_arrangements_not_listed`
is the members inside those; `members_without_a_neighbourhood` is members with no recorded window at
all. A rewrite that computes "the rest" once collapses them and the page starts making a claim it
cannot support — so each is emitted, and each is emitted even when it is zero.

⚠ **There are five here and four in the plan, and the fifth is the API's own doing.** The published
payload is uncapped, so *members past the cap* did not exist as a category and `size − Σ(listed)`
really did mean "no coordinates for the gene, so no window". The moment the API capped the
arrangement list that stopped being true, and splitting the two is what keeps the fourth honest.

⚠ **`null` is *not measured* and `0.0` is *measured zero*, everywhere below.** A serialiser that
emitted `0` for an absent float would turn "we did not look" into "we looked and found nothing".
"""

from __future__ import annotations

from syntitude_backend.services.locus_detail_service import (
    SIGNED_OFFSETS,
    LocusDetail,
    resolve_cosine_matrix,
)

#: What a slot's absence means, when it has one. ⛔ A contig end is an OBSERVATION — the member
#: genuinely has no gene there — and is not the same as a neighbour that fell outside the catalogue.
ABSENCE_CONTIG_END = "contig_end"


def serialise_annotation_entry(entry) -> dict:
    """One (vocabulary, term) row. `term_name` is `null` where the vocabulary has no name to give."""
    return {
        "rank": entry.rank_within_locus,
        "term": entry.term_value,
        "name": entry.term_name,
        "gene_count": entry.member_gene_count,
        **(
            {"gene_ontology_namespace": entry.gene_ontology_namespace}
            if entry.gene_ontology_namespace is not None
            else {}
        ),
    }


def serialise_uniref_family(family) -> dict:
    """One UniRef50 family's row of the cross-tab.

    ⚠ `distinct_symbol_count` is a COUNT and not a list: the page shows the modal plus "+N" and
    cannot name the others, so the response must not appear to offer them.
    """
    return {
        "rank": family.rank_within_locus,
        "uniref50_accession": family.uniref50_accession,
        "gene_count": family.member_gene_count,
        "modal_product": family.modal_bakta_product,
        "modal_architecture": family.modal_pfam_architecture,
        "pfam_annotated_gene_count": family.pfam_annotated_member_count,
        "modal_symbol": family.modal_bakta_gene_symbol,
        "distinct_symbol_count": family.distinct_real_symbol_count,
    }


def serialise_arrangement(arrangement, neighbours) -> dict:
    """One whole ±5 neighbourhood — the JOINT view, with each slot resolved or explicitly absent."""
    slots = []
    for position, offset in enumerate(SIGNED_OFFSETS):
        code = arrangement.neighbour_slot_codes[position]
        if code < 0:
            slots.append(
                {
                    "signed_offset": offset,
                    "locus": None,
                    # ⛔ Named, not implied by the null. A member truncated at a contig edge has a
                    # genuinely different OBSERVED neighbourhood; folding it into the untruncated
                    # group would claim an observation that was never made.
                    "absence_reason": ABSENCE_CONTIG_END,
                    "same_strand": None,
                }
            )
            continue
        row = neighbours.by_catalogue_ordinal.get(code // 2)
        slots.append(
            {
                "signed_offset": offset,
                "locus": row.node_label if row else None,
                "absence_reason": None if row else "outside_catalogue",
                "same_strand": bool(code % 2),
            }
        )
    return {
        "rank": arrangement.rank_within_locus,
        "gene_count": arrangement.member_gene_count,
        "genome_count": arrangement.member_genome_count,
        # ⚠ INTRINSIC to the arrangement, not display mirroring. The two are different slot spaces,
        # and conflating them puts a count from one position under a gene from another.
        "is_recorded_reverse_complement": arrangement.is_recorded_reverse_complement,
        "slots": slots,
    }


def serialise_offset_occupants(detail: LocusDetail) -> list[dict]:
    """The MARGINAL view — one entry per offset, each with its own honest denominator."""
    observed = list(detail.locus.context_observed_member_counts)
    out = []
    for position, offset in enumerate(SIGNED_OFFSETS):
        occupants = detail.offset_occupants.get(offset, [])
        listed = sum(occupant.member_gene_count for occupant in occupants)
        observed_here = observed[position] if position < len(observed) else 0
        out.append(
            {
                "signed_offset": offset,
                "observed_member_count": observed_here,
                # ⛔ Two different remainders, both emitted, both named.
                "observed_not_listed": max(0, observed_here - listed),
                "members_without_an_observation": max(
                    0, detail.locus.member_gene_count - observed_here
                ),
                "occupants": [
                    {
                        "rank": occupant.rank_within_offset,
                        "locus": (
                            detail.neighbour_display_rows.by_locus_id[
                                occupant.neighbour_locus_id
                            ].node_label
                            if occupant.neighbour_locus_id in detail.neighbour_display_rows.by_locus_id
                            else None
                        ),
                        "gene_count": occupant.member_gene_count,
                        "same_strand_gene_count": occupant.same_strand_member_count,
                    }
                    for occupant in occupants
                ],
            }
        )
    return out


def serialise_intergenic_gap(gap, labels: dict) -> dict:
    """One gap, keyed by the two flanking LABELS — never by an index.

    ⛔ The published page keys its gap lookup by payload INDEX against a map built from
    **label**-sorted pairs, and 7,379 of 22,838 *E. coli* gaps therefore cannot be found on it: the
    track draws no block, which reads as *"these genes are adjacent with nothing between them"*. The
    API answers with the labels, so a client sorts two strings and the miss cannot recur.
    """
    return {
        "flanking_loci": [labels.get(gap.flanking_locus_id_a), labels.get(gap.flanking_locus_id_b)],
        "observed_genome_count": gap.observed_genome_count,
        # ⛔ SIGNED. Negative means the two genes OVERLAP — 18.8 % of adjacent pairs do, at a median
        # of −4 bases. Clamping at zero made *abuts exactly* and *overlaps by 190* the same number.
        "median_signed_length_nt": gap.median_signed_length_nt,
        "quartile1_signed_length_nt": gap.quartile1_signed_length_nt,
        "quartile3_signed_length_nt": gap.quartile3_signed_length_nt,
        "minimum_signed_length_nt": gap.minimum_signed_length_nt,
        "maximum_signed_length_nt": gap.maximum_signed_length_nt,
        # ⛔ `null` = not measured; `0.0` = every genome agrees. White on the track has to mean
        # "identical in every genome", never "small".
        "length_variance_score": gap.length_variance_score,
        "modal_length_nt": gap.modal_length_nt,
        "distinct_named_feature_count": gap.distinct_named_feature_count,
        # ⚠ `q1 == q3` means the MIDDLE HALF agrees; only `mn == mx` certifies the strong claim.
        "every_genome_agrees": (
            gap.minimum_signed_length_nt is not None
            and gap.minimum_signed_length_nt == gap.maximum_signed_length_nt
        ),
    }


def serialise_locus_detail(detail: LocusDetail, *, cosine_scale_factor: int = 10_000) -> dict:
    """The whole locus response — one round trip, and the popover is then offline."""
    locus = detail.locus
    neighbours = detail.neighbour_display_rows
    labels = {row.locus_id: row.node_label for row in neighbours.by_locus_id.values()}
    labels.setdefault(locus.locus_id, locus.node_label)

    listed_members = sum(
        arrangement.member_gene_count for arrangement in detail.arrangements
    )
    return {
        "locus": {
            "label": locus.node_label,
            "catalogue_ordinal": locus.catalogue_ordinal,
            "display_name": locus.display_name,
            "display_name_source": locus.display_name_source,
            "display_name_source_accession": locus.display_name_source_accession,
            "best_product": locus.best_product,
            "bakta_gene_symbol": locus.bakta_gene_symbol,
            "gene_count": locus.member_gene_count,
            "genome_count": locus.member_genome_count,
            "named_gene_count": locus.named_member_count,
            "prevalence_band": locus.prevalence_band.value,
            "median_gene_length_nt": locus.median_gene_length_nt,
            "gene_length_interquartile_range_nt": locus.gene_length_interquartile_range_nt,
            "uniref50": {
                "family_count": locus.uniref50_family_count,
                # ⚠ What the card CLAIMS with, while the list below shows every family.
                "major_family_count": locus.uniref50_major_family_count,
                "labelled_gene_count": locus.uniref50_labelled_member_count,
                "impurity": locus.uniref50_impurity,
                "coverage": locus.uniref50_coverage,
            },
            "pfam": {
                # ⛔ `gene_count − annotated_gene_count` is MISSING COVERAGE, not a competing
                # architecture. Without this denominator the page cannot tell the two apart.
                "annotated_gene_count": locus.pfam_annotated_member_count,
                "architecture_count": locus.pfam_architecture_count,
                # ⛔ The audit's own verdict, read and never re-derived.
                "concordance_class": locus.pfam_concordance_class,
            },
            "evidence": {
                "syntenic_a5": locus.syntenic_a5,
                "collapse_tier": locus.collapse_tier,
                "collapse_bucket": locus.collapse_bucket,
                # ⚠ Over at most 50 members, longest-first (`FAMILY_MEMBER_CAP`) — 4,138 of 12,104
                # ecoli loci sit at that cap, so this is "the identity at which the 50 longest
                # members first group", a different and weaker claim than the whole locus.
                "resolved_threshold": locus.resolved_threshold,
                "resolved_threshold_is_capped_at_50_members": True,
            },
            "geometry": {
                representation: {
                    "within_medoid_distance": getattr(
                        locus, f"{'esm' if representation == 'esm' else 'bacformer'}_within_medoid_distance"
                    ),
                    "nearest_medoid_distance": getattr(
                        locus, f"{'esm' if representation == 'esm' else 'bacformer'}_nearest_medoid_distance"
                    ),
                    "separation_percentile": getattr(
                        locus, f"separation_percentile_{'esm' if representation == 'esm' else 'bacformer'}"
                    ),
                    "map_position": (
                        [geometry.map_x, geometry.map_y] if geometry is not None else None
                    ),
                    "nearest_locus_ordinals": (
                        list(geometry.nearest_locus_ordinals) if geometry is not None else None
                    ),
                    # ⛔ Resolved server-side, `-1` slot-drops already applied: slots are not ranks.
                    "cosine_matrix": (
                        resolve_cosine_matrix(geometry, cosine_scale_factor)
                        if geometry is not None
                        else None
                    ),
                }
                for representation, geometry in (
                    ("esm", detail.geometry.get("esm")),
                    ("bacformer", detail.geometry.get("bacformer")),
                )
            },
            "interest_score": locus.interest_score,
        },
        "annotations": {
            kind: [serialise_annotation_entry(entry) for entry in entries]
            for kind, entries in detail.card_annotations.items()
        },
        "uniref50_families": [serialise_uniref_family(family) for family in detail.uniref_families],
        "arrangements": {
            "listed": [
                serialise_arrangement(arrangement, neighbours) for arrangement in detail.arrangements
            ],
            # ⛔ Never moved by any display cap, and never conflated with the number listed.
            "total": locus.total_arrangement_count,
            "arrangements_not_listed": max(
                0, locus.total_arrangement_count - detail.arrangements_listed
            ),
            # ⛔⛔ TWO remainders, and the API needs both where the published page needed only one.
            # That payload is UNCAPPED, so `size − Σ(listed)` there really did mean "no coordinates
            # for the gene, so no window". Capping the list at 8 makes the same subtraction sweep in
            # every member sitting past the cap — 15,912 E. coli genes over 2,340 loci and 10,437 kp
            # genes over 1,548 — each of which the page would then have told a reader has no
            # coordinates. `arrangement_member_gene_count` is the denominator that separates them.
            "members_in_arrangements_not_listed": max(
                0, locus.arrangement_member_gene_count - listed_members
            ),
            "members_without_a_neighbourhood": max(
                0, locus.member_gene_count - locus.arrangement_member_gene_count
            ),
            # ⛔ Whether EVERY genome present reaches an arrangement — a GENOME question, and the
            # only thing that settles which of two sentences the anchor line may say. Empty anchor
            # ranks mean *"has no gene at this locus"* only where membership is complete; where it
            # is not, the true sentence is *"has no recorded neighbourhood at this locus"*, and at
            # 6.26 % of ecoli loci the first one is false. ⚠ Not derivable from the gene counts
            # above: a genome at ρ > 1 can lose one gene's window and keep its arrangement.
            "membership_is_complete": (
                locus.arrangement_member_genome_count >= locus.member_genome_count
            ),
        },
        # ⛔ A LIST, and it is not decoration: without it a client cannot draw the anchored
        # arrangement by default, and cannot offer the button that the display cap's whole rule
        # exists for — "otherwise the reader is told in words that their genome sits in #37 and has
        # no button to go back to it". Empty means the anchored genome has no gene here, which is a
        # different statement from there being no anchor; `is_anchored` separates them.
        "anchor": {
            "is_anchored": detail.is_anchored,
            "arrangement_ranks": list(detail.anchor_arrangement_ranks),
        },
        "offsets": serialise_offset_occupants(detail),
        "intergenic_gaps": [
            serialise_intergenic_gap(gap, labels) for gap in detail.intergenic_gaps
        ],
        # ⭐ The fan-out, answered in this response rather than in 15–303 more.
        "neighbour_display_rows": [
            {
                "label": row.node_label,
                "display_name": row.display_name,
                "display_name_source": row.display_name_source,
                "genome_count": row.member_genome_count,
                "median_gene_length_nt": row.median_gene_length_nt,
                "prevalence_band": row.prevalence_band,
            }
            for row in sorted(neighbours.all_rows(), key=lambda row: row.node_label)
        ],
    }
