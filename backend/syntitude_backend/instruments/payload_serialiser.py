"""Rebuild the published locus-browser payload from the database.

⭐⭐ **This is an instrument, not an endpoint.** The API serves its own, better shape — nulls with a
named ``absence_reason``, a resolved 6×6 cosine matrix, four separately named remainders. This
module exists to prove a different claim: that the database is a **lossless superset** of the JSON
catalogue the static site ships, checked against the real 17,531-locus payload rather than asserted.
Once that holds, the static site can be retired knowing nothing on it was lost.

⛔⛔ **EMISSION ORDER IS THE WHOLE PROBLEM.** ``_Intern`` assigns a string its index *on first use*,
so the pools in ``strings`` are in whatever order ``build_payload`` walked the data. Emit the same
strings in a different order and the payload is **correct and not identical** — every ``idx`` column
differs and a column-wise diff reports the catalogue changed. The order is therefore not a detail of
this file, it is its contract:

1. ``nodes`` first, **column by column in payload order**, because its dict literal is what interns
   ``name`` → ``tier`` → ``pfclass`` → ``cog_cat`` → ``go_0/1/2``;
2. then the ``lists`` loop, in ``build_payload``'s own order: sym, prod, u50, pfam, cog, ec, kegg, go;
3. then the ``u50`` **second pass**, which adds to ``prod``, ``pfam`` and ``sym`` — three pools that
   already have entries.

⭐ **The order is checked, not trusted.** :func:`build_payload_from_database` runs
:func:`verify_intern_walk` over its own output before returning, so a wrong emission order raises
here — with the pool and the column named — instead of surfacing later as thousands of changed
indices in a diff nobody can read.

⚠ **Every value is READ, never recomputed.** The ingest wrote the float columns through the
payload's own ``_floats``/``_sigfigs`` helpers, so ``locus.syntenic_a5`` already *is* ``nodes.a5``.
Re-rounding a stored value would risk double rounding; re-deriving one would risk disagreeing with
the report, which is the mistake ``pfam_concordance_class`` exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from syntitude_backend.instruments.payload_string_pool import StringPool
from syntitude_backend.models.locus import Locus


def _payload_constants():
    """The constants `build_payload` itself used, imported rather than copied — code, not a memory."""
    from nuna.tl.locus_browser.export_payload import (
        BAND_ORDER,
        NS_CODE,
        OFFSETS,
        POLICY,
        SCHEMA_VERSION,
    )

    return SCHEMA_VERSION, tuple(OFFSETS), tuple(BAND_ORDER), dict(NS_CODE), POLICY


@dataclass
class CataloguePools:
    """The eleven ``strings`` pools, shared across blocks — which is why order is global, not local.

    ⚠ ``cog`` is one pool holding **two vocabularies**: ``nodes.cog_cat`` writes Bakta category
    strings into it, and ``lists.cog.idx`` then writes COG *ids*. That is not a bug to tidy; it is
    how every published catalogue was interned.
    """

    sym: StringPool = field(default_factory=StringPool)
    prod: StringPool = field(default_factory=StringPool)
    u50: StringPool = field(default_factory=StringPool)
    pfam: StringPool = field(default_factory=StringPool)
    tier: StringPool = field(default_factory=StringPool)
    pfclass: StringPool = field(default_factory=StringPool)
    cog: StringPool = field(default_factory=StringPool)
    go: StringPool = field(default_factory=StringPool)
    ec: StringPool = field(default_factory=StringPool)
    kegg: StringPool = field(default_factory=StringPool)
    goclass: StringPool = field(default_factory=StringPool)

    def tables(self) -> dict[str, list[str]]:
        """The ``strings`` block — the pools as they stand after every block has been emitted."""
        return {name: getattr(self, name).values for name in self.__dataclass_fields__}


def _enum_value(value) -> str | None:
    """An enum's payload spelling, or ``None`` — the DB stores enums, the payload stores strings."""
    return None if value is None else getattr(value, "value", value)


def load_catalogue_loci(session: Session, pangenome_id: int) -> list[Locus]:
    """Every locus of one pangenome, **in catalogue order**.

    ⛔ ``catalogue_ordinal`` is a stored ordinal, not a sort of convenience: it is the payload's own
    array index, written once at ingest from ``node_order``. Ordering by anything else — the label,
    the id, the size — produces a different catalogue that is internally consistent and wrong,
    because every ``nid``, ``near``, ``a``/``b`` and ``failures`` entry addresses this order.
    """
    loci = list(
        session.execute(
            select(Locus)
            .where(Locus.pangenome_id == pangenome_id)
            .order_by(Locus.catalogue_ordinal)
        ).scalars()
    )
    expected = list(range(len(loci)))
    actual = [locus.catalogue_ordinal for locus in loci]
    if actual != expected:
        # A hole or a duplicate here shifts every downstream index by one and nothing else notices.
        raise ValueError(
            f"pangenome {pangenome_id} has {len(loci):,} loci whose catalogue_ordinal is not "
            f"0…{len(loci) - 1:,} — the payload's array index cannot be reconstructed"
        )
    return loci


