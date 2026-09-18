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

from syntitude_backend.models.enumerations import (
    EmbeddingRepresentation,
    EvaluationKind,
    PrevalenceBand,
)
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.locus_embedding_geometry import (
    LocusMapProjection,
    LocusMapScatterSprite,
)
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
    #: ⭐ The SAME catalogue partitioned by GENE — member genes summed per band. The page prints both
    #: (`app.js::renderPangenome`) because they answer different questions: a third of the loci are
    #: singletons, while a typical genome carries about fifty singleton genes. Given only the locus
    #: count a reader reasonably concludes the wrong thing about what is in a genome.
    prevalence_gene_census: dict = field(default_factory=dict)
    audit_headline: dict = field(default_factory=dict)
    map_projections: list = field(default_factory=list)
    #: ⚠ Descriptors ONLY — never the bytes. The species response is JSON and the sprite is a
    #: megabyte of PNG; they travel by different routes on purpose.
    scatter_sprites: dict = field(default_factory=dict)
    landing_locus_label: str | None = None
    example_locus_labels: list = field(default_factory=list)
    #: The example loci as the chips draw them — label, name and the UniRef50 families the chip
    #: quotes (`render_page._examples`). A label alone would have to be resolved per chip.
    example_locus_rows: list = field(default_factory=list)


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


def resolve_published_pangenome(session: Session, species_key: str) -> Pangenome:
    """The pangenome a species serves — ONE statement, for every route that is not the shell.

    ⛔⛔ **Not `load_species_catalogue(...).pangenome`.** That is the whole shell — the band census
    (a GROUP BY over every locus of the species), the audit headline, the projections, the sprite
    descriptors and the example chips — and every locus navigation, search keystroke and sequence
    view paid for it just to learn one integer. The cost oracle measured the SERVICES and so could
    not see it: at 17,531 loci it is a few milliseconds per click, at the 889,160-locus design target
    it is an aggregation over the whole catalogue on the hot path.
    """
    row = session.execute(
        select(PathogenSpecies.published_pangenome_id, Pangenome)
        .outerjoin(Pangenome, Pangenome.pangenome_id == PathogenSpecies.published_pangenome_id)
        .where(PathogenSpecies.species_key == species_key)
    ).one_or_none()
    if row is None:
        raise SpeciesNotPublished(f"no species {species_key!r}")
    if row.Pangenome is None:
        raise SpeciesNotPublished(
            f"{species_key!r} has no published pangenome. ⚠ That is a distinct state from 'no such "
            "species', and the picker says so rather than omitting it."
        )
    return row.Pangenome


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
    # ⚠ The gene sums ride in the SAME grouped statement: a second one would be a second read of the
    # same rows, and the cost oracle counts statements.
    counts = session.execute(
        select(Locus.prevalence_band, func.count(), func.sum(Locus.member_gene_count))
        .where(Locus.pangenome_id == pangenome.pangenome_id)
        .group_by(Locus.prevalence_band)
    ).all()
    catalogue.prevalence_census = {band.value: count for band, count, _ in counts}
    catalogue.prevalence_gene_census = {band.value: int(genes or 0) for band, _, genes in counts}
    for band in PrevalenceBand:
        # ⛔ A band with no loci is `0`, not absent: the page prints every band and an absent key
        # would render as a gap rather than as the measured zero it is.
        catalogue.prevalence_census.setdefault(band.value, 0)
        catalogue.prevalence_gene_census.setdefault(band.value, 0)

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
    catalogue.scatter_sprites = load_scatter_sprite_descriptors(session, pangenome.pangenome_id)

    wanted = [pangenome.landing_locus_id, *(pangenome.example_locus_ids or [])]
    rows = {
        row.locus_id: row
        for row in session.execute(
            select(
                Locus.locus_id,
                Locus.node_label,
                Locus.display_name,
                Locus.uniref50_family_count,
                Locus.uniref50_major_family_count,
            ).where(Locus.locus_id.in_([value for value in wanted if value is not None]))
        ).all()
    }
    landing = rows.get(pangenome.landing_locus_id)
    catalogue.landing_locus_label = landing.node_label if landing else None
    examples = [rows[locus_id] for locus_id in (pangenome.example_locus_ids or []) if locus_id in rows]
    catalogue.example_locus_labels = [row.node_label for row in examples]
    catalogue.example_locus_rows = [
        {
            "label": row.node_label,
            "display_name": row.display_name,
            # ⚠ The MAJOR family count, as the chip always quoted (`nodes.n_u50_major` over `n_u50`):
            # a locus with one real family and a scatter of one-member families is not the point
            # the chip is making. Falls back to the full count where no major count was measured.
            "uniref50_family_count": (
                row.uniref50_major_family_count
                if row.uniref50_major_family_count is not None
                else row.uniref50_family_count
            ),
        }
        for row in examples
    ]
    return catalogue


def load_scatter_sprite_descriptors(session: Session, pangenome_id: int) -> dict:
    """Everything about the whole-catalogue sprite EXCEPT its bytes, keyed by representation.

    ⛔ **The columns are named one by one, and that is the point.** `select(LocusMapScatterSprite)`
    would pull a megabyte of PNG into the species response's session for every page load, to send a
    dozen numbers. The blob has its own endpoint because it has its own content type, its own cache
    lifetime and its own ETag; this query must never be the thing that fetches it.
    """
    rows = session.execute(
        select(
            LocusMapScatterSprite.representation,
            LocusMapScatterSprite.pixel_size,
            LocusMapScatterSprite.viewport_centre_x,
            LocusMapScatterSprite.viewport_centre_y,
            LocusMapScatterSprite.viewport_span,
            LocusMapScatterSprite.dust_radius_pixels,
            LocusMapScatterSprite.alpha_per_locus,
            LocusMapScatterSprite.plotted_locus_count,
            LocusMapScatterSprite.unplotted_locus_count,
            LocusMapScatterSprite.content_digest,
        ).where(LocusMapScatterSprite.pangenome_id == pangenome_id)
    ).all()
    return {
        row.representation.value: {
            "pixel_size": row.pixel_size,
            # ⛔ The transform the renderer ACTUALLY used, in the quantised units of `map_x`/`map_y`.
            # The client projects the six foreground dots with exactly these, never with the extent:
            # a re-derived viewport puts the focal dot beside its own speck, not on it.
            "viewport_centre": [row.viewport_centre_x, row.viewport_centre_y],
            "viewport_span": row.viewport_span,
            "dust_radius_pixels": row.dust_radius_pixels,
            "alpha_per_locus": row.alpha_per_locus,
            # ⭐ Both counts. The published caption quoted the CATALOGUE size — a locus with no
            # medoid is not on this picture at all, and the page now says which number it means.
            "plotted_locus_count": row.plotted_locus_count,
            "unplotted_locus_count": row.unplotted_locus_count,
            # ⚠ The ETag, and the client's cache-buster. Not the pangenome id — an image is cached
            # hard by caches we do not control, so a re-render must be able to invalidate it.
            "content_digest": row.content_digest,
        }
        for row in rows
    }


def load_scatter_sprite(session: Session, pangenome_id: int, representation: str):
    """The sprite bytes and their digest, or `None` where this representation has no map."""
    return session.execute(
        select(
            LocusMapScatterSprite.image_png,
            LocusMapScatterSprite.image_media_type,
            LocusMapScatterSprite.content_digest,
        ).where(
            LocusMapScatterSprite.pangenome_id == pangenome_id,
            LocusMapScatterSprite.representation == EmbeddingRepresentation(representation),
        )
    ).one_or_none()
