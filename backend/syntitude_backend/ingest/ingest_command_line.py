"""`python -m syntitude_backend.ingest` — the offline loader.

⛔ **Writes are OURS ALONE, and never on a request path.** This is the only thing in the package
that inserts, and it runs on a machine that has the cluster artifacts. The serving install has
neither them nor `nuna`.

⭐ **Every stage reports what it did, in counts.** A loader that prints "done" has told you nothing
you can check; one that prints `280 genomes · 1,436,421 genes · 0 refused` can be reconciled against
the store it read. A refusal is named with the genome and the check that caught it, and the run
continues — so one bad genome costs one line, not the whole load.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import syntitude_backend.models  # noqa: F401  (registers every table on the metadata)
from syntitude_backend.ingest.artifact_locator import CatalogueArtifacts
from syntitude_backend.ingest.genome_gene_alignment import GeneAlignmentError
from syntitude_backend.ingest.ingest_genome_gene_table import GenomeIngestError, ingest_one_genome
from syntitude_backend.ingest.ingest_pathogen_species import ingest_pathogen_species
from syntitude_backend.models.gene import Gene, GeneFunctionalAnnotation, GenomeNoncodingFeature
from syntitude_backend.models.genome import Genome, GenomeContig


@dataclass
class GenomeLayerReport:
    """The whole genome-layer load, in numbers that can be reconciled against the store."""

    genomes_loaded: int = 0
    genomes_refused: int = 0
    genes: int = 0
    contigs: int = 0
    functional_annotations: int = 0
    noncoding_features: int = 0
    seconds: float = 0.0
    refusals: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        """The report as the lines the CLI prints — counts first, then every refusal by name."""
        lines = [
            f"genome layer: {self.genomes_loaded:,} loaded, {self.genomes_refused:,} refused, "
            f"{self.seconds:.0f}s",
            f"  genes                  {self.genes:,}",
            f"  contigs                {self.contigs:,}",
            f"  functional annotations {self.functional_annotations:,}",
            f"  non-coding features    {self.noncoding_features:,}",
        ]
        for sample_id, reason in self.refusals:
            lines.append(f"  REFUSED {sample_id}: {reason}")
        for note in self.notes:
            lines.append(f"  NOTE {note}")
        return "\n".join(lines)


def discover_genomes(artifacts: CatalogueArtifacts) -> list[tuple[str, str]]:
    """`(sample_id, bakrep_dataset_id)` for every GFF in the store.

    ⚠ The dataset id is a PATH component and appears in no parquet — captured here or lost. The GFF
    sits one level deeper than `<BS>/`, which is why the glob has three segments and not two.
    """
    pairs = [
        (path.parent.name, path.parent.parent.name)
        for path in sorted(artifacts.annotation_root.glob("*/*/*.bakta.gff3.gz"))
    ]
    duplicates = {name for name, _ in pairs if sum(1 for other, _ in pairs if other == name) > 1}
    if duplicates:
        raise RuntimeError(
            f"{len(duplicates)} sample id(s) appear under more than one dataset directory: "
            f"{sorted(duplicates)[:5]}. One genome must resolve to one GFF, or the sequence "
            "endpoint would serve whichever the glob happened to reach first."
        )
    return pairs


def load_genome_layer(
    session: Session,
    artifacts: CatalogueArtifacts,
    *,
    limit: int | None = None,
    only: set[str] | None = None,
    progress_every: int = 25,
) -> GenomeLayerReport:
    """Load every genome in the store, one atomic transaction each."""
    report = GenomeLayerReport()
    species_ids = ingest_pathogen_species(session)
    session.commit()

    genomes = discover_genomes(artifacts)
    if only:
        genomes = [pair for pair in genomes if pair[0] in only]
    if limit:
        genomes = genomes[:limit]

    started = time.time()
    for index, (sample_id, dataset_id) in enumerate(genomes, start=1):
        try:
            one = ingest_one_genome(
                session, artifacts, sample_id=sample_id, bakrep_dataset_id=dataset_id,
                pathogen_species_ids=species_ids,
            )
            session.commit()
        except (GenomeIngestError, GeneAlignmentError, KeyError) as error:
            # ⛔ Roll back THIS genome and carry on. A genome is the unit of work, so one refusal
            # must not discard the 200 already loaded — and it must be named, not counted.
            session.rollback()
            report.genomes_refused += 1
            report.refusals.append((sample_id, str(error).replace("\n", " ")[:300]))
            continue
        report.genomes_loaded += 1
        report.genes += one.genes_written
        report.contigs += one.contigs_written
        report.functional_annotations += one.functional_annotations_written
        report.noncoding_features += one.noncoding_features_written
        report.notes.extend(one.notes)
        if progress_every and index % progress_every == 0:
            print(
                f"  {index}/{len(genomes)}  {report.genes:,} genes  {time.time() - started:.0f}s",
                file=sys.stderr, flush=True,
            )
    report.seconds = time.time() - started
    return report


def reconcile(session: Session, report: GenomeLayerReport) -> list[str]:
    """⛔ What the loader WROTE against what the table HOLDS — the two are not the same claim.

    A loader reporting its own writes confirms itself. This asks the database, and a difference means
    something else wrote (or deleted) rows underneath the run.
    """
    held = {
        "genes": session.execute(select(func.count()).select_from(Gene)).scalar_one(),
        "contigs": session.execute(select(func.count()).select_from(GenomeContig)).scalar_one(),
        "functional_annotations": session.execute(
            select(func.count()).select_from(GeneFunctionalAnnotation)
        ).scalar_one(),
        "noncoding_features": session.execute(
            select(func.count()).select_from(GenomeNoncodingFeature)
        ).scalar_one(),
        "genomes": session.execute(select(func.count()).select_from(Genome)).scalar_one(),
    }
    written = {
        "genes": report.genes, "contigs": report.contigs,
        "functional_annotations": report.functional_annotations,
        "noncoding_features": report.noncoding_features, "genomes": report.genomes_loaded,
    }
    return [
        f"{key}: wrote {written[key]:,} but the table holds {held[key]:,}"
        for key in written
        if written[key] != held[key]
    ]


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface. `--limit` and `--only` are smoke-run conveniences, not modes to load in."""
    parser = argparse.ArgumentParser(prog="python -m syntitude_backend.ingest", description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("~/developer/nuna/data"),
                        help="the local mirror of the cluster artifacts")
    parser.add_argument("--set-key", default="ecoli", help="the dataset token in filenames")
    parser.add_argument("--model-label", required=True, help="the audit's --model-label")
    parser.add_argument("--run-id", required=True, help="the assignment stem")
    parser.add_argument("--database-url", default=os.environ.get("SYNTITUDE_DATABASE_URL"))
    parser.add_argument("--stage", choices=("genomes",), default="genomes",
                        help="which layer to load; the pangenome layer lands next")
    parser.add_argument("--limit", type=int, help="stop after N genomes (a smoke run, not a mode)")
    parser.add_argument("--only", nargs="*", help="load only these sample ids")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a load and return a shell exit code: 0 clean, 1 refusals or unreconciled, 2 misconfigured."""
    args = build_parser().parse_args(argv)
    if not args.database_url:
        print("SYNTITUDE_DATABASE_URL is not set and --database-url was not given", file=sys.stderr)
        return 2

    artifacts = CatalogueArtifacts(
        data_root=args.data_root, set_key=args.set_key,
        model_label=args.model_label, run_id=args.run_id,
    )
    optional = artifacts.verify()
    print(f"artifacts: all {len(artifacts.required())} required present; optional {optional}")

    engine = create_engine(args.database_url, future=True)
    with Session(engine) as session:
        report = load_genome_layer(
            session, artifacts, limit=args.limit, only=set(args.only) if args.only else None
        )
        print(report.render())
        differences = reconcile(session, report)

    # ⚠ Reconciliation is only meaningful on a FULL load: a --limit or --only run writes a subset
    # into a table that may already hold more, so a difference there is expected, not a fault.
    if args.limit or args.only:
        print("reconciliation skipped: a partial load cannot be reconciled against the whole table")
    elif differences:
        print("RECONCILIATION FAILED:", file=sys.stderr)
        for difference in differences:
            print(f"  {difference}", file=sys.stderr)
        return 1
    else:
        print("reconciled: every count the loader reported is what the tables hold")
    return 1 if report.refusals else 0


if __name__ == "__main__":
    raise SystemExit(main())