def node_block(loci: list[Locus], pools: CataloguePools) -> dict[str, list]:
    """The ``nodes`` block — **built column by column, in the payload's own column order**.

    ⛔ The order of the statements below is load-bearing. ``build_payload``'s ``node_block`` is a
    dict literal, evaluated top to bottom, and each interning column writes into a shared pool as it
    is evaluated. Reordering these lines reorders ``strings.sym``, ``strings.tier``,
    ``strings.pfclass``, ``strings.cog`` and ``strings.goclass`` — and therefore every index that
    addresses them.

    ⚠ ``len_nt`` and ``len_iqr`` are APPENDED at the end, never inserted: the invariance check reads
    ``nodes`` by position, so a column slipped into the middle makes every prior payload look
    different for no reason.
    """
    _, _, band_order, namespace_codes, _ = _payload_constants()
    block: dict[str, list] = {
        "label": [locus.node_label for locus in loci],
        "size": [locus.member_gene_count for locus in loci],
        "genomes": [locus.member_genome_count for locus in loci],
        "band": [band_order.index(_enum_value(locus.prevalence_band)) for locus in loci],
        "name": pools.sym.indices(locus.bakta_gene_symbol for locus in loci),
        "n_named": [locus.named_member_count for locus in loci],
        "n_u50": [locus.uniref50_family_count for locus in loci],
        "n_u50_major": [locus.uniref50_major_family_count for locus in loci],
        "n_u50_labelled": [locus.uniref50_labelled_member_count for locus in loci],
        "n_pfam": [locus.pfam_annotated_member_count for locus in loci],
        "a5": [locus.syntenic_a5 for locus in loci],
        "tier": pools.tier.indices(locus.collapse_tier for locus in loci),
        "pfclass": pools.pfclass.indices(locus.pfam_concordance_class for locus in loci),
        # ⚠ -1, not null: `_Intern` never saw this column — `build_payload` wrote the sentinel itself.
        "n_arch": [-1 if locus.pfam_architecture_count is None else locus.pfam_architecture_count for locus in loci],
        "resolved": [locus.resolved_threshold for locus in loci],
        "esm_d_intra": [locus.esm_within_medoid_distance for locus in loci],
        "esm_d_near": [locus.esm_nearest_medoid_distance for locus in loci],
        "bac_d_intra": [locus.bacformer_within_medoid_distance for locus in loci],
        "bac_d_near": [locus.bacformer_nearest_medoid_distance for locus in loci],
        "n_cog": [locus.cog_annotated_member_count for locus in loci],
        "cog_n": [locus.cog_distinct_id_count for locus in loci],
        # ⛔ Bakta writes a SET of COG categories as a letter run (`MV`, `KG`, `DN`), which the
        # schema stores as an array so it can be queried by letter. The payload carries the run, so
        # the join must preserve the stored order — the array is not a set to be sorted.
        "cog_cat": pools.cog.indices(
            None if not locus.modal_cog_categories else "".join(locus.modal_cog_categories)
            for locus in loci
        ),
        "n_ec": [locus.ec_annotated_member_count for locus in loci],
        "n_kegg": [locus.kegg_annotated_member_count for locus in loci],
    }
    # The GO verdicts and their coverage counts, per namespace — the verdict NEVER without the
    # count, because a list of labels cannot say whether members disagreed or were never annotated.
    for namespace, code in namespace_codes.items():
        block[f"go_{code}"] = pools.goclass.indices(
            _enum_value(getattr(locus, f"go_verdict_{namespace}")) for locus in loci
        )
    for namespace, code in namespace_codes.items():
        block[f"n_go_{code}"] = [
            getattr(locus, f"go_annotated_member_count_{namespace}") for locus in loci
        ]
    block["len_nt"] = [locus.median_gene_length_nt for locus in loci]
    block["len_iqr"] = [locus.gene_length_interquartile_range_nt for locus in loci]
    return block


#: ⛔⛔ **The order ``build_payload`` interns the vocabularies in — NOT the order it emits them.**
#: Its `for f, col, pool in (...)` loop runs before the `lists` dict literal is assembled, so the
#: pools are filled in *this* sequence while the emitted block happens to share it. They are two
#: different facts that agree today; this constant is the one that matters, and `u50` sitting third
#: rather than last is exactly the kind of detail a "tidy" alphabetical rewrite would destroy.
LIST_INTERN_ORDER: tuple[tuple[str, str], ...] = (
    ("sym", "GENE_SYMBOL"),
    ("prod", "PROTEIN_PRODUCT"),
    ("u50", "__crosstab__"),
    ("pfam", "PFAM_ARCHITECTURE"),
    ("cog", "COG_ORTHOGROUP"),
    ("ec", "EC_NUMBER"),
    ("kegg", "KEGG_ORTHOLOGY"),
    ("go", "GENE_ONTOLOGY_SLIM"),
)


def _run_lengths(per_locus: dict[int, list], n_loci: int, columns: dict[str, list]) -> dict:
    """A per-locus variable-length list as ``{"n": [...], <col>: [...]}`` — run lengths, not offsets.

    ⛔ ``n`` is length ``n_loci`` and carries a **zero for every locus with no entries**. A block
    listing only the loci that have something is a different, shorter array that silently
    misaligns every prefix sum after the first gap.
    """
    return {"n": [len(per_locus.get(index, ())) for index in range(n_loci)], **columns}


