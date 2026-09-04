"""One catalogue, computed from its source artifacts — the pandas half, with no database in it.

⛔ **This calls nuna's own functions and reimplements none of them.** `node_order`, `top_counts`,
`family_pfam`, `family_modal_symbols`, `family_modal_products`, `oriented_windows`, `arrangements`,
`neighbour_counts`, `near_synteny_agreement`, `gap_table` and even the two rounding helpers
(`_floats`, `_sigfigs`) are the science; a second implementation of any of them would be a second
thing to keep in step, and the two would agree until the day they did not. What this module does is
**assemble** their outputs into rows rather than into the payload's columnar, string-interned,
run-length-encoded blocks.

⭐ That split is what makes the parity check mean something. Ingest and the export share the science
and differ in the assembly, so a comparison between the database and the published catalogue tests
the assembly — which is the part that is new.

⚠ **Read the SOURCE artifacts, never the published payload.** The payload is the acceptance oracle;
loading it would make the test circular. The one thing taken from outside the source tree is the
vendored Pfam/GO/COG name tables, which are public reference metadata and not a property of any model.

⛔ **The audit's own verdicts are READ, never re-derived** — `class_clan`, `n_arch`, the collapse
tier, the resolved threshold and the two embedding pairs. The page once re-derived the Pfam verdict
by a different rule and disagreed with the report on 2 of 22,624 loci: *"a page that quotes the
report must not be able to contradict it, ever."*
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from syntitude_backend.ingest.artifact_locator import CatalogueArtifacts

#: The signed offsets, in display order. ⛔ `0` is absent — it is the focal gene.
#: Asserted against `export_payload.OFFSETS` at load, because `locus_offset_occupant` has a CHECK
#: over this vocabulary and `context_observed_member_counts` is an array in exactly this order.
OFFSETS = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)

#: `render_page`'s `nodes.a5` / `nodes.resolved` rounding, which `interest_score` must see.
SYNTENY_DECIMALS = 4
RESOLVED_DECIMALS = 3

#: The seven annotation vocabularies, as `(AnnotationKind value, payload list key, value column)`.
#: ⚠ `u50` is deliberately absent: it has five extra columns and gets its own cross-tab table.
ANNOTATION_SOURCES = (
    ("gene_symbol", "sym", "gene"),
    ("protein_product", "prod", "product"),
    ("pfam_architecture", "pfam", "arch"),
    ("cog_orthogroup", "cog", "cog_id"),
    ("ec_number", "ec", "ec"),
    ("kegg_orthology", "kegg", "kegg_ko"),
)


class CatalogueFrameError(RuntimeError):
    """A catalogue that cannot be assembled without inventing part of it."""


@dataclass
class CatalogueFrames:
    """Every table of one catalogue, as pandas frames in payload locus order."""

    #: One row per locus, ordered by `catalogue_ordinal`, carrying every `locus` column.
    loci: object
    #: `(node, annotation_kind, rank, term, gene_count, namespace)` — long, one row per term.
    annotation_entries: object
    #: `(node, rank, uniref50, n, product, arch, n_pfam, gene, n_sym)` — the cross-tab.
    uniref_crosstab: object
    #: `(node, rank, genes, genomes, flip, s0..s9, gset)` — the JOINT view.
    arrangements: object
    #: `(node, d, neigh_pos, cnt, same, obs, rank)` — the MARGINAL view.
    offset_occupants: object
    #: One row per member gene: `(sample_id, flat_index, node, arrangement_rank)`.
    gene_memberships: object
    #: `(a, b, …)` keyed by node LABEL, canonicalised the way `gene_adjacencies` canonicalises.
    gaps: object
    #: `{representation: {"info": …, "geometry": frame}}`.
    geometry: dict
    #: `{representation: null-baseline dict}`.
    null_baselines: dict

    #: The genome vocabulary `arr.gid` indexes into, and the ordinal every membership is a position in.
    samples: list = field(default_factory=list)
    n_genes: int = 0
    audit_summary: dict = field(default_factory=dict)
    #: Sections the source tree could not supply, so an absent block is never read as a measured zero.
    omitted: dict = field(default_factory=dict)
    #: ⭐ What was actually examined, so a report states its own coverage rather than saying "done".
    coverage: dict = field(default_factory=dict)


# ── loading ────────────────────────────────────────────────────────────────────────────────────
def _load_source_frames(artifacts: CatalogueArtifacts) -> dict:
    """Every source frame `export_payload.main` loads, by the same calls and in the same order."""
    import numpy
    import pandas
    from nuna.eval.assignments import gene_universe, load_assignments
    from nuna.eval.reference_annotation import (
        load_bakta_dbxrefs,
        load_bakta_noncoding,
        load_bakta_products,
        load_gene_coords,
    )

    processed = artifacts.processed_root
    universe = gene_universe(processed, artifacts.set_key)
    samples = sorted(str(value) for value in universe["sample_id"].unique())

    omitted: dict[str, str] = {}
    assign = load_assignments(artifacts.assignment, universe=universe)[
        ["sample_id", "flat_index", "node"]
    ]
    products = load_bakta_products(processed, samples)
    coords = load_gene_coords(processed, samples)
    noncoding = load_bakta_noncoding(processed, samples)

    dbxrefs = load_bakta_dbxrefs(processed, samples)
    if not len(dbxrefs):
        # ⚠ A payload without COG is *a page without a function tab*, not a broken export — the same
        # judgement `build_payload` makes. Recorded so the absence is never read as a measured zero.
        omitted["uniref50"] = "no {BS}_dbxref.parquet under embeddings/meta/ — allele families unavailable"
        dbxrefs = None

    pfam = None
    if artifacts.pfam_architectures.exists():
        pfam = pandas.read_parquet(artifacts.pfam_architectures)
        pfam["sample_id"] = pfam["sample_id"].astype(str)
    else:
        omitted["pfam"] = f"{artifacts.pfam_architectures.name} not found — domain architectures unavailable"

    return {
        "numpy": numpy,
        "pandas": pandas,
        "samples": samples,
        "n_genes": int(len(universe)),
        "assign": assign,
        "products": products,
        "coords": coords,
        "noncoding": noncoding,
        "dbxrefs": dbxrefs,
        "pfam": pfam,
        "omitted": omitted,
    }


def _load_audit_frames(artifacts: CatalogueArtifacts, omitted: dict) -> dict:
    """The audit's own outputs — read, and recorded with WHICH artifact each came from.

    ⚠ The published *E. coli* export did **not** read `{label}_cluster_table.parquet` (it did not
    exist on CSD3 that day), so its Bacformer pair was recomputed from the full embedding matrix.
    Measured against the shipped catalogue afterwards the two agree to 5.0e-5 — the payload's own
    4-significant-figure rounding — on all 12,104 measurable loci. So the cluster table is a sound
    source, and it is a *different artifact* than the page used: which one supplied each column is
    recorded rather than left for a reader to assume.
    """
    import pandas
    from nuna.tl.locus_browser.export_payload import load_audit_evidence

    evidence, source = load_audit_evidence(artifacts.cluster_table, artifacts.homology_waterfall)
    if evidence is None:
        raise CatalogueFrameError(
            f"neither {artifacts.cluster_table.name} nor {artifacts.homology_waterfall.name} exists. "
            "The collapse tier, the resolved threshold and both embedding pairs come from one of "
            "them, and a catalogue without those is not the one the pages serve."
        )

    concordance = None
    if artifacts.pfam_concordance.exists():
        concordance = pandas.read_csv(artifacts.pfam_concordance, sep="\t")
        concordance["node"] = concordance["node"].astype(str)
        concordance = concordance.drop_duplicates("node").set_index("node")
    else:
        omitted["pfam_concordance"] = (
            f"{artifacts.pfam_concordance.name} not found — the Pfam verdict would fall back to a "
            "derivation over the top-5 architectures, which can differ from the audit's over all"
        )

    return {
        "evidence": evidence.set_index("node"),
        "evidence_source": source,
        "concordance": concordance,
        "audit_summary": json.loads(artifacts.audit_summary.read_text()),
    }


def load_pfam_name_table() -> dict:
    """The vendored Pfam table — `render_page._pfam_lookup`, the only reader of that file.

    ⛔ **`display_name`'s second fall-through needs this and the exported payload does not carry
    it.** `attach_pfam_names` runs at RENDER time, so an ingest reading only the export would demote
    370 *E. coli* loci to `locus <label>` — which reads as a data gap rather than a missing table.
    """
    from nuna.tl.locus_browser.render_page import _pfam_lookup

    return _pfam_lookup()


# ── the wide annotation frame ──────────────────────────────────────────────────────────────────
def _annotation_frame(assign, products, dbxrefs, pfam, numpy):
    """`build_payload`'s one wide frame — every per-locus reduction below is a groupby on it."""
    from nuna.eval.reference_annotation import DBXREF_VALUE_COLS
    from nuna.tl.locus_browser.export_payload import real_gene_names

    function_columns = [column for column in DBXREF_VALUE_COLS if column != "sample_id"]
    names = real_gene_names(products)
    frame = assign.merge(names, on=["sample_id", "flat_index"], how="left").merge(
        products[["sample_id", "flat_index", "product"]], on=["sample_id", "flat_index"], how="left"
    )
    if dbxrefs is not None:
        # ⚠ `reindex` and not a column select: a frame from before a column existed yields NaN for
        # it rather than a KeyError, which is what keeps an older mirror loadable.
        frame = frame.merge(
            dbxrefs.reindex(columns=["sample_id", "flat_index", *function_columns]),
            on=["sample_id", "flat_index"],
            how="left",
        )
    else:
        for column in function_columns:
            frame[column] = numpy.nan
    if pfam is not None:
        frame = frame.merge(
            pfam[["sample_id", "flat_index", "arch"]], on=["sample_id", "flat_index"], how="left"
        )
    else:
        frame["arch"] = numpy.nan
    return frame


