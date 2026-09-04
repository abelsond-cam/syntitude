"""The two orderings the page reads and never computes — separation percentiles, and interest.

Both were single implementations already: `sepIndex` in `app.js`, `_interest`/`ranking` in
`render_page`. Moving them to ingest keeps them single and makes the landing locus a column behind a
verification gate rather than a render-time payload mutation — the mutation that shipped five days
of pages opening on locus 0.

⛔ **The percentile is a MIDRANK over MEASURABLE loci only — not over the catalogue.** The card
prints *"p12 of 12,104 loci"* and both halves of that sentence are assertions. Singletons have no
separation and must read *not measurable*, never `0.000`.

⚠ **Gate measurability on the GEOMETRY, never on the prevalence band.** On the published *E. coli*
catalogue the unmeasurable set is exactly the 5,427 loci of size 1, while `prevalence_band = RARE`
covers **5,458** — the extra 31 are paralogues inside one genome, which do have a measurable
separation. Gating on the band would blank 31 real measurements and nothing would say so.

⛔ **`interest_score` must be computed on the payload's ROUNDED values, not on full precision.**
`a5` ships at 4 decimal places and `resolved` at 3, and the score weights them `3e5` and `2e6`; a
difference in the fifth decimal of `a5` moves the score by 30, which is enough to swap two neighbours
in a ranking whose top four become the published example chips. Reproducing the ranking means
reproducing the rounding.

⚠ **Two things about `interest_score`'s sign, both of which read wrong at a glance.** `-1e12` is a
**sentinel** and not a score — 51 *E. coli* loci carry it, barred outright because a disjoint Pfam
architecture is evidence *against* the merge. And `(major − 1) × 2e6` makes **942** more loci
legitimately negative without being barred at all, so *"negative means barred"* is false.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: `render_page._interest`'s weights, named rather than repeated as literals.
WEIGHT_MAJOR_FAMILY = 2e6
WEIGHT_CORE_BAND = 2e6
WEIGHT_SOFT_CORE_BAND = 1.2e6
WEIGHT_DEPTH = 2e6
WEIGHT_CONCORDANCE = 1.5e6
WEIGHT_SYNTENY = 3e5
WEIGHT_SIZE_DIVISOR = 1e4

#: ⛔ A **sentinel**, not a score. `render_page._interest` returns it for a locus the showcase bars:
#: a contested Pfam architecture, or a collapse tier the audit grades as a failure. Such a locus stays
#: fully reachable by search, by a neighbour and from the footer lists — demoted, never hidden.
BARRED_SENTINEL = -1e12

#: The gene the page opens on when the catalogue has one (`render_page.LANDING_SYMBOL`).
LANDING_SYMBOL = "fimA"

#: How many example chips sit beside it.
EXAMPLE_COUNT = 4

#: The payload's own rounding, which the score must be computed through — see the module docstring.
SYNTENY_DECIMALS = 4
RESOLVED_DECIMALS = 3


def _round_or_none(value, decimals: int) -> float | None:
    if value is None:
        return None
    number = float(value)
    return None if math.isnan(number) else round(number, decimals)


@dataclass(frozen=True)
class SeparationIndex:
    """One representation's separations and their midrank percentiles."""

    #: `d_near − d_intra` per locus, `None` where either distance is absent.
    separation: list[float | None]
    #: The midrank in [0, 1] over the measurable loci, `None` where the separation is.
    percentile: list[float | None]
    #: ⭐ The denominator the card prints — *"of 12,104 loci"*. Its own assertion.
    measurable_count: int


def separation_index(
    within_distance: list[float | None], nearest_distance: list[float | None]
) -> SeparationIndex:
    """`app.js::sepIndex`, on DISTANCES — separation is `d_near − d_intra`, directly.

    ⚠ The page holds similarities and subtracts them the other way round; the two are the same
    number because `(1 − d_intra) − (1 − d_near) = d_near − d_intra`. Working in distances here
    avoids a round trip through `1 − x`, which at ESM's ~1e-5 median distance is where precision goes.
    """
    separation: list[float | None] = []
    measurable: list[float] = []
    for intra, near in zip(within_distance, nearest_distance, strict=True):
        if intra is None or near is None or math.isnan(intra) or math.isnan(near):
            separation.append(None)
            continue
        value = float(near) - float(intra)
        separation.append(value)
        measurable.append(value)

    ordered = sorted(measurable)
    count = len(ordered)
    percentile: list[float | None] = []
    for value in separation:
        if value is None or not count:
            percentile.append(None)
            continue
        # The midrank: the mean of the first and last positions this value could occupy, normalised.
        # ⚠ `bisect` over a sorted list is `sepIndex`'s two binary searches, exactly.
        low = _bisect_left(ordered, value)
        high = _bisect_right(ordered, value)
        percentile.append((low + high - 1) / 2 / (count - 1 or 1))
    return SeparationIndex(separation=separation, percentile=percentile, measurable_count=count)


def _bisect_left(ordered: list[float], value: float) -> int:
    import bisect

    return bisect.bisect_left(ordered, value)


