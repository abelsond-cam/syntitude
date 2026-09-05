"""One locus, whole — the hot path, and the fan-out it exists to fix.

⭐ **Rendering one locus touches a median 15–19 other loci and up to 303**, because a neighbour's
*name* is a transitive read through its Pfam and product lists. `display_name` and `best_product` are
materialised at ingest, so that read becomes `WHERE locus_id = ANY($1)` over ~20 ids: **one index
scan, in the same round trip**, carried as `neighbour_display_rows`.

⛔ **The statement count must not grow with the neighbour count.** That is the property worth
asserting, and it is what a naive implementation breaks: fetching each neighbour's name on demand is
15–19 round trips typically and 303 at worst, every one of them correct. A per-request budget of "4"
would be a number to satisfy rather than a property to hold — this module issues **one statement per
table the response draws from**, and the cost oracle asserts that against the tables, not a snapshot.

⛔ **`occ(code)` is deleted.** A slot is `null` plus an explicit `absence_reason`, never a bare `-1`:
that packed form is exactly where the "−1 means five different things" trap lives.

⚠ **The four remainders stay four.** `observed − listed` is a *display* cut; `size − observed` is
*missing data* (contig ends); `total − listed` is arrangements not drawn; `size − listed` is members
with no recorded neighbourhood. A rewrite that computes "the rest" once collapses them, and the page
starts making a claim it cannot support.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from syntitude_backend.models.enumerations import AnnotationKind
from syntitude_backend.models.intergenic_gap import IntergenicGap
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.locus_annotation import LocusAnnotationEntry, LocusUnirefFamilyCrosstab
from syntitude_backend.models.locus_arrangement import LocusArrangement
from syntitude_backend.models.locus_embedding_geometry import LocusEmbeddingGeometry
from syntitude_backend.models.locus_offset_occupant import LocusOffsetOccupant

#: The signed offsets, in display order. ⛔ `0` is absent — it is the focal locus.
SIGNED_OFFSETS = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)

#: How many arrangements a locus response carries before the reader must page.
#: ⚠ `total_arrangement_count` always ships separately, and the anchored genome's arrangement is
#: offered even past this cap — *"otherwise the reader is told in words that their genome sits in #37
#: and has no button to go back to it"*.
ARRANGEMENT_PAGE_SIZE = 8

#: `LocusAnnotationEntry` kinds that belong to the **function** tab and are fetched on tab open, not
#: on every walk. Splitting them is what keeps the hot path ~14 kB.
FUNCTION_ANNOTATION_KINDS = (
    AnnotationKind.COG_ORTHOGROUP,
    AnnotationKind.GENE_ONTOLOGY_SLIM,
    AnnotationKind.EC_NUMBER,
    AnnotationKind.KEGG_ORTHOLOGY,
)

#: The kinds the locus card itself shows.
CARD_ANNOTATION_KINDS = (
    AnnotationKind.GENE_SYMBOL,
    AnnotationKind.PROTEIN_PRODUCT,
    AnnotationKind.PFAM_ARCHITECTURE,
)


class LocusNotFound(LookupError):
    """No locus with that label in this species' published pangenome."""


@dataclass
class NeighbourDisplayRow:
    """Everything the track needs to DRAW a neighbour block, without a second request.

    ⚠ Three fields, and each is needed for a different part of the block: the name is its label, the
    genome count sets its alpha, and the median length sets its width (`max(6, len_nt / 10)` px).
    """

    locus_id: int
    node_label: str
    display_name: str
    display_name_source: str
    member_genome_count: int
    median_gene_length_nt: int | None
    prevalence_band: str


@dataclass
class NeighbourDisplayIndex:
    """The neighbour rows, addressed BOTH ways and never in one dict.

    ⛔ `by_locus_id` and `by_catalogue_ordinal` are different key spaces over the same small
    integers. Merging them is the mistake this type exists to make unwriteable.
    """

    by_locus_id: dict = field(default_factory=dict)
    by_catalogue_ordinal: dict = field(default_factory=dict)

    def all_rows(self) -> list:
        """Every distinct row, for a serialiser that wants to emit the block once."""
        return list({row.locus_id: row for row in self.by_locus_id.values()}.values())