# ── the catalogue ──────────────────────────────────────────────────────────────────────────────
def build_catalogue_frames(artifacts: CatalogueArtifacts) -> CatalogueFrames:
    """Assemble every table of one catalogue. The only entry point; everything else is a helper."""
    import numpy
    import pandas
    from nuna.eval.metrics.oversubscription import node_membership_profile
    from nuna.eval.metrics.syntology import NEAR_SHELLS, near_synteny_agreement
    from nuna.eval.prevalence import categorise
    from nuna.tl.locus_browser.export_payload import (
        MAJOR_SHARE,
        TOP_COG,
        TOP_EC,
        TOP_FAMILIES,
        TOP_GO,
        TOP_KEGG,
        TOP_NEIGHBOURS,
        TOP_PFAM,
        TOP_PRODUCTS,
        TOP_SYMBOLS,
        _floats,
        _sigfigs,
        family_modal_products,
        family_modal_symbols,
        family_pfam,
        neighbour_counts,
        node_order,
        oriented_windows,
        top_counts,
    )
    from nuna.tl.locus_browser.export_payload import (
        OFFSETS as NUNA_OFFSETS,
    )
    from nuna.tl.locus_browser.export_payload import (
        arrangements as build_arrangements,
    )
    from nuna.tl.locus_browser.functional import NS_CODE, cog_summary, go_verdicts, top_go_slim
    from nuna.tl.locus_browser.intergenic import gap_table
    from nuna.tl.locus_browser.vendor_go import go_reference, slim_of

    if tuple(NUNA_OFFSETS) != OFFSETS:
        raise CatalogueFrameError(
            f"nuna's OFFSETS is now {tuple(NUNA_OFFSETS)!r} but this schema stores "
            f"`context_observed_member_counts` as an array in the order {OFFSETS!r} and has a CHECK "
            "over that vocabulary. A reordering would silently put every count under a different "
            "position, so it is refused rather than absorbed."
        )

    source = _load_source_frames(artifacts)
    omitted = source["omitted"]
    audit = _load_audit_frames(artifacts, omitted)
    samples, assign = source["samples"], source["assign"]
    n_genomes = len(samples)
    sample_position = {sample: index for index, sample in enumerate(samples)}

    # ── the locus roster, in the payload's canonical order ─────────────────────────────────────
    profile = node_membership_profile(assign, n_genomes)
    profile["band"] = categorise(profile["genomes_present"].to_numpy(), n_genomes)
    profile = node_order(profile)
    nodes = profile["node"].tolist()
    node_position = {node: index for index, node in enumerate(nodes)}
    n_loci = len(nodes)

    annotation = _annotation_frame(
        assign, source["products"], source["dbxrefs"], source["pfam"], numpy
    )

    # ── per-locus reductions ───────────────────────────────────────────────────────────────────
    named_counts = annotation.assign(_named=annotation["gene"].notna()).groupby("node")["_named"].sum()
    distinct_families = annotation.groupby("node")["uniref50"].nunique()
    labelled = annotation.dropna(subset=["uniref50"])
    labelled_counts = labelled.groupby("node").size()
    family_counts = (
        labelled.groupby(["node", "uniref50"], observed=True).size().rename("n").reset_index()
    )
    family_counts["_total"] = family_counts["node"].map(labelled_counts)
    # ⛔ "Major" = holding ≥ MAJOR_SHARE of the LABELLED members — the audit's own bar. The distinct
    # count above includes single-gene stragglers, so it overstates how many families a locus spans:
    # the card claims with the major count and lists with the distinct one.
    major_families = (
        family_counts[family_counts["n"] >= MAJOR_SHARE * family_counts["_total"]]
        .groupby("node")
        .size()
    )

    top_symbols = top_counts(annotation, "gene", TOP_SYMBOLS)
    top_products = top_counts(annotation, "product", TOP_PRODUCTS)
    top_families = top_counts(annotation, "uniref50", TOP_FAMILIES)
    if len(top_families):
        top_families = (
            top_families.merge(family_modal_products(annotation), on=["node", "uniref50"], how="left")
            .merge(family_pfam(annotation), on=["node", "uniref50"], how="left")
            .merge(family_modal_symbols(annotation), on=["node", "uniref50"], how="left")
        )
    top_architectures = top_counts(annotation, "arch", TOP_PFAM)
    # ⛔ How many members carry ANY domain. `top_counts` drops nulls, so without this denominator the
    # page cannot tell a locus whose members DISAGREE about architecture from one where most members
    # were never annotated — and the second read as the first is the "14/99 have different Pfam
    # structures" misreading this column exists to prevent.
    pfam_annotated = annotation.groupby("node")["arch"].count()

    go_fold = slim_of(go_reference())
    go_namespaces = {term: value[1] for term, value in go_reference().items()}
    cog = cog_summary(annotation).set_index("node")
    go_verdict_frame = go_verdicts(annotation, go_fold, go_namespaces).set_index("node")
    top_cog = top_counts(annotation, "cog_id", TOP_COG)
    top_ec = top_counts(annotation, "ec", TOP_EC)
    top_kegg = top_counts(annotation, "kegg_ko", TOP_KEGG)
    top_go = top_go_slim(annotation, go_fold, go_namespaces, TOP_GO)
    ec_annotated = annotation.groupby("node")["ec"].count()
    kegg_annotated = annotation.groupby("node")["kegg_ko"].count()

    # ── the ±5 neighbourhood, built ONCE (10 rows per gene) ────────────────────────────────────
    assign_coords = source["coords"].merge(assign, on=["sample_id", "flat_index"], how="inner")
    # ⚠ 1-based INCLUSIVE, hence the +1: these are the GFF's own coordinates, and getting it wrong is
    # a one-base error in every block width — invisible on screen and wrong in the data.
    gene_lengths = (
        assign_coords["end"].astype("int64") - assign_coords["start"].astype("int64") + 1
    ).rename("nt")
    by_node = pandas.DataFrame(
        {"node": assign_coords["node"].to_numpy(), "nt": gene_lengths.to_numpy()}
    ).groupby("node")["nt"]
    median_length = by_node.median()
    length_iqr = by_node.quantile(0.75) - by_node.quantile(0.25)

    gaps = gap_table(assign_coords, source["noncoding"]) if len(assign_coords) else None
    if gaps is not None and len(gaps):
        gaps = gaps[gaps["a"].isin(node_position) & gaps["b"].isin(node_position)]
    windows = oriented_windows(assign_coords, node_position, radius=NEAR_SHELLS)
    occupants = neighbour_counts(windows, top=TOP_NEIGHBOURS)
    slot_of = {offset: index for index, offset in enumerate(OFFSETS)}
    # ⛔ `top=None` keeps EVERY arrangement — the page's own default. At 4, a quarter of loci were
    # truncated and the genome a reader anchors to often had no row at all.
    arrangement_frame = build_arrangements(
        windows, slot_of, top=None, sample_pos=sample_position
    )
    # A5 groups on locus identity alone (the audit's definition), so the strand bit must not split
    # its groups — hence the rename rather than the packed `neigh_pos`.
    synteny = near_synteny_agreement(
        windows.rename(columns={"neigh_pos": "neigh_id"}), radius=NEAR_SHELLS
    ).set_index("node")["syntenic_A5"]
    gene_memberships = _gene_memberships(
        assign, windows, arrangement_frame, slot_of, numpy, pandas
    )
    del windows

    # ── the audit's own columns ────────────────────────────────────────────────────────────────
    evidence = audit["evidence"]
    if "syntenic_A5" in evidence.columns:
        # The audit computed A5 over this same window; prefer its value verbatim and fill the rest
        # from ours. On the published ecoli catalogue the audit covers 12,020 and the windows 4,889
        # more, so the union is what the page actually shipped.
        synteny = evidence["syntenic_A5"].dropna().combine_first(synteny)

    def evidence_column(name):
        if name not in evidence.columns:
            return pandas.Series(numpy.nan, index=nodes)
        return evidence[name].reindex(nodes)

    concordance = audit["concordance"]

    def concordance_column(name, default):
        if concordance is None or name not in concordance.columns:
            return pandas.Series(default, index=nodes)
        return concordance[name].reindex(nodes)

    modal_symbol = (
        top_symbols[top_symbols["rank"] == 0].set_index("node")["gene"]
        if len(top_symbols)
        else pandas.Series(dtype=object)
    )

    loci = pandas.DataFrame({"node": nodes})
    loci["catalogue_ordinal"] = range(n_loci)
    loci["member_gene_count"] = profile["size"].to_numpy()
    loci["member_genome_count"] = profile["genomes_present"].to_numpy()
    loci["prevalence_band"] = profile["band"].to_numpy()
    loci["bakta_gene_symbol"] = [modal_symbol.get(node) for node in nodes]
    loci["named_member_count"] = named_counts.reindex(nodes).fillna(0).astype("int64").to_numpy()
    loci["uniref50_family_count"] = distinct_families.reindex(nodes).fillna(0).astype("int64").to_numpy()
    loci["uniref50_major_family_count"] = major_families.reindex(nodes).fillna(0).astype("int64").to_numpy()
    loci["uniref50_labelled_member_count"] = labelled_counts.reindex(nodes).fillna(0).astype("int64").to_numpy()
    loci["pfam_annotated_member_count"] = pfam_annotated.reindex(nodes).fillna(0).astype("int64").to_numpy()
    # ⛔⛔ **SIX COLUMNS THE CLUSTER TABLE CARRIES AND THIS INGEST ONCE DID NOT READ.** Each is
    # documented on `locus` in detail and each was 100 % NULL, which for `uniref50_impurity` is
    # indistinguishable from its DOCUMENTED meaning — *"NULL below 5 labelled members"*. A reader
    # querying `WHERE uniref50_impurity IS NULL` would have concluded that all 17,531 loci have
    # fewer than five labelled members, when in fact **8,576 carry a measured impurity** and the
    # rest were simply never loaded. That is the exact shape of "a column whose meaning and its
    # contents differ", and the payload cannot catch it because the payload does not carry them.
    loci["uniref50_impurity"] = _floats(evidence_column("u50_impurity"), nd=6)
    loci["uniref50_coverage"] = _floats(evidence_column("u50_coverage"), nd=6)
    loci["seqid_coverage"] = _floats(evidence_column("seqid_coverage"), nd=6)
    if "seqid_coverage" not in evidence.columns or not evidence["seqid_coverage"].notna().any():
        # ⛔ NULL now means *the audit did not measure this*, and it says so. Before this ingest read
        # the column at all, NULL meant *we never looked* — the same value carrying a different
        # fact, which is exactly the confusion an omission record exists to prevent. nuna's own
        # comment on the source: *"seqid lens not measured — NaN (not 0, which would read as
        # 'divergent')"*.
        omitted["seqid_to_medoid"] = (
            "the audit ran with --skip-seqid-to-medoid, so member-vs-medoid identity was never "
            "measured — seqid_coverage is NULL for every locus, and that is a fact about the RUN"
        )
    loci["embed_within_over_nearest"] = _floats(evidence_column("embed_within_over_nearest"), nd=6)
    #: ⚠ The medoid is a GENE — one real member, named by its genome and its flat_index — and not a
    #: centroid. Carried so the page can say WHICH gene the geometry is measured from.
    loci["medoid_sample_id"] = evidence_column("medoid_sample_id").to_numpy()
    loci["medoid_flat_index"] = [
        None if not numpy.isfinite(float(value)) else int(value)
        for value in evidence_column("medoid_flat_index")
    ]
    loci["syntenic_a5"] = _floats(synteny.reindex(nodes), nd=SYNTENY_DECIMALS)
    loci["collapse_tier"] = evidence_column("tier").to_numpy()
    loci["collapse_bucket"] = evidence_column("bucket").to_numpy()
    loci["resolved_threshold"] = _floats(evidence_column("resolved_threshold"), nd=RESOLVED_DECIMALS)
    # ⛔ DISTANCES, not similarities, at significant figures. The audit hands over `1 − d`, and
    # storing that at 3 dp threw the resolution away exactly where it matters.
    loci["esm_within_medoid_distance"] = _sigfigs(1.0 - evidence_column("esm_intra_sim"))
    loci["esm_nearest_medoid_distance"] = _sigfigs(1.0 - evidence_column("esm_inter_sim"))
    loci["bacformer_within_medoid_distance"] = _sigfigs(1.0 - evidence_column("bacformer_intra_sim"))
    loci["bacformer_nearest_medoid_distance"] = _sigfigs(1.0 - evidence_column("bacformer_inter_sim"))
    loci["pfam_concordance_class"] = concordance_column("class_clan", None).to_numpy()
    loci["pfam_architecture_count"] = [
        None if not numpy.isfinite(float(value)) else int(value)
        for value in concordance_column("n_arch", numpy.nan)
    ]
    loci["cog_annotated_member_count"] = (
        cog["n_cog"].reindex(nodes).fillna(0).astype("int64").to_numpy() if len(cog) else 0
    )
    loci["cog_distinct_id_count"] = (
        cog["cog_n_distinct"].reindex(nodes).fillna(0).astype("int64").to_numpy() if len(cog) else 0
    )
    loci["modal_cog_category"] = (
        cog["cog_cat"].reindex(nodes).to_numpy() if len(cog) else None
    )
    loci["ec_annotated_member_count"] = ec_annotated.reindex(nodes).fillna(0).astype("int64").to_numpy()
    loci["kegg_annotated_member_count"] = kegg_annotated.reindex(nodes).fillna(0).astype("int64").to_numpy()
    for namespace, code in NS_CODE.items():
        loci[f"go_verdict_{namespace}"] = go_verdict_frame[f"go_{code}"].reindex(nodes).to_numpy()
        loci[f"go_annotated_member_count_{namespace}"] = (
            go_verdict_frame[f"n_go_{code}"].reindex(nodes).fillna(0).astype("int64").to_numpy()
        )
    loci["median_gene_length_nt"] = median_length.reindex(nodes).fillna(0).astype("int64").to_numpy()
    loci["gene_length_interquartile_range_nt"] = (
        length_iqr.reindex(nodes).fillna(0).astype("int64").to_numpy()
    )
    loci["context_observed_member_counts"] = _observed_counts(occupants, node_position, n_loci, numpy)
    loci["total_arrangement_count"] = _total_arrangements(arrangement_frame, node_position, n_loci, numpy)

    annotation_entries = _annotation_entries(
        {
            "sym": top_symbols,
            "prod": top_products,
            "pfam": top_architectures,
            "cog": top_cog,
            "ec": top_ec,
            "kegg": top_kegg,
        },
        top_go,
        node_position,
        pandas,
    )

    return CatalogueFrames(
        loci=loci,
        annotation_entries=annotation_entries,
        uniref_crosstab=_uniref_crosstab(top_families, node_position),
        arrangements=arrangement_frame,
        offset_occupants=occupants,
        gene_memberships=gene_memberships,
        gaps=gaps,
        geometry=_map_geometry(artifacts, node_position, pandas),
        null_baselines=_null_baselines(artifacts, n_loci),
        samples=samples,
        n_genes=source["n_genes"],
        audit_summary=audit["audit_summary"],
        omitted=omitted,
        coverage={
            "loci": n_loci,
            "genomes": n_genomes,
            "genes_assigned": int(len(assign)),
            "genes_with_coordinates": int(len(assign_coords)),
            "arrangements": int(len(arrangement_frame)),
            "offset_occupant_rows": int(len(occupants)),
            "gaps": int(len(gaps)) if gaps is not None else 0,
            "audit_evidence_source": audit["evidence_source"],
            "audit_evidence_loci": int(len(evidence)),
        },
    )