def annotation_rows(session: Session, pangenome_id: int) -> dict[str, list]:
    """Every annotation entry, grouped by list key, **in the payload's own row order**.

    ⛔ Two different orders, and using one for the other breaks the run lengths silently:

    * six vocabularies rank **within a locus** → ``(catalogue_ordinal, rank)``;
    * GO ranks within **(locus, namespace)** → ``(catalogue_ordinal, namespace, rank)``.

    ``build_payload`` uses `_ordered` for the first and `_ordered_ns` for the second, and its own
    comment says why: *"`top_go` ranks within (locus, namespace), so it sorts on namespace too or
    the run lengths break."*
    """
    from syntitude_backend.models.locus_annotation import LocusAnnotationEntry

    rows = session.execute(
        select(LocusAnnotationEntry, Locus.catalogue_ordinal)
        .join(Locus, Locus.locus_id == LocusAnnotationEntry.locus_id)
        .where(Locus.pangenome_id == pangenome_id)
        .order_by(
            Locus.catalogue_ordinal,
            LocusAnnotationEntry.gene_ontology_namespace.nulls_first(),
            LocusAnnotationEntry.rank_within_locus,
        )
    ).all()
    grouped: dict[str, list] = {}
    for entry, ordinal in rows:
        grouped.setdefault(entry.annotation_kind.name, []).append((ordinal, entry))
    return grouped


def uniref_crosstab_rows(session: Session, pangenome_id: int) -> list:
    """The UniRef50 cross-tab in ``(catalogue_ordinal, rank)`` order — the payload's ``lists.u50``."""
    from syntitude_backend.models.locus_annotation import LocusUnirefFamilyCrosstab

    return session.execute(
        select(LocusUnirefFamilyCrosstab, Locus.catalogue_ordinal)
        .join(Locus, Locus.locus_id == LocusUnirefFamilyCrosstab.locus_id)
        .where(Locus.pangenome_id == pangenome_id)
        .order_by(Locus.catalogue_ordinal, LocusUnirefFamilyCrosstab.rank_within_locus)
    ).all()


def list_block(session: Session, pangenome_id: int, n_loci: int, pools: CataloguePools) -> dict:
    """The whole ``lists`` block, interned in :data:`LIST_INTERN_ORDER`.

    ⚠ ``u50``'s five extra columns split two ways, and the split is the absence rule:
    ``prod``/``arch``/``sym`` are **pool indices**, so a missing value is ``-1``; ``npf``/``nsym``
    are **counts**, so a missing value is ``0``. Emitting ``-1`` for a count would make "no Pfam
    coverage" sort below zero, and emitting ``0`` for an index would name the pool's first string.
    """
    grouped = annotation_rows(session, pangenome_id)
    crosstab = uniref_crosstab_rows(session, pangenome_id)
    per_locus_crosstab: dict[int, list] = {}
    for family, ordinal in crosstab:
        per_locus_crosstab.setdefault(ordinal, []).append(family)

    interned: dict[str, list[int]] = {}
    for key, kind in LIST_INTERN_ORDER:
        pool = getattr(pools, key)
        if kind == "__crosstab__":
            interned[key] = pool.indices(family.uniref50_accession for family, _ in crosstab)
        else:
            interned[key] = pool.indices(entry.term_value for _, entry in grouped.get(kind, ()))

    # ⛔ The SECOND pass over the cross-tab, and it must come after every list above: it adds to
    # `prod`, `pfam` and `sym`, three pools that already hold entries. Running it earlier changes
    # three pools and every index into them.
    crosstab_product = pools.prod.indices(family.modal_bakta_product for family, _ in crosstab)
    crosstab_architecture = pools.pfam.indices(family.modal_pfam_architecture for family, _ in crosstab)
    crosstab_symbol = pools.sym.indices(family.modal_bakta_gene_symbol for family, _ in crosstab)

    def _grouped_lengths(kind: str) -> dict[int, list]:
        per_locus: dict[int, list] = {}
        for ordinal, entry in grouped.get(kind, ()):
            per_locus.setdefault(ordinal, []).append(entry)
        return per_locus

    block: dict[str, dict] = {}
    for key, kind in LIST_INTERN_ORDER:
        if kind == "__crosstab__":
            continue
        entries = grouped.get(kind, ())
        columns = {
            "idx": interned[key],
            "cnt": [entry.member_gene_count for _, entry in entries],
        }
        if key == "go":
            # GO carries its namespace per entry, so one list serves all three groups.
            columns["ns"] = [entry.gene_ontology_namespace for _, entry in entries]
        block[key] = _run_lengths(_grouped_lengths(kind), n_loci, columns)

    block["u50"] = _run_lengths(
        per_locus_crosstab,
        n_loci,
        {
            "idx": interned["u50"],
            "cnt": [family.member_gene_count for family, _ in crosstab],
            "prod": crosstab_product,
            "arch": crosstab_architecture,
            "npf": [family.pfam_annotated_member_count or 0 for family, _ in crosstab],
            "sym": crosstab_symbol,
            "nsym": [family.distinct_real_symbol_count or 0 for family, _ in crosstab],
        },
    )
    # Emitted in the payload's own key order, which is NOT the interning order above.
    return {key: block[key] for key in ("sym", "prod", "u50", "pfam", "cog", "ec", "kegg", "go")}