@dataclass
class LocusDetail:
    """One locus and everything a walk step needs, in one response."""

    locus: Locus
    card_annotations: dict = field(default_factory=dict)
    uniref_families: list = field(default_factory=list)
    arrangements: list = field(default_factory=list)
    arrangements_listed: int = 0
    offset_occupants: dict = field(default_factory=dict)
    neighbour_display_rows: NeighbourDisplayIndex = field(default_factory=NeighbourDisplayIndex)
    intergenic_gaps: list = field(default_factory=list)
    geometry: dict = field(default_factory=dict)
    #: ⭐ How many DISTINCT other loci this response resolved. The fan-out, measured per request.
    resolved_neighbour_count: int = 0
    #: ⛔ Which arrangement RANKS the anchored genome carries here — a **list**, because a genome at
    #: rho > 1 occupies two arrangements at one locus and there is no uniqueness constraint on
    #: (locus, genome) anywhere. Empty when there is no anchor, or when the anchored genome has no
    #: gene at this locus; those two are distinguished by `anchor_genome_id` being set at all.
    anchor_arrangement_ranks: list[int] = field(default_factory=list)
    #: Whether a genome was anchored at all. ⚠ Distinguishes "no anchor set" from "anchored, and
    #: this genome has no gene at this locus" — an empty rank list means the second only when this
    #: is true, and the two are different sentences on the page.
    is_anchored: bool = False


def _locus_by_label(session: Session, pangenome_id: int, node_label: str) -> Locus:
    locus = session.execute(
        select(Locus).where(Locus.pangenome_id == pangenome_id, Locus.node_label == node_label)
    ).scalar_one_or_none()
    if locus is None:
        raise LocusNotFound(
            f"no locus {node_label!r} in pangenome {pangenome_id}. ⚠ Node labels are TEXT — "
            "`0123` and `123` are different loci, and a numeric round-trip loses the distinction."
        )
    return locus


