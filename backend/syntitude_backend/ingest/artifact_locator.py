"""Where every input of one catalogue lives — resolved once, checked all at once.

⛔ **This is derived from the naming conventions, NOT from `meta.audit.sources`.** That key
under-reports: the published *E. coli* payload names two artifacts (`_pfam_concordance.tsv` and
`_audit_summary.json`) while the export read **three** — the homology waterfall CSV supplied the
collapse tier, the resolved threshold and the ESM distance pair, and is never listed. A locator
built from it would silently omit the file three columns come from.

⛔ **Every missing artifact is reported together, and named.** One `FileNotFoundError` per run means
finding a second gap costs a second run; at eight artifact families and two representations that is
how a load takes an afternoon. `MissingArtifacts` lists all of them, with what each would have
supplied, so one look is enough.

⚠ **Three filename traps, all of them measured on the real store:**

1. **The output filename doubles the set token.** `locus_browser_{set}_{label}.json`, and `{label}`
   itself begins with the set — `locus_browser_ecoli_ecoli_nuna4_g2_0.98_…json`. A locator that
   assumes one `ecoli` finds nothing.
2. **The map's siblings are DERIVED, not passed.** `export_payload._sibling` finds the neighbour and
   cos6 CSVs by string-replacing `_catalogue_map_` in the map's own path, so they are addressed
   relative to it rather than rebuilt from the label. Reproduced here for the same reason: a map
   can then never be paired with another run's geometry.
3. **The payload JSON is not under `analysis/`.** The exporter writes it beside the maps on CSD3,
   but the local pull lands it in `data/browser/`. It is an ORACLE here, never an input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The two representations, in the payload's tab order — Bacformer first, because it is the axis
#: the method is about.
REPRESENTATIONS = ("bacformer", "esm")


class MissingArtifacts(FileNotFoundError):
    """Raised with EVERY absent required artifact, not the first one."""

    def __init__(self, missing: list[tuple[str, Path, str]]) -> None:
        self.missing = missing
        listing = "\n  ".join(
            f"{role:28s} {path}\n{'':30s} -> supplies {supplies}" for role, path, supplies in missing
        )
        super().__init__(f"{len(missing)} required artifact(s) absent:\n  {listing}")


@dataclass(frozen=True)
class CatalogueArtifacts:
    """Every input for one (species, model) catalogue, addressed from one data root.

    ``set_key`` is the dataset token in filenames (`ecoli`, `kp`) and ``species_key`` is the browser
    key. They are the same for the two published species and are kept separate anyway, because
    ``meta.species`` in the parquets is a THIRD vocabulary (`ecoli` | `kpneumoniae`) and collapsing
    any two of the three is how a load silently drops a whole species.
    """

    data_root: Path
    set_key: str
    model_label: str
    run_id: str
    species_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", Path(self.data_root).expanduser())
        if self.species_key is None:
            object.__setattr__(self, "species_key", self.set_key)
        if not self.model_label.startswith(f"{self.set_key}_"):
            raise ValueError(
                f"model_label {self.model_label!r} does not begin with the set token "
                f"{self.set_key + '_'!r}. Every artifact below is addressed by one or the other, "
                "and a mismatch resolves to paths that exist for a DIFFERENT catalogue."
            )

    # ── roots ─────────────────────────────────────────────────────────────────────────────────
    @property
    def processed_root(self) -> Path:
        """Everything the pipeline produced, as opposed to what it was given."""
        return self.data_root / "proc"

    @property
    def analysis_root(self) -> Path:
        """The audit, the assignments, the run manifests and the browser artifacts."""
        return self.processed_root / "analysis"

    @property
    def per_genome_root(self) -> Path:
        """The `{BS}_{meta,product,strand,dbxref,noncoding}.parquet` store."""
        return self.processed_root / "embeddings" / "meta"

    @property
    def annotation_root(self) -> Path:
        """`gff/<datasetID>/<BS>/<BS>.bakta.gff3.gz` — ⭐ the SEQUENCE source, and the only one."""
        return self.data_root / "raw" / "gff"

    # ── the run ───────────────────────────────────────────────────────────────────────────────
    @property
    def gene_universe(self) -> Path:
        """One row per gene in the set — the universe, and the genome vocabulary's own source."""
        return self.processed_root / "mmseqs" / f"{self.set_key}_close_seq.parquet"

    @property
    def assignment(self) -> Path:
        """One row per gene, exactly once — the loader raises otherwise."""
        return self.analysis_root / "step4_global_merge" / "assignments" / f"{self.run_id}.tsv"

    @property
    def run_manifest(self) -> Path:
        """⚠ Its `precluster_assign` is an ABSOLUTE CSD3 path, so the chain does not walk locally."""
        return self.analysis_root / "step4_global_merge" / "runs" / f"{self.run_id}.json"

    @property
    def pfam_architectures(self) -> Path:
        """One row per protein WITH a Pfam hit — absence is missing coverage, not a lack of domains."""
        return self.analysis_root / "pfam" / f"pfam_arch_{self.set_key}.parquet"

    # ── the audit ─────────────────────────────────────────────────────────────────────────────
    def _audit(self, suffix: str) -> Path:
        return self.analysis_root / "accessory_audit" / f"{self.model_label}_{suffix}"

    @property
    def homology_waterfall(self) -> Path:
        """⚠ **Not in `meta.audit.sources`**, and it supplied three of the payload's columns."""
        return self._audit("homology_waterfall.csv")

    @property
    def pfam_concordance(self) -> Path:
        """One row per locus, full coverage — the `class_clan` verdict is READ from here, never re-derived."""
        return self._audit("pfam_concordance.tsv")

    @property
    def audit_summary(self) -> Path:
        """The graded headline, and the guard that this audit describes THIS model."""
        return self._audit("audit_summary.json")

    @property
    def cluster_table(self) -> Path:
        """The six columns nothing else carries, plus the Bacformer distance pair.

        ⚠ **The published export did not read this** — it did not exist on CSD3 on 2026-08-25, so
        the page's `bac_d_*` were recomputed from the full embedding matrix instead. Measured
        against the shipped catalogue afterwards, the two derivations agree to 5.0e-5 on all 12,104
        measurable loci, which is the payload's own 4-significant-figure rounding. So this file is a
        sound source for them — but it is a *different artifact* than the page used, and the ingest
        records which one each column came from rather than leaving the reader to assume.
        """
        return self._audit("cluster_table.parquet")

    # ── the neighbourhood map ─────────────────────────────────────────────────────────────────
    def catalogue_map(self, representation: str) -> Path:
        """One row per locus medoid: the quantised map position."""
        return self.analysis_root / "locus_browser" / f"{self.model_label}_catalogue_map_{representation}.csv"

    def catalogue_map_metadata(self, representation: str) -> Path:
        """⚠ The `.meta` sidecar is the ONLY record of `rep`, `how` and `metric` — the CSV has none."""
        return self.catalogue_map(representation).with_suffix(".meta")

    def map_sibling(self, representation: str, kind: str) -> Path:
        """`node_neighbours` / `locus_cos6`, addressed RELATIVE to the map — `_sibling`'s own rule."""
        path = self.catalogue_map(representation)
        return path.with_name(path.name.replace("_catalogue_map_", f"_{kind}_"))

    def null_baseline(self, representation: str) -> Path:
        """200 uniform bins over (−1, 1) — the axis the geometry card reads its numbers against."""
        return self.analysis_root / "locus_browser" / f"{self.model_label}_null_{representation}.csv"

    def null_baseline_metadata(self, representation: str) -> Path:
        """The sidecar carrying the baseline's mean cosine, which the CSV itself does not."""
        return self.null_baseline(representation).with_suffix(".meta")

    # ── the oracle, which is never an input ───────────────────────────────────────────────────
    @property
    def published_payload(self) -> Path:
        """⛔ **The acceptance ORACLE.** Reading it into the database would make the test circular."""
        return self.data_root / "browser" / f"locus_browser_{self.set_key}_{self.model_label}.json"

    # ── per-genome ────────────────────────────────────────────────────────────────────────────
    def per_genome(self, sample_id: str, kind: str) -> Path:
        """`kind` ∈ `meta | product | strand | dbxref | noncoding`."""
        return self.per_genome_root / f"{sample_id}_{kind}.parquet"

    def genome_annotation(self, sample_id: str, bakrep_dataset_id: str) -> Path:
        """The gzipped Bakta GFF — annotation AND, in its `##FASTA` block, the bases."""
        return self.annotation_root / bakrep_dataset_id / sample_id / f"{sample_id}.bakta.gff3.gz"

    # ── checking ──────────────────────────────────────────────────────────────────────────────
    def required(self) -> list[tuple[str, Path, str]]:
        """`(role, path, what it supplies)` for everything that must exist to ingest at all."""
        items = [
            ("gene_universe", self.gene_universe, "the gene universe and the genome vocabulary"),
            ("assignment", self.assignment, "gene → locus, and the locus set"),
            ("run_manifest", self.run_manifest, "pangenome_step and the lineage edges"),
            ("pfam_architectures", self.pfam_architectures, "locus.pfam_annotated_member_count"),
            ("homology_waterfall", self.homology_waterfall, "collapse_tier, resolved_threshold, the ESM pair"),
            ("pfam_concordance", self.pfam_concordance, "pfam_architecture_count, pfam_concordance_class"),
            ("audit_summary", self.audit_summary, "pangenome_evaluation and the model-identity guard"),
        ]
        for rep in REPRESENTATIONS:
            items += [
                (f"catalogue_map[{rep}]", self.catalogue_map(rep), "locus map x/y"),
                (f"map_meta[{rep}]", self.catalogue_map_metadata(rep), "projection and metric"),
                (f"node_neighbours[{rep}]", self.map_sibling(rep, "node_neighbours"), "the 5 nearest medoids"),
                (f"locus_cos6[{rep}]", self.map_sibling(rep, "locus_cos6"), "the 6x6 local geometry"),
                (f"null[{rep}]", self.null_baseline(rep), "the random-pair baseline"),
                (f"null_meta[{rep}]", self.null_baseline_metadata(rep), "the baseline's mean cosine"),
            ]
        return items

    def optional(self) -> list[tuple[str, Path, str]]:
        """Present or absent is a FACT about the run, recorded rather than treated as a failure."""
        return [
            ("cluster_table", self.cluster_table, "u50 impurity/coverage, the medoid, the Bacformer pair"),
            ("published_payload", self.published_payload, "the acceptance oracle — never an input"),
        ]

    def verify(self) -> dict[str, bool]:
        """Raise naming EVERY absent required artifact; return which optional ones are present."""
        missing = [item for item in self.required() if not item[1].exists()]
        if missing:
            raise MissingArtifacts(missing)
        return {role: path.exists() for role, path, _ in self.optional()}
