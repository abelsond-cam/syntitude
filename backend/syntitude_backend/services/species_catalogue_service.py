"""The species list and one species' census — everything the page needs before a locus.

⭐ **`published_pangenome_id` is the only pointer that decides what a species serves.** Ingest builds
a new generation alongside the live one and never touches it; `publish_pangenome` flips it in its own
transaction. That is what makes a re-ingest safe on a running service: the new catalogue is complete
and verified before anything points at it, and a rollback is the same one-row update backwards.

⚠ **The census is read, not counted per request.** `pangenome.genome_count` / `gene_count` /
`locus_count` are written by ingest and reconciled against the checked-in published triple, so the
number the page prints is the number the loader wrote and not a `COUNT(*)` that could disagree with
it after a partial write.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from syntitude_backend.models.enumerations import EvaluationKind, PrevalenceBand
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.locus_embedding_geometry import LocusMapProjection
from syntitude_backend.models.nuna_model import NunaModel
from syntitude_backend.models.pangenome import Pangenome, PangenomeEvaluation, PangenomeStep
from syntitude_backend.models.pathogen_species import PathogenSpecies

#: The audit headline keys the footer prints, in `export_payload.AUDIT_HEADLINE_KEYS` order.
#: ⛔ A whitelist, and copied verbatim — *"the page quoting a lookalike it derived itself is the
#: failure mode this exists to make impossible"*.
AUDIT_HEADLINE_KEYS = (
    "n_clusters_total", "n_genes_total", "n_singleton_clusters",
    "synteny_only_n_clusters", "synteny_only_n_genes", "synteny_only_gene_rate",
    "no_homology_n_clusters", "no_homology_n_genes", "no_homology_gene_rate",
    "over_merge_gene_rate", "over_merge_gene_rate_num",
    "split_gene_rate", "split_gene_rate_excl_singletons",
    "family_split_across_clusters_n_families",
    "pfam_conflict_n_clusters", "pfam_conflict_n_genes", "pfam_conflict_gene_rate",
    "pfam_judgeable_n_clusters", "pfam_no_coverage_n_clusters",
    "n_clusters_esm_rescued", "esm_rescued_gene_num",
)  # fmt: skip


class SpeciesNotPublished(LookupError):
    """The species exists, or does not, and either way it has nothing to serve."""


@dataclass
class SpeciesCatalogue:
    """One species' published pangenome, and everything the shell renders before a locus."""

    species: PathogenSpecies
    pangenome: Pangenome
    model: NunaModel | None = None
    steps: list = field(default_factory=list)
    prevalence_census: dict = field(default_factory=dict)
    audit_headline: dict = field(default_factory=dict)
    map_projections: list = field(default_factory=list)
    landing_locus_label: str | None = None
    example_locus_labels: list = field(default_factory=list)


def list_published_species(session: Session) -> list[tuple[PathogenSpecies, Pangenome | None]]:
    """Every species and the pangenome it serves — `published.tsv`, as a query.

    ⚠ A species with no published pangenome is RETURNED with `None`, not filtered out. The picker
    lists the others and says why they are unavailable; a silently short list would read as though
    the species did not exist.
    """
    rows = session.execute(
        select(PathogenSpecies, Pangenome)
        .outerjoin(Pangenome, Pangenome.pangenome_id == PathogenSpecies.published_pangenome_id)
        .order_by(PathogenSpecies.species_key)
    ).all()
    return [(species, pangenome) for species, pangenome in rows]


def load_species_catalogue(session: Session, species_key: str) -> SpeciesCatalogue:
    """The whole species shell in a fixed number of statements, none of them per locus."""
    species = session.execute(
        select(PathogenSpecies).where(PathogenSpecies.species_key == species_key)
    ).scalar_one_or_none()
    if species is None:
        raise SpeciesNotPublished(f"no species {species_key!r}")
    if species.published_pangenome_id is None:
        raise SpeciesNotPublished(
            f"{species_key!r} has no published pangenome. ⚠ That is a distinct state from 'no such "
            "species', and the picker says so rather than omitting it."
        )
    pangenome = session.get(Pangenome, species.published_pangenome_id)
    catalogue = SpeciesCatalogue(species=species, pangenome=pangenome)

    if pangenome.nuna_model_id is not None:
        catalogue.model = session.get(NunaModel, pangenome.nuna_model_id)
    catalogue.steps = list(
        session.execute(
            select(PangenomeStep)
            .where(PangenomeStep.pangenome_id == pangenome.pangenome_id)
            .order_by(PangenomeStep.step_ordinal)
        ).scalars()
    )

    # ⚠ The census IS counted, because it is a distribution rather than a total and no column holds
    # it. One grouped statement over an index, not one per band.
    counts = session.execute(
        select(Locus.prevalence_band, func.count())
        .where(Locus.pangenome_id == pangenome.pangenome_id)
        .group_by(Locus.prevalence_band)
    ).all()
    catalogue.prevalence_census = {band.value: count for band, count in counts}
    for band in PrevalenceBand:
        # ⛔ A band with no loci is `0`, not absent: the page prints every band and an absent key
        # would render as a gap rather than as the measured zero it is.
        catalogue.prevalence_census.setdefault(band.value, 0)

    catalogue.audit_headline = {
        row.metric_name: row.numeric_value if row.numeric_value is not None else row.detail
        for row in session.execute(
            select(PangenomeEvaluation).where(
                PangenomeEvaluation.pangenome_id == pangenome.pangenome_id,
                PangenomeEvaluation.evaluation_kind == EvaluationKind.ACCESSORY_AUDIT,
                PangenomeEvaluation.metric_name.in_(AUDIT_HEADLINE_KEYS),
            )
        ).scalars()
    }

    catalogue.map_projections = list(
        session.execute(
            select(LocusMapProjection).where(LocusMapProjection.pangenome_id == pangenome.pangenome_id)
        ).scalars()
    )

    wanted = [pangenome.landing_locus_id, *(pangenome.example_locus_ids or [])]
    labels = {
        locus_id: label
        for locus_id, label in session.execute(
            select(Locus.locus_id, Locus.node_label).where(
                Locus.locus_id.in_([value for value in wanted if value is not None])
            )
        ).all()
    }
    catalogue.landing_locus_label = labels.get(pangenome.landing_locus_id)
    catalogue.example_locus_labels = [
        labels[locus_id] for locus_id in (pangenome.example_locus_ids or []) if locus_id in labels
    ]
    return catalogue