def genome_ordinal_map(session: Session, pangenome_id: int) -> dict[int, int]:
    """``genome_id`` → ``collection_genome_ordinal`` — the index ``arr.gid`` actually holds.

    ⛔⛔ **The schema stores a foreign key; the payload stores a position.** ``member_genome_ids``
    holds real ``genome_id`` values, which is right — a column of positions could not be joined to
    anything, and the ordinal is a property of the *collection*, not of the genome. But ``arr.gid``
    indexes into ``meta.genomes``, so the two are different integers over the same objects and
    reading one as the other silently names the wrong genome throughout: at 100 genomes both are
    small integers, both are in range, and every page renders.
    """
    from syntitude_backend.models.genome_collection import GenomeCollectionMembership
    from syntitude_backend.models.pangenome import Pangenome

    collection_id = session.execute(
        select(Pangenome.genome_collection_id).where(Pangenome.pangenome_id == pangenome_id)
    ).scalar_one()
    rows = session.execute(
        select(
            GenomeCollectionMembership.genome_id,
            GenomeCollectionMembership.collection_genome_ordinal,
        ).where(GenomeCollectionMembership.genome_collection_id == collection_id)
    ).all()
    ordinals = {genome_id: ordinal for genome_id, ordinal in rows}
    if sorted(ordinals.values()) != list(range(len(ordinals))):
        raise ValueError(
            f"collection {collection_id} has {len(ordinals):,} members whose ordinals are not "
            f"0…{len(ordinals) - 1} — every arr.gid would name the wrong genome"
        )
    return ordinals


def arrangement_block(session: Session, pangenome_id: int, loci: list[Locus]) -> dict:
    """The ``arr`` block — the **joint** view: whole ±5 neighbourhoods, and who carries each.

    ⛔ ``tot`` is read from ``locus.total_arrangement_count``, **not counted from the rows**. It is
    the TRUE total and the listed count is whatever the export cap admitted; conflating them is
    what lets a capped payload claim a locus has four neighbourhoods when it has thirty-seven.
    (The published catalogues happen to be uncapped — ``meta.top_arrangements`` is 0 and
    ``n == tot`` on all 33,201 loci — which is exactly why reading `tot` from a count would pass
    here and fail on the first capped export.)

    ⚠ ``gid`` rides on ``gen``: run *j* is exactly ``gen[j]`` long, concatenated in the same row
    order. Asserted before returning, because a mismatch makes the page read every arrangement's
    membership from the wrong offset — and every genome name it then shows is a real genome.
    """
    from syntitude_backend.models.locus_arrangement import LocusArrangement

    rows = session.execute(
        select(LocusArrangement, Locus.catalogue_ordinal)
        .join(Locus, Locus.locus_id == LocusArrangement.locus_id)
        .where(Locus.pangenome_id == pangenome_id)
        .order_by(Locus.catalogue_ordinal, LocusArrangement.rank_within_locus)
    ).all()

    ordinal_of_genome_id = genome_ordinal_map(session, pangenome_id)
    counts = [0] * len(loci)
    genes, genomes, flips, vectors, members = [], [], [], [], []
    for arrangement, ordinal in rows:
        counts[ordinal] += 1
        genes.append(arrangement.member_gene_count)
        genomes.append(arrangement.member_genome_count)
        # ⚠ The payload stores an int, not a bool — `flip` is emitted through `_ints`.
        flips.append(int(arrangement.is_recorded_reverse_complement))
        vectors.extend(arrangement.neighbour_slot_codes)
        # ⚠ Sorted by ORDINAL, not by genome_id. Both are ascending in the published catalogues
        # because ingest happened to assign ids in accession order, so mapping alone would pass
        # here — and would silently emit a differently-ordered run the first time a collection is
        # built from an existing `genome` table. All 70,519 published runs are ascending ordinals.
        members.extend(sorted(ordinal_of_genome_id[gid] for gid in arrangement.member_genome_ids))

    block = {
        "n": counts,
        "cnt": genes,
        "gen": genomes,
        "flip": flips,
        "tot": [locus.total_arrangement_count for locus in loci],
        "vec": vectors,
        "gid": members,
    }
    if len(members) != sum(genomes):
        raise ValueError(
            f"arr.gid is {len(members):,} entries but arr.gen sums to {sum(genomes):,} — the page "
            "would read every arrangement's membership from the wrong offset"
        )
    return block


def context_block(session: Session, pangenome_id: int, loci: list[Locus]) -> dict:
    """The ``ctx`` block — the **marginal** view: one candidate at one position, ten slots per locus.

    ⛔ ``n`` and ``obs`` are flat arrays of ``n_loci × 10``, addressed as
    ``catalogue_ordinal * 10 + slot`` where ``slot`` is the position of the signed offset in
    ``OFFSETS`` — **not the offset itself**, which runs −5…−1, 1…5 and has no zero.

    ⛔⛔ ``obs`` is the denominator counted **before the top-N cut**, so it cannot be recovered by
    summing the occupant rows: a locus with more than ``top_neighbours`` candidates at a slot has a
    larger ``obs`` than its rows account for, and that difference is one of the payload's four
    distinct remainders. It is read from ``locus.context_observed_member_counts``, which is where
    the ingest stored it for exactly this reason.

    ⚠ ``nid`` holds payload **ordinals**, not database ids — the page holds indices everywhere.
    """
    from syntitude_backend.models.locus_offset_occupant import LocusOffsetOccupant

    _, offsets, _, _, _ = _payload_constants()
    slot_of = {offset: index for index, offset in enumerate(offsets)}
    n_slots = len(offsets)
    ordinal_of_locus_id = {locus.locus_id: locus.catalogue_ordinal for locus in loci}

    rows = session.execute(
        select(LocusOffsetOccupant, Locus.catalogue_ordinal)
        .join(Locus, Locus.locus_id == LocusOffsetOccupant.locus_id)
        .where(Locus.pangenome_id == pangenome_id)
        .order_by(
            Locus.catalogue_ordinal,
            LocusOffsetOccupant.signed_offset,
            LocusOffsetOccupant.rank_within_offset,
        )
    ).all()

    slot_counts = [0] * (len(loci) * n_slots)
    neighbours, gene_counts, same_strand = [], [], []
    for occupant, ordinal in rows:
        slot_counts[ordinal * n_slots + slot_of[occupant.signed_offset]] += 1
        neighbours.append(ordinal_of_locus_id[occupant.neighbour_locus_id])
        gene_counts.append(occupant.member_gene_count)
        same_strand.append(occupant.same_strand_member_count)

    observed: list[int] = []
    for locus in loci:
        observed.extend(locus.context_observed_member_counts)
    return {
        "n": slot_counts,
        "obs": observed,
        "nid": neighbours,
        "cnt": gene_counts,
        "same": same_strand,
    }