# ── the pieces ─────────────────────────────────────────────────────────────────────────────────
def _observed_counts(occupants, node_position, n_loci, numpy):
    """`ctx.obs` per locus — member genes for which each offset EXISTS, in `OFFSETS` order.

    ⛔ Counted **before** the top-N cut, which is what lets the page say "and 14 others" honestly;
    read against `member_gene_count` it exposes contig-edge truncation, which a short-read assembly
    has a great deal of.
    """
    slot_of = {offset: index for index, offset in enumerate(OFFSETS)}
    observed = numpy.zeros((n_loci, len(OFFSETS)), dtype=numpy.int64)
    if len(occupants):
        first = occupants[occupants["rank"] == 0]
        rows = first["node"].map(node_position).to_numpy(dtype=int)
        columns = first["d"].map(slot_of).to_numpy(dtype=int)
        observed[rows, columns] = first["obs"].to_numpy(dtype=numpy.int64)
    return [row.tolist() for row in observed]


def _total_arrangements(arrangement_frame, node_position, n_loci, numpy):
    """`arr.tot` — arrangements in TOTAL, never moved by any display cap."""
    totals = numpy.zeros(n_loci, dtype=numpy.int64)
    if len(arrangement_frame):
        first = arrangement_frame[arrangement_frame["rank"] == 0]
        totals[first["node"].map(node_position).to_numpy(dtype=int)] = first["total"].to_numpy(
            dtype=numpy.int64
        )
    return totals.tolist()


