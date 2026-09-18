"""The audit's residual loci — every one grouped on context alone, and every Pfam conflict.

⭐ **A model's own residuals, on its own page.** The published footer lists both, each locus one click
away (`render_page._failures`), because they are exactly where to look first: where the model is doing
something an identity threshold cannot, and where it would go wrong if it did.

⛔ **Two lists, never one.** They are different kinds of evidence and neither is a verdict. *Grouped
on context alone* says no sequence, Pfam or ESM method could join the members; a Pfam conflict says
their domain architectures share no clan, which an HMM can get wrong by missing homology ESM sees.
One list would state a conflict as a grade.

⚠ **Fetched when the reader opens the list, not with the species.** At the probe scale both lists
are tens of loci; at the 80,000-genome design target they could be thousands, and a closed
`<details>` element is the wrong place to spend a first page load.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from syntitude_backend.models.locus import Locus

#: ⛔ **Vendored from `nuna.tl.locus_browser.export_payload.POLICY`** — the serving side must not
#: import `nuna`, a private repo the med-school server does not have. The tiers the audit counts
#: against a model (`failure_tiers`) and the Pfam verdict it calls contested (`contested_pfclass`).
#: `tests/test_page_shell_endpoints.py` asserts these equal nuna's own wherever nuna is installed,
#: because a copy that drifted would list a different set of loci from the one the report counted.
FAILURE_TIERS = ("synteny_only", "no_homology")
CONTESTED_PFAM_CLASS = "disjoint"


@dataclass(frozen=True)
class ResidualLocus:
    """One row of either list — enough evidence beside the name to judge it before clicking."""

    label: str
    display_name: str
    prevalence_band: str
    gene_count: int
    uniref50_family_count: int | None
    pfam_architecture_count: int | None
    syntenic_a5: float | None
    esm_within_medoid_distance: float | None
    esm_nearest_medoid_distance: float | None


@dataclass(frozen=True)
class AuditResiduals:
    """Both lists, each in catalogue order — the order the published footer listed them in."""

    grouped_on_context_alone: list[ResidualLocus]
    pfam_conflicts: list[ResidualLocus]


def load_audit_residuals(session: Session, *, pangenome_id: int) -> AuditResiduals:
    """Both residual lists, in ONE statement — the two sets overlap, so each row is read once."""
    rows = session.execute(
        select(
            Locus.node_label,
            Locus.display_name,
            Locus.prevalence_band,
            Locus.member_gene_count,
            Locus.uniref50_family_count,
            Locus.pfam_architecture_count,
            Locus.syntenic_a5,
            Locus.esm_within_medoid_distance,
            Locus.esm_nearest_medoid_distance,
            Locus.collapse_tier,
            Locus.pfam_concordance_class,
        )
        .where(
            Locus.pangenome_id == pangenome_id,
            or_(
                Locus.collapse_tier.in_(FAILURE_TIERS),
                Locus.pfam_concordance_class == CONTESTED_PFAM_CLASS,
            ),
        )
        .order_by(Locus.catalogue_ordinal)
    ).all()

    context_alone: list[ResidualLocus] = []
    conflicts: list[ResidualLocus] = []
    for row in rows:
        entry = ResidualLocus(
            label=row.node_label,
            display_name=row.display_name,
            prevalence_band=row.prevalence_band.value,
            gene_count=row.member_gene_count,
            uniref50_family_count=row.uniref50_family_count,
            # ⚠ `-1`/NULL means Pfam could not judge the locus — not "no architectures".
            pfam_architecture_count=(
                row.pfam_architecture_count
                if row.pfam_architecture_count is not None and row.pfam_architecture_count >= 0
                else None
            ),
            syntenic_a5=row.syntenic_a5,
            esm_within_medoid_distance=row.esm_within_medoid_distance,
            esm_nearest_medoid_distance=row.esm_nearest_medoid_distance,
        )
        if row.collapse_tier in FAILURE_TIERS:
            context_alone.append(entry)
        if row.pfam_concordance_class == CONTESTED_PFAM_CLASS:
            conflicts.append(entry)
    return AuditResiduals(grouped_on_context_alone=context_alone, pfam_conflicts=conflicts)