#: The payload stores the variance score ×1000 and **clipped at 2.0**, as an integer. The column
#: holds the score itself, so both steps are re-applied here rather than stored twice.
VARIANCE_SCALE = 1000
VARIANCE_CLIP = 2.0

#: `null_block` rounds its three floats to 6 dp before shipping them.
NULL_BASELINE_DECIMALS = 6


def _rounded(value: float | None, decimals: int) -> float | None:
    """`round`, but NULL stays NULL — an unmeasured baseline is not a baseline of zero."""
    return None if value is None else round(float(value), decimals)


def gaps_block(session: Session, pangenome_id: int, loci: list[Locus]) -> dict:
    """The ``gaps`` block — adjacencies, their length spread, and what was seen inside them.

    ⛔⛔ **The sparse triple is where the meaning INVERTS, and it inverts in only one direction.**
    The payload ships ``vi``/``vd``/``vmd`` sparsely because a JSON array cannot be sparse, so
    *absent* there means **every genome agrees** — 86.1 % of ecoli's gaps. The column is dense, so
    ``0.0`` carries that agreement explicitly and ``NULL`` means *this run did not measure variance*
    — a state the sparse form could not express at all. Re-sparsifying is therefore
    ``score > 0``, under which a measured zero and an unmeasured NULL both drop out, which is
    exactly what the published file did. **The database is strictly more informative than the
    payload here, and going back is lossy on purpose.**

    ⚠ ``q1 == q3`` means the MIDDLE HALF agrees; only ``mn == mx`` certifies "every genome agrees".
    Both pairs are carried because an earlier page reported the first as the second.
    """
    from syntitude_backend.models.intergenic_gap import IntergenicGap, IntergenicGapFeature

    ordinal_of_locus_id = {locus.locus_id: locus.catalogue_ordinal for locus in loci}
    gaps = list(
        session.execute(
            select(IntergenicGap)
            .where(IntergenicGap.pangenome_id == pangenome_id)
            .order_by(IntergenicGap.intergenic_gap_id)
        ).scalars()
    )
    if not gaps:
        # ⚠ `{}` and not an empty scaffold: a cohort without the non-coding pass has nothing to say
        # here, and the page special-cases an absent block rather than an empty one.
        return {}

    features_by_gap: dict[int, list] = {}
    for feature in session.execute(
        select(IntergenicGapFeature)
        .join(IntergenicGap, IntergenicGap.intergenic_gap_id == IntergenicGapFeature.intergenic_gap_id)
        .where(IntergenicGap.pangenome_id == pangenome_id)
        .order_by(IntergenicGapFeature.intergenic_gap_id, IntergenicGapFeature.rank_within_gap)
    ).scalars():
        features_by_gap.setdefault(feature.intergenic_gap_id, []).append(feature)

    # ⚠ Two pools LOCAL to this block, not the global `strings` table — `intergenic_block` builds
    # its own `_Intern` pair, so their indices address `gaps.labels`/`gaps.types` and nothing else.
    labels, types = StringPool(), StringPool()
    per_gap_counts, label_indices, type_indices, feature_counts = [], [], [], []
    for gap in gaps:
        features = features_by_gap.get(gap.intergenic_gap_id, ())
        per_gap_counts.append(len(features))
        for feature in features:
            label_indices.append(labels.index(feature.feature_label))
            type_indices.append(types.index(feature.feature_type))
            feature_counts.append(feature.observed_genome_count)

    varying = [
        index
        for index, gap in enumerate(gaps)
        if gap.length_variance_score is not None and gap.length_variance_score > 0
    ]
    return {
        "a": [ordinal_of_locus_id[gap.flanking_locus_id_a] for gap in gaps],
        "b": [ordinal_of_locus_id[gap.flanking_locus_id_b] for gap in gaps],
        "n": [gap.observed_genome_count for gap in gaps],
        "nt": [gap.median_signed_length_nt for gap in gaps],
        "q1": [gap.quartile1_signed_length_nt for gap in gaps],
        "q3": [gap.quartile3_signed_length_nt for gap in gaps],
        "mn": [gap.minimum_signed_length_nt for gap in gaps],
        "mx": [gap.maximum_signed_length_nt for gap in gaps],
        "vi": varying,
        "vd": [
            int(round(min(gaps[index].length_variance_score, VARIANCE_CLIP) * VARIANCE_SCALE))
            for index in varying
        ],
        "vmd": [gaps[index].modal_length_nt for index in varying],
        "n_feat": [gap.distinct_named_feature_count for gap in gaps],
        "fn": per_gap_counts,
        "flab": label_indices,
        "ftyp": type_indices,
        "fcnt": feature_counts,
        "labels": labels.values,
        "types": types.values,
    }