def _annotation_entries(top_frames: dict, top_go, node_position, pandas):
    """The six single-column vocabularies plus GO, as one long frame in rank order."""
    kind_by_key = {key: kind for kind, key, _ in ANNOTATION_SOURCES}
    column_by_key = {key: column for _, key, column in ANNOTATION_SOURCES}
    pieces = []
    for key, frame in top_frames.items():
        if frame is None or not len(frame):
            continue
        piece = frame[["node", column_by_key[key], "n", "rank"]].rename(
            columns={column_by_key[key]: "term", "n": "gene_count"}
        )
        piece = piece[piece["node"].isin(node_position)].copy()
        piece["annotation_kind"] = kind_by_key[key]
        piece["namespace"] = None
        pieces.append(piece)
    if top_go is not None and len(top_go):
        piece = top_go[["node", "slim", "n", "rank", "ns"]].rename(
            columns={"slim": "term", "n": "gene_count", "ns": "namespace"}
        )
        piece = piece[piece["node"].isin(node_position)].copy()
        piece["annotation_kind"] = "gene_ontology_slim"
        pieces.append(piece)
    if not pieces:
        return pandas.DataFrame(
            columns=["node", "term", "gene_count", "rank", "annotation_kind", "namespace"]
        )
    return pandas.concat(pieces, ignore_index=True)