def load_locus_detail(
    session: Session,
    *,
    pangenome_id: int,
    node_label: str,
    anchor_genome_id: int | None = None,
    arrangement_limit: int = ARRANGEMENT_PAGE_SIZE,
) -> LocusDetail:
    """The whole locus view. One statement per table, and none of them per neighbour."""
    locus = _locus_by_label(session, pangenome_id, node_label)
    detail = LocusDetail(locus=locus)

    # ── the card's own lists ───────────────────────────────────────────────────────────────────
    entries = session.execute(
        select(LocusAnnotationEntry)
        .where(
            LocusAnnotationEntry.locus_id == locus.locus_id,
            LocusAnnotationEntry.annotation_kind.in_(CARD_ANNOTATION_KINDS),
        )
        .order_by(LocusAnnotationEntry.annotation_kind, LocusAnnotationEntry.rank_within_locus)
    ).scalars()
    for entry in entries:
        detail.card_annotations.setdefault(entry.annotation_kind.value, []).append(entry)

    detail.uniref_families = list(
        session.execute(
            select(LocusUnirefFamilyCrosstab)
            .where(LocusUnirefFamilyCrosstab.locus_id == locus.locus_id)
            .order_by(LocusUnirefFamilyCrosstab.rank_within_locus)
        ).scalars()
    )

    # ── the joint view, capped, plus whichever the anchored genome carries ─────────────────────
    # ⭐ `member_genome_ids @> ARRAY[?]` is the GIN index doing the work a binary search over a
    # ~490k-entry Int32Array did in the browser. The OR is what honours `arrShown`'s rule.
    condition = LocusArrangement.rank_within_locus < arrangement_limit
    if anchor_genome_id is not None:
        condition = or_(condition, LocusArrangement.member_genome_ids.contains([anchor_genome_id]))
    detail.arrangements = list(
        session.execute(
            select(LocusArrangement)
            .where(LocusArrangement.locus_id == locus.locus_id, condition)
            .order_by(LocusArrangement.rank_within_locus)
        ).scalars()
    )
    detail.arrangements_listed = len(detail.arrangements)
    detail.is_anchored = anchor_genome_id is not None
    if anchor_genome_id is not None:
        # ⛔ Recomputed from the rows rather than inferred from the OR above: the anchored genome's
        # arrangement may ALSO be within the cap, in which case the OR added nothing and a client
        # that assumed "the last one" would mark the wrong row. And it is a list, not a scalar —
        # see `anchor_arrangement_ranks`.
        detail.anchor_arrangement_ranks = [
            arrangement.rank_within_locus
            for arrangement in detail.arrangements
            if anchor_genome_id in (arrangement.member_genome_ids or ())
        ]

    # ── the marginal view ──────────────────────────────────────────────────────────────────────
    occupants = session.execute(
        select(LocusOffsetOccupant)
        .where(LocusOffsetOccupant.locus_id == locus.locus_id)
        .order_by(LocusOffsetOccupant.signed_offset, LocusOffsetOccupant.rank_within_offset)
    ).scalars()
    for occupant in occupants:
        detail.offset_occupants.setdefault(occupant.signed_offset, []).append(occupant)

    # ── the fan-out, resolved in ONE statement ─────────────────────────────────────────────────
    # ⛔⛔ **TWO DIFFERENT INTEGER SPACES, KEPT APART.** `locus_offset_occupant.neighbour_locus_id`
    # is a surrogate `locus_id`; an arrangement slot code carries a **catalogue ordinal**
    # (`code // 2`). Both are small integers over the same range, so locus_id 5 and ordinal 5 are
    # different loci and a single lookup keyed by "the number" silently draws one on the other —
    # with a page that still looks entirely correct. They are collected separately and returned
    # separately, so a caller has to say which address it is holding.
    neighbour_locus_ids = {
        occupant.neighbour_locus_id
        for rows in detail.offset_occupants.values()
        for occupant in rows
    }
    neighbour_ordinals = {
        code // 2
        for arrangement in detail.arrangements
        for code in arrangement.neighbour_slot_codes
        if code >= 0
    }
    detail.neighbour_display_rows = _neighbour_display_rows(
        session,
        pangenome_id=pangenome_id,
        locus_ids=neighbour_locus_ids,
        catalogue_ordinals=neighbour_ordinals,
        focal_locus=locus,
    )
    detail.resolved_neighbour_count = len(
        {row.locus_id for row in detail.neighbour_display_rows.by_locus_id.values()}
    )

    # ── the gaps this locus can be an endpoint of ──────────────────────────────────────────────
    # ⛔ BOTH columns, because the canonical order is by node_label and a caller holding a locus_id
    # cannot tell which side it is on without resolving the labels.
    detail.intergenic_gaps = list(
        session.execute(
            select(IntergenicGap).where(
                IntergenicGap.pangenome_id == pangenome_id,
                or_(
                    IntergenicGap.flanking_locus_id_a == locus.locus_id,
                    IntergenicGap.flanking_locus_id_b == locus.locus_id,
                ),
            )
        ).scalars()
    )

    # ── the six-point geometry, both representations ───────────────────────────────────────────
    for geometry in session.execute(
        select(LocusEmbeddingGeometry).where(LocusEmbeddingGeometry.locus_id == locus.locus_id)
    ).scalars():
        detail.geometry[geometry.representation.value] = geometry
    return detail