def map_representation_blocks(session: Session, pangenome_id: int, loci: list[Locus]) -> list[dict]:
    """The ``map_reps`` block — one entry per representation, **as a LIST because order is meaning**.

    The page renders the representations as tabs in a fixed order (Bacformer first — it is the axis
    the method is about), so this is a list and not a dict.

    ⛔⛔ **``x``, ``y``, ``near`` and ``cos6`` are base64-packed binary, not JSON arrays.** They are
    emitted through nuna's own ``_b64_i16``/``_b64_i32``, imported rather than reimplemented — a
    second little-endian packer is a second thing to get wrong, and an endianness mistake produces
    a valid base64 string, a valid picture, and the wrong loci.

    ⚠ ``near`` is ``n_loci × k`` **raveled**, and a neighbour outside the catalogue is ``-1``, which
    **drops its slot rather than its rank** — the surviving slot indices are what address ``cos6``.
    Reading ``near`` by rank instead draws one locus's distances on another, and the picture still
    looks like a picture.

    ⚠ ``nowhere`` (−32768) is *no medoid*, and it is **not** ``-1``. Both catalogues happen to place
    every locus, so the sentinel never appears in them — which is precisely why it must be carried
    from the constant rather than inferred from the data.
    """
    from pathlib import Path

    from nuna.tl.locus_browser.export_payload import _NOWHERE, _b64_i16, _b64_i32

    from syntitude_backend.models.locus_embedding_geometry import (
        LocusEmbeddingGeometry,
        LocusMapProjection,
    )

    projections = list(
        session.execute(
            select(LocusMapProjection)
            .where(LocusMapProjection.pangenome_id == pangenome_id)
            .order_by(LocusMapProjection.locus_map_projection_id)
        ).scalars()
    )
    if not projections:
        return []

    blocks = []
    for projection in projections:
        rows = session.execute(
            select(LocusEmbeddingGeometry, Locus.catalogue_ordinal)
            .join(Locus, Locus.locus_id == LocusEmbeddingGeometry.locus_id)
            .where(
                Locus.pangenome_id == pangenome_id,
                LocusEmbeddingGeometry.representation == projection.representation,
            )
            .order_by(Locus.catalogue_ordinal)
        ).all()
        if len(rows) != len(loci):
            raise ValueError(
                f"{projection.representation.value}: {len(rows):,} geometry rows for "
                f"{len(loci):,} loci — x/y are positional, so a missing row shifts the whole map"
            )
        x = [geometry.map_x for geometry, _ in rows]
        y = [geometry.map_y for geometry, _ in rows]
        near: list[int] = []
        cosines: list[int] = []
        for geometry, _ in rows:
            near.extend(geometry.nearest_locus_ordinals)
            cosines.extend(geometry.pairwise_cosine_scaled)
        blocks.append(
            {
                "rep": projection.representation.value,
                # The projection NAME and metric travel with the coordinates, so a t-SNE fallback
                # can never be captioned as a UMAP and a euclidean fit never as a cosine one.
                "how": projection.projection_method,
                "metric": projection.requested_metric,
                "k": projection.neighbour_count,
                "cos_scale": projection.cosine_scale_factor,
                "nowhere": int(_NOWHERE),
                "scale": {
                    "cx": projection.scale_centre_x,
                    "cy": projection.scale_centre_y,
                    "span": projection.scale_span,
                    "unit": projection.scale_unit,
                },
                "x": _b64_i16(x),
                "y": _b64_i16(y),
                "near": _b64_i32(near),
                "cos6": _b64_i16(cosines),
                # ⚠ The basename, as the payload carries it — the column holds the absolute path
                # the ingest read, which is a fact about this machine and not about the catalogue.
                "source": Path(projection.source_csv_path).name,
            }
        )
    return blocks


#: ⚠ Where each `meta` field comes from, stated per field rather than left to the reader. Three of
#: them are **not in the database at all** — they are properties of the *export*, not of the
#: pangenome — so the instrument takes them from nuna's constants or the checked-in catalogue
#: registry and says so, rather than quietly inventing a column's worth of authority.
META_FIELD_SOURCES: dict[str, str] = {
    "n_genomes": "database", "n_genes": "database", "n_loci": "database",
    "genomes": "database", "model_id": "database", "species": "database",
    "omitted": "database", "provenance": "database", "audit": "database",
    "built": "database (volatile — excluded by the oracle)",
    "git_sha": "database (volatile — excluded by the oracle)",
    "offsets": "nuna constant", "bands": "nuna constant", "policy": "nuna constant",
    "top_neighbours": "nuna constant — NOT STORED",
    "top_arrangements": "nuna constant — NOT STORED",
    "seq": "export setting — NOT STORED",
    "model_label": "database (pangenome_evaluation.detail WHERE metric_name = 'label')",
    "dset": "database (pathogen_species.species_key)",
}  # fmt: skip


def _headline_value(metric_name: str, value):
    """An audit headline value with its JSON type restored — **by integrality, not by name**.

    ⛔ `pangenome_evaluation.numeric_value` is one numeric column, so *whether the audit wrote an
    int or a float is genuinely not stored*. This is the one place in the payload where that bites:
    `17531` must not come back as `17531.0`, and `0.032587` must not come back as `0`.

    ⚠ A suffix rule was tried first and was wrong twice in twenty-one keys —
    `split_gene_rate_excl_singletons` does not end in `_rate` (so it was truncated to `0`) and
    `over_merge_gene_rate_num` contains `_rate` but is a count. Integrality is a property of the
    *value* rather than of the spelling, and it is right on every key here.

    ⚠ Its one blind spot, stated rather than discovered: **a rate that is exactly 0.0 or 1.0** comes
    back as an int. Only `no_homology_gene_rate` is such a value today, and only because the tier it
    counts was retired — so it already sits inside a recorded difference.
    """
    if value is None:
        return None
    number = float(value)
    return int(number) if number == int(number) else number