def _uniref_crosstab(top_families, node_position):
    """The UniRef50 cross-tab, filtered to loci this catalogue actually has."""
    if top_families is None or not len(top_families):
        return top_families
    return top_families[top_families["node"].isin(node_position)].reset_index(drop=True)


def _gene_memberships(assign, windows, arrangement_frame, slot_of, numpy, pandas):
    """One row per ASSIGNED gene, with the arrangement rank it realises where it has one.

    ⭐ Written in the same pass as `member_genome_ids`, so the array and the rows cannot disagree
    about which genomes carry an arrangement.

    ⛔⛔ **The base is the ASSIGNMENT, not the windows — exactly one row per gene, always.**
    `flank_windows` emits nothing at all for a gene with no neighbour, so a gene alone on its contig
    never reaches the window table. Measured on the published *E. coli* catalogue: **2,352 of
    489,146 genes (0.48 %)**, which is entirely ordinary in draft assemblies whose mean contig holds
    ~14 genes. Building this frame from the windows alone left `gene_locus_membership` — a table
    whose docstring says *"exactly one row per gene"* — short by exactly that many, with nothing
    anywhere reporting it.

    ⚠ Those genes get a row with a **NULL arrangement rank**, which is a different fact from *"this
    genome has no gene at this locus"*. The page says the two in different words, and only a row can
    carry the second.
    """
    base = assign[["sample_id", "flat_index", "node"]].copy()
    base["sample_id"] = base["sample_id"].astype(str)
    if not len(windows) or not len(arrangement_frame):
        return base.assign(arrangement_rank=None)[
            ["node", "sample_id", "flat_index", "arrangement_rank"]
        ]

    columns = [f"s{index}" for index in range(len(slot_of))]
    gene_columns = ["node", "sample_id", "flat_index"]
    codes, unique = pandas.MultiIndex.from_frame(windows[gene_columns]).factorize()
    unique = unique.set_names(gene_columns)
    slots = windows["d"].map(slot_of)
    usable = slots.notna().to_numpy()
    matrix = numpy.full((len(unique), len(slot_of)), -1, dtype=numpy.int64)
    matrix[codes[usable], slots[usable].to_numpy(dtype=int)] = (
        windows["neigh_pos"].to_numpy(dtype=numpy.int64)[usable] * 2
        + windows["same_strand"].to_numpy().astype(numpy.int64)[usable]
    )
    genes = pandas.DataFrame(matrix, columns=columns)
    genes["node"] = unique.get_level_values("node")
    genes["sample_id"] = unique.get_level_values("sample_id")
    genes["flat_index"] = unique.get_level_values("flat_index")
    ranks = arrangement_frame[["node", *columns, "rank"]].rename(columns={"rank": "arrangement_rank"})
    windowed = genes.merge(ranks, on=["node", *columns], how="left")[
        ["node", "sample_id", "flat_index", "arrangement_rank"]
    ]
    windowed["sample_id"] = windowed["sample_id"].astype(str)
    # ⛔ LEFT join from the assignment, so every assigned gene has a row and the ones with no window
    # arrive with a NULL rank rather than being absent.
    return base.merge(
        windowed[["sample_id", "flat_index", "arrangement_rank"]],
        on=["sample_id", "flat_index"],
        how="left",
    )[["node", "sample_id", "flat_index", "arrangement_rank"]]