def _bisect_right(ordered: list[float], value: float) -> int:
    import bisect

    return bisect.bisect_right(ordered, value)


def pfam_concordance(
    architecture_counts: list[list[int]],
    pfam_annotated_member_count: list[int | None],
    member_gene_count: list[int],
) -> list[float]:
    """`render_page._pfam_concordance` — the dominant architecture's share, **weighted by coverage**.

    ⛔ The weighting is the point. The dominant architecture's share of the *annotated* genes is 1.0
    whenever a locus has one annotated member, which would rank a locus with almost no Pfam coverage
    as strongly concordant. Scaling by `n_pfam / size` makes the term *how much corroboration there
    actually is* rather than *how uncontested the little there is happens to be*.
    """
    out = []
    for counts, covered, size in zip(
        architecture_counts, pfam_annotated_member_count, member_gene_count, strict=True
    ):
        total = sum(counts)
        share = (counts[0] / total) if total else 0.0
        weight = (covered / size) if (covered is not None and size) else 1.0
        out.append(share * weight)
    return out


@dataclass(frozen=True)
class InterestInputs:
    """Everything `_interest` reads for one locus, at the payload's own precision."""

    syntenic_a5: float | None
    uniref50_major_family_count: int
    collapse_tier: str | None
    resolved_threshold: float | None
    prevalence_band_index: int
    member_gene_count: int
    concordance: float
    pfam_concordance_class: str | None


def interest_score(row: InterestInputs, policy: dict) -> float:
    """`render_page._interest` — how much a locus demonstrates the point.

    Barred outright, not down-weighted, on two grounds, *"because the showcase is the first thing a
    stranger sees"*: a Pfam architecture the audit calls contested, and a collapse tier the audit
    grades as a failure.
    """
    if row.pfam_concordance_class == policy.get("contested_pfclass", "disjoint"):
        return BARRED_SENTINEL
    tier = row.collapse_tier or ""
    if tier in tuple(policy.get("failure_tiers", ())):
        return BARRED_SENTINEL

    if tier in tuple(policy.get("rescue_tiers", ("pfam_not_alignable", "esm_homology"))):
        # Never aligns at all, yet demonstrably homologous — the strongest case.
        depth = WEIGHT_DEPTH
    elif row.resolved_threshold is not None:
        depth = WEIGHT_DEPTH * (1.0 - row.resolved_threshold)
    else:
        depth = 0.0

    band = row.prevalence_band_index
    core = WEIGHT_CORE_BAND if band == 0 else (WEIGHT_SOFT_CORE_BAND if band == 1 else 0.0)
    a5 = row.syntenic_a5 or 0.0
    return (
        (row.uniref50_major_family_count - 1) * WEIGHT_MAJOR_FAMILY
        + core
        + depth
        + WEIGHT_CONCORDANCE * row.concordance
        + WEIGHT_SYNTENY * a5
        + row.member_gene_count / WEIGHT_SIZE_DIVISOR
    )


def build_interest_inputs(
    *,
    syntenic_a5: list[float | None],
    uniref50_major_family_count: list[int],
    collapse_tier: list[str | None],
    resolved_threshold: list[float | None],
    prevalence_band_index: list[int],
    member_gene_count: list[int],
    concordance: list[float],
    pfam_concordance_class: list[str | None],
) -> list[InterestInputs]:
    """Assemble the per-locus inputs, applying the payload's rounding — see the module docstring."""
    return [
        InterestInputs(
            syntenic_a5=_round_or_none(a5, SYNTENY_DECIMALS),
            uniref50_major_family_count=int(major),
            collapse_tier=tier,
            resolved_threshold=_round_or_none(resolved, RESOLVED_DECIMALS),
            prevalence_band_index=int(band),
            member_gene_count=int(size),
            concordance=float(concord),
            pfam_concordance_class=verdict,
        )
        for a5, major, tier, resolved, band, size, concord, verdict in zip(
            syntenic_a5,
            uniref50_major_family_count,
            collapse_tier,
            resolved_threshold,
            prevalence_band_index,
            member_gene_count,
            concordance,
            pfam_concordance_class,
            strict=True,
        )
    ]


def ranking(scores: list[float]) -> list[int]:
    """Every locus, most demonstrative first — `render_page.ranking`'s single ordering.

    ⚠ Stable, and it must be: ties keep ascending catalogue order in both languages (Python's sort
    always; JavaScript's since ES2019), and the top four become the published example chips.
    """
    return sorted(range(len(scores)), key=lambda index: -scores[index])


def landing_index(order: list[int], modal_symbols: list[str | None]) -> int:
    """`render_page.landing` — the best-ranked `LANDING_SYMBOL`, else the ranking's own first.

    ⭐ It only ever FILTERS the ranking, so the showcase and the chips stay one scoring rule and a
    preferred gene cannot smuggle in a locus the ranking bars outright. On the published catalogues
    the preference actually fires: *E. coli* opens on 2811 and kp on 1098, neither its `examples[0]`.
    """
    wanted = LANDING_SYMBOL.lower()
    for index in order:
        symbol = modal_symbols[index]
        if symbol and str(symbol).lower() == wanted:
            return index
    return order[0] if order else 0
