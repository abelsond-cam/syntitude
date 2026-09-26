"""A projected genome as JSON — and never as a member of the catalogue.

⛔ Every field here describes a genome placed BESIDE the model. The serialiser deliberately emits no
key that a client could confuse with membership: no `genome_index`, no prevalence, no share of the
catalogue. What it does emit is the rule, the evidence and its denominator.
"""

from __future__ import annotations

from bacatlas_backend.services.projected_genome_service import ProjectedGenomeRow


def serialise_projected_genome(row: ProjectedGenomeRow) -> dict:
    """One row for the picker and the summary.

    ⛔ **Four counts that are not the same number**, and the reason they are all here: `gene_count`
    is the genome's genes; `placed_gene_count` is how many were placed; `genes_without_a_vector` had
    no Bacformer embedding at all (past its 6,000-protein cut) and so no placement; and
    `genes_without_a_neighbourhood` are alone on their contig, placed but with no ±5 window. A page
    that merged any two would describe genes it has nothing to say about.

    ⚠ **The cosine DISTRIBUTION, not a mean.** There is no novelty threshold — every gene is placed
    — so the spread is the only thing that makes a distant placement visible.
    """
    return {
        "sample_id": row.sample_id,
        "rule": row.rule_label,
        "neighbours_searched": row.neighbours_searched,
        "neighbours_reported": row.neighbours_reported,
        "gene_count": row.gene_count,
        "placed_gene_count": row.placed_gene_count,
        "genes_without_a_vector": row.gene_without_vector_count,
        "genes_without_a_neighbourhood": row.gene_without_window_count,
        "contested_gene_count": row.contested_gene_count,
        "distinct_locus_count": row.distinct_locus_count,
        "multi_copy_locus_count": row.multi_copy_locus_count,
        "window_matched_gene_count": row.window_matched_gene_count,
        "nearest_cosine": {
            "median": row.nearest_cosine_median,
            "fifth_percentile": row.nearest_cosine_fifth_percentile,
            "minimum": row.nearest_cosine_minimum,
        },
        "nuna_git_sha": row.nuna_git_sha,
    }