def _map_geometry(artifacts: CatalogueArtifacts, node_position, pandas):
    """Per representation, the projection's own metadata plus one geometry row per mapped locus.

    ⛔ **The siblings are addressed relative to the map**, `export_payload._sibling`'s own rule, so a
    map can never be paired with another run's neighbours or another run's cos6.
    """
    from syntitude_backend.ingest.artifact_locator import REPRESENTATIONS

    out: dict[str, dict] = {}
    locus_sets: dict[str, set] = {}
    for representation in REPRESENTATIONS:
        map_csv = artifacts.catalogue_map(representation)
        metadata_path = artifacts.catalogue_map_metadata(representation)
        info = dict(
            line.split("=", 1)
            for line in metadata_path.read_text().splitlines()
            if "=" in line
        )
        if not info.get("rep"):
            raise CatalogueFrameError(
                f"{metadata_path.name} names no `rep=` — with two representations on one card an "
                "unlabelled map would be attached to whichever tab came first"
            )
        coordinates = pandas.read_csv(map_csv, dtype={"node": str})
        neighbours = pandas.read_csv(
            artifacts.map_sibling(representation, "node_neighbours"),
            dtype={"node": str, "neighbour": str},
        )
        cosines = pandas.read_csv(
            artifacts.map_sibling(representation, "locus_cos6"), dtype={"node": str}
        )
        unknown = set(coordinates["node"]) - set(node_position)
        if unknown:
            raise CatalogueFrameError(
                f"{map_csv.name} carries {len(unknown):,} loci this catalogue does not have (e.g. "
                f"{sorted(unknown)[:3]}) — it was built from a different model or assignment."
            )
        locus_sets[representation] = set(coordinates["node"])
        first = next(iter(locus_sets))
        if locus_sets[representation] != locus_sets[first]:
            difference = len(locus_sets[representation] ^ locus_sets[first])
            raise CatalogueFrameError(
                f"the {representation} and {first} maps disagree about {difference:,} loci — they "
                "are not two views of one catalogue, so the tabs would compare different models"
            )
        out[representation] = {
            "info": info,
            "source": str(map_csv),
            "coordinates": coordinates,
            "neighbours": neighbours,
            "cosines": cosines,
        }
    return out