def _arrangement_cap(loci: list[Locus], listed_counts: list[int]) -> int:
    """The `--top-arrangements` the export ran with, recovered from what it shipped.

    ⭐ **0 means every arrangement was kept**, and it is a different statement from "four were": the
    page tells the reader whether a rarer neighbourhood exists or merely was not shipped.

    A locus is evidence of a cap only when its `total_arrangement_count` exceeds what was listed,
    and then the cap is what it was cut to. Uncapped catalogues have no such locus, so the answer is
    0 — which is what both published catalogues shipped, on all 33,201 loci.
    """
    # ⛔ `listed > 0` is not a tidy-up. **847 loci have no arrangement row at all** — their genes
    # never reached a window, because `ac` is an inner join on coordinates — and a locus that listed
    # NONE reveals no cap. Without the guard such a locus reads as "cut to zero", which is a cap of
    # 0, which is the encoding for *uncapped*: the two ends of the scale collide on the case that
    # actually occurs. (It happens to be harmless here only because all 847 also have `tot == 0`.)
    capped = [
        listed
        for locus, listed in zip(loci, listed_counts, strict=True)
        if listed > 0 and locus.total_arrangement_count > listed
    ]
    if not capped:
        return 0
    cap = max(capped)
    if min(capped) != cap:
        raise ValueError(
            f"loci were cut to between {min(capped)} and {cap} arrangements — no single "
            "--top-arrangements produces that, so the cap cannot be stated"
        )
    return cap


def null_baseline_block(session: Session, pangenome_id: int, *, model_label: str) -> dict:
    """The `null` block — the random-pair baseline per representation, **keyed by rep, not a list**.

    Top-level in the payload on purpose: the card needs it in every render, whereas `map_reps` is
    optional and comes from a GPU job.

    ⚠ `source` is the CSV's filename, which is a fact about the export rather than about the
    baseline, so it is rebuilt from the model label rather than stored — see
    :data:`META_FIELD_SOURCES` for the same distinction applied to `meta`.
    """
    from syntitude_backend.models.locus_embedding_geometry import LocusMapProjection

    out: dict[str, dict] = {}
    for projection in session.execute(
        select(LocusMapProjection)
        .where(LocusMapProjection.pangenome_id == pangenome_id)
        .order_by(LocusMapProjection.locus_map_projection_id)
    ).scalars():
        if projection.null_bin_counts is None:
            continue
        rep = projection.representation.value
        # ⛔ The payload rounds all three to 6 dp and the columns hold the unrounded values — which
        # is the right way round: the database keeps what was measured and the emitter applies the
        # payload's convention. Without this, `w` ships as 0.010000000000000009 (a float subtraction
        # of two bin edges) and `mean` at 8 dp — both correct numbers, neither the published one.
        out[rep] = {
            "lo": _rounded(projection.null_bin_lower_edge, NULL_BASELINE_DECIMALS),
            "w": _rounded(projection.null_bin_width, NULL_BASELINE_DECIMALS),
            "count": list(projection.null_bin_counts),
            "mean": _rounded(projection.null_mean_cosine, NULL_BASELINE_DECIMALS),
            "source": f"{model_label}_null_{rep}.csv",
        }
    return out