def _neighbour_display_rows(
    session: Session,
    *,
    pangenome_id: int,
    locus_ids: set[int],
    catalogue_ordinals: set[int],
    focal_locus: Locus,
) -> NeighbourDisplayIndex:
    """Every locus this response refers to, by either address — **one statement, always**."""
    index = NeighbourDisplayIndex()
    if not locus_ids and not catalogue_ordinals:
        return index
    rows = session.execute(
        select(
            Locus.locus_id,
            Locus.catalogue_ordinal,
            Locus.node_label,
            Locus.display_name,
            Locus.display_name_source,
            Locus.member_genome_count,
            Locus.median_gene_length_nt,
            Locus.prevalence_band,
        ).where(
            Locus.pangenome_id == pangenome_id,
            or_(Locus.locus_id.in_(locus_ids), Locus.catalogue_ordinal.in_(locus_ids)),
        )
    ).all()
    for locus_id, ordinal, label, name, source, genomes, length, band in rows:
        row = NeighbourDisplayRow(
            locus_id=locus_id,
            node_label=label,
            display_name=name,
            display_name_source=source,
            member_genome_count=genomes,
            median_gene_length_nt=length,
            prevalence_band=band.value,
        )
        if locus_id in locus_ids:
            index.by_locus_id[locus_id] = row
        if ordinal in catalogue_ordinals:
            index.by_catalogue_ordinal[ordinal] = row
    # ⚠ The focal locus is its own neighbour on a tandem repeat (hokE, ldrB, zorO …) — a real case
    # and not a degenerate one, so it is always resolvable from its own response.
    focal = NeighbourDisplayRow(
        locus_id=focal_locus.locus_id,
        node_label=focal_locus.node_label,
        display_name=focal_locus.display_name,
        display_name_source=focal_locus.display_name_source,
        member_genome_count=focal_locus.member_genome_count,
        median_gene_length_nt=focal_locus.median_gene_length_nt,
        prevalence_band=focal_locus.prevalence_band.value,
    )
    index.by_locus_id.setdefault(focal_locus.locus_id, focal)
    index.by_catalogue_ordinal.setdefault(focal_locus.catalogue_ordinal, focal)
    return index


def load_function_block(session: Session, *, locus_id: int) -> dict:
    """The EggNOG tab — fetched on tab open, not on every walk. One statement."""
    entries = session.execute(
        select(LocusAnnotationEntry)
        .where(
            LocusAnnotationEntry.locus_id == locus_id,
            LocusAnnotationEntry.annotation_kind.in_(FUNCTION_ANNOTATION_KINDS),
        )
        .order_by(
            LocusAnnotationEntry.annotation_kind,
            LocusAnnotationEntry.gene_ontology_namespace,
            LocusAnnotationEntry.rank_within_locus,
        )
    ).scalars()
    grouped: dict[str, list] = {}
    for entry in entries:
        grouped.setdefault(entry.annotation_kind.value, []).append(entry)
    return grouped


def load_arrangement_page(
    session: Session, *, locus_id: int, offset: int = 0, limit: int = 50
) -> list[LocusArrangement]:
    """Arrangements past the display cut — the full scroller, paged. One statement."""
    return list(
        session.execute(
            select(LocusArrangement)
            .where(LocusArrangement.locus_id == locus_id)
            .order_by(LocusArrangement.rank_within_locus)
            .offset(offset)
            .limit(limit)
        ).scalars()
    )


def resolve_cosine_matrix(geometry: LocusEmbeddingGeometry, scale_factor: int) -> list[list[float | None]]:
    """The 15 stored upper-triangle values → a full 6×6 matrix, `-1` slot-drops already applied.

    ⛔ **Slots are not ranks.** A `-1` in `nearest_locus_ordinals` drops that locus AND its slot; the
    surviving slot indices are what address the triangle. Reading by rank instead draws one locus's
    distances on another — and the picture still looks like a picture. Resolving it server-side
    retires that two-sided contract entirely.
    """
    pairs = [(a, b) for a in range(6) for b in range(a + 1, 6)]
    matrix: list[list[float | None]] = [[None] * 6 for _ in range(6)]
    for index in range(6):
        matrix[index][index] = 1.0
    present = {0, *(slot + 1 for slot, value in enumerate(geometry.nearest_locus_ordinals) if value >= 0)}
    for (a, b), scaled in zip(pairs, geometry.pairwise_cosine_scaled, strict=True):
        if a in present and b in present:
            matrix[a][b] = matrix[b][a] = scaled / scale_factor
    return matrix