def _null_baselines(artifacts: CatalogueArtifacts, n_loci: int) -> dict:
    """The random-pair baseline per representation, guarded on model identity.

    ⚠ Without it a cosine has no meaning: ESM's random pairs sit at ~0.645 and Bacformer's at
    ~0.065, so the same "inter" reads oppositely in the two.
    """
    import pandas

    from syntitude_backend.ingest.artifact_locator import REPRESENTATIONS

    out: dict[str, dict] = {}
    for representation in REPRESENTATIONS:
        csv_path = artifacts.null_baseline(representation)
        metadata_path = artifacts.null_baseline_metadata(representation)
        info = dict(
            line.split("=", 1) for line in metadata_path.read_text().splitlines() if "=" in line
        )
        declared = info.get("n_loci")
        if declared and int(declared) != n_loci:
            raise CatalogueFrameError(
                f"{csv_path.name} was computed over {int(declared):,} loci but this catalogue has "
                f"{n_loci:,} — it is a different model. Re-run the null for this one."
            )
        histogram = pandas.read_csv(csv_path)
        out[representation] = {
            "lower_edge": float(histogram["lo"].iloc[0]),
            "width": float(histogram["hi"].iloc[0] - histogram["lo"].iloc[0]),
            "counts": [int(value) for value in histogram["count"]],
            "mean": float(info["mean"]) if info.get("mean") else None,
            "source": str(csv_path),
        }
    return out