def meta_block(
    session: Session,
    pangenome_id: int,
    loci: list[Locus],
    *,
    species_key: str,
    listed_arrangement_counts: list[int],
) -> dict:
    """The `meta` block — the page's header, footer and genome vocabulary.

    ⛔ `genomes` is the **vocabulary `arr.gid` indexes into**, ordered by
    `collection_genome_ordinal` and never re-sorted here. Re-deriving it by sorting accessions is
    the implicit ordering this project punishes: it agrees today and stops agreeing the moment a
    collection is built in any other order.
    """
    from nuna.tl.locus_browser.export_payload import (
        AUDIT_HEADLINE_KEYS,
        SEQ_FLANK,
        TOP_NEIGHBOURS,
    )

    from syntitude_backend.models.genome import Genome
    from syntitude_backend.models.genome_collection import GenomeCollectionMembership
    from syntitude_backend.models.pangenome import Pangenome, PangenomeEvaluation
    from syntitude_backend.models.pathogen_species import PathogenSpecies

    _, offsets, band_order, _, policy = _payload_constants()
    pangenome = session.get(Pangenome, pangenome_id)
    species = session.get(PathogenSpecies, pangenome.pathogen_species_id)

    vocabulary = [
        accession
        for accession, in session.execute(
            select(Genome.sample_id)
            .join(
                GenomeCollectionMembership,
                GenomeCollectionMembership.genome_id == Genome.genome_id,
            )
            .where(
                GenomeCollectionMembership.genome_collection_id == pangenome.genome_collection_id
            )
            .order_by(GenomeCollectionMembership.collection_genome_ordinal)
        ).all()
    ]

    evaluation_detail: dict[str, str | None] = {}
    evaluation_detail: dict[str, str | None] = {}
    headline_rows: dict[str, float | None] = {}
    for row in session.execute(
        select(PangenomeEvaluation).where(PangenomeEvaluation.pangenome_id == pangenome_id)
    ).scalars():
        headline_rows[row.metric_name] = row.numeric_value
        evaluation_detail[row.metric_name] = row.detail

    # ⭐ The audit's own label, as the audit wrote it — read from the database rather than from the
    # checked-in `published_catalogues` triple. The registry is right about these two catalogues and
    # is the correct authority for *addressing artifacts*; it is the wrong authority for what a
    # pangenome IS, and an instrument that asks it here would keep passing after the database
    # started disagreeing with it.
    # ⚠ `nuna_model.label` is NOT this string — it carries no species prefix.
    model_label = evaluation_detail.get("label")
    if not model_label:
        raise ValueError(
            f"pangenome {pangenome_id} has no `label` evaluation row — `meta.model_label` and the "
            "audit block's own label would have to be guessed"
        )
    headline = {
        key: _headline_value(key, headline_rows[key])
        for key in AUDIT_HEADLINE_KEYS
        if key in headline_rows
    }

    # ⚠ Derived from the tier the audit assigned, so the lists cannot drift from the counts in the
    # report — and kept as TWO lists, because a Pfam conflict is weaker evidence than an over-merge
    # and merging them would state a conflict as a grade.
    failure_tiers = set(policy["failure_tiers"])
    contested = policy["contested_pfclass"]
    return {
        "species": species.scientific_name,
        # ⚠ `species_key` is the BROWSER key. It coincides with the export's `--dset` token for
        # these two species and is a different vocabulary from the parquets' `species` column
        # (`kpneumoniae`), so this equality is a fact about this cohort, not a rule.
        "dset": species.species_key,
        "model_id": pangenome.run_id,
        "model_label": model_label,
        "built": pangenome.built_at.date().isoformat() if pangenome.built_at else None,
        "git_sha": pangenome.git_sha,
        "provenance": pangenome.provenance_rows,
        "omitted": pangenome.omitted_sections or {},
        "n_genomes": pangenome.genome_count,
        "n_genes": pangenome.gene_count,
        "n_loci": len(loci),
        "offsets": list(offsets),
        "bands": list(band_order),
        "genomes": vocabulary,
        "top_neighbours": int(TOP_NEIGHBOURS),
        # ⛔ Read from the DATA, never from `TOP_ARRANGEMENTS`. The constant is nuna's *default* (4)
        # and the published exports overrode it to run uncapped, so taking the default emits `4` for
        # a catalogue that shipped `0` — and 0 vs 4 is the difference between "a rarer neighbourhood
        # exists but was not shipped" and "there are no others", which is the whole reason the field
        # is in the payload.
        "top_arrangements": _arrangement_cap(loci, listed_arrangement_counts),
        "seq": {"dir": "data/seq", "flank": SEQ_FLANK},
        "policy": policy,
        "audit": {
            "label": model_label,
            "sources": [
                f"{model_label}_pfam_concordance.tsv",
                f"{model_label}_audit_summary.json",
            ],
            "headline": headline,
            "failures": [
                locus.catalogue_ordinal for locus in loci if locus.collapse_tier in failure_tiers
            ],
            "contested": [
                locus.catalogue_ordinal
                for locus in loci
                if locus.pfam_concordance_class == contested
            ],
        },
    }


def build_payload_from_database(session: Session, species_key: str) -> dict:
    """The whole payload, rebuilt — **and its own interning order checked before it is returned**.

    ⭐ The self-check is the point: a serialiser that emitted the blocks in the wrong order would
    otherwise produce thousands of changed indices in a diff nobody can read. Here it raises, naming
    the pool and the column.
    """
    from syntitude_backend.instruments.payload_reproduction import verify_intern_walk
    from syntitude_backend.models.pathogen_species import PathogenSpecies

    schema_version, _, _, _, _ = _payload_constants()
    pangenome_id = session.execute(
        select(PathogenSpecies.published_pangenome_id).where(
            PathogenSpecies.species_key == species_key
        )
    ).scalar_one()
    loci = load_catalogue_loci(session, pangenome_id)
    pools = CataloguePools()

    # ⛔ ORDER: nodes, then lists, then everything that does not intern. See the module docstring.
    nodes = node_block(loci, pools)
    lists = list_block(session, pangenome_id, len(loci), pools)
    # ⚠ None of the blocks below intern, so their order is free — `arr` is built first only because
    # `meta.top_arrangements` is recovered from what it listed.
    arrangements = arrangement_block(session, pangenome_id, loci)
    maps = map_representation_blocks(session, pangenome_id, loci)
    gaps = gaps_block(session, pangenome_id, loci)

    payload = {
        "schema": schema_version,
        "meta": meta_block(
            session,
            pangenome_id,
            loci,
            species_key=species_key,
            listed_arrangement_counts=arrangements["n"],
        ),
        "strings": pools.tables(),
        "nodes": nodes,
        "lists": lists,
        "arr": arrangements,
        **({"map_reps": maps} if maps else {}),
        "ctx": context_block(session, pangenome_id, loci),
        **({"gaps": gaps} if gaps else {}),
    }
    baseline = null_baseline_block(
        session, pangenome_id, model_label=payload["meta"]["model_label"]
    )
    if baseline:
        payload["null"] = baseline
    failures = verify_intern_walk(payload)
    if failures:
        raise ValueError(
            "the rebuilt payload's own interning order is wrong — the blocks were emitted in a "
            "different order from `build_payload`:\n  " + "\n  ".join(failures)
        )
    return payload
