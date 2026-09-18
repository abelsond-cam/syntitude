"""`/api/v1/species…` — the catalogue, one locus, its arrangements, its function tab, and search.

⭐ **Every response is immutable for a build**, because writes are ours alone and offline. So each
carries `ETag: "{pangenome_id}"` and a long `Cache-Control`, and the cache is a pure function of its
key with nothing that can invalidate it — the single largest payoff of the read-only scope.

⛔ **`locus_label` is the only locus identifier that appears in a URL.** It is the existing page's
hash, so every link a reader has saved keeps working, and it is durable across a re-export while the
surrogate id and the catalogue ordinal are not. The integer id appears only inside responses.

⚠ **A failed request and an empty result must never render the same.** The rule generalises from
`app.js:4604` — *"a sequence panel that fails silently is one a reader will read as 'this genome has
nothing here', which is a different claim and a false one"* — so a 404 says which of the species, the
pangenome or the locus was missing, and never returns an empty body with a 200.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from syntitude_backend.models.enumerations import EmbeddingRepresentation
from syntitude_backend.models.genome import Genome
from syntitude_backend.models.locus import Locus
from syntitude_backend.serialisers.locus_serialiser import (
    serialise_annotation_entry,
    serialise_arrangement,
    serialise_gene_sequence,
    serialise_locus_detail,
)
from syntitude_backend.services.audit_residual_service import load_audit_residuals
from syntitude_backend.services.gene_sequence_service import (
    SequenceUnavailable,
    load_gene_sequences,
)
from syntitude_backend.services.genome_listing_service import clamp_genome_limit, list_genomes
from syntitude_backend.services.locus_detail_service import (
    LocusNotFound,
    load_arrangement_page,
    load_function_block,
    load_locus_detail,
)
from syntitude_backend.services.locus_search_service import DEFAULT_RESULT_LIMIT, search_loci
from syntitude_backend.services.species_catalogue_service import (
    SpeciesNotPublished,
    list_published_species,
    load_scatter_sprite,
    load_species_catalogue,
    resolve_published_pangenome,
)

species_blueprint = Blueprint("species", __name__)

#: One day. Long, because a response cannot go stale without a deploy that changes the ETag.
CACHE_CONTROL = "public, max-age=86400"

#: Arrangements per page past the display cut.
ARRANGEMENT_PAGE_LIMIT = 50


def _immutable(payload, pangenome_id: int | None):
    """Attach the caching headers every response of a built catalogue is entitled to."""
    response = jsonify(payload)
    response.headers["Cache-Control"] = CACHE_CONTROL
    if pangenome_id is not None:
        response.headers["ETag"] = f'"{pangenome_id}"'
    return response


def _session():
    return current_app.extensions["syntitude_database"].session()


def _not_found(message: str):
    """⚠ A named 404, never an empty 200 — see the module docstring."""
    return jsonify({"error": "not_found", "detail": message}), 404


@species_blueprint.get("/species")
def get_species():
    """Every species and the pangenome it serves. Replaces `published.tsv`."""
    with _session() as session:
        rows = list_published_species(session)
        return _immutable(
            {
                "species": [
                    {
                        "key": species.species_key,
                        "scientific_name": species.scientific_name,
                        "ncbi_taxonomy_id": species.ncbi_taxonomy_id,
                        # ⚠ A species with nothing published is LISTED, with `null`. Filtering it
                        # out would read as though the species did not exist.
                        "published": pangenome is not None,
                        "genome_count": pangenome.genome_count if pangenome else None,
                        "gene_count": pangenome.gene_count if pangenome else None,
                        "locus_count": pangenome.locus_count if pangenome else None,
                        "model_label": None,
                    }
                    for species, pangenome in rows
                ]
            },
            None,
        )


@species_blueprint.get("/species/<species_key>")
def get_species_catalogue(species_key: str):
    """The census, the model provenance and the landing locus — everything before a locus."""
    with _session() as session:
        try:
            catalogue = load_species_catalogue(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))
        pangenome = catalogue.pangenome
        return _immutable(
            {
                "species": {
                    "key": catalogue.species.species_key,
                    "scientific_name": catalogue.species.scientific_name,
                },
                "pangenome": {
                    "run_id": pangenome.run_id,
                    "genome_count": pangenome.genome_count,
                    "gene_count": pangenome.gene_count,
                    "locus_count": pangenome.locus_count,
                    "built_at": pangenome.built_at,
                    "git_sha": pangenome.git_sha,
                    "exclusivity_form": pangenome.exclusivity_form.value,
                    # ⚠ An absent section is NAMED. The page prints these rather than showing an
                    # empty panel, so an omission is never mistaken for a measured zero.
                    "omitted_sections": pangenome.omitted_sections or {},
                },
                "model": (
                    {
                        "key": catalogue.model.model_key,
                        "label": catalogue.model.label,
                        "exclusivity_form": catalogue.model.exclusivity_form.value,
                        "knn_k": catalogue.model.knn_k,
                        "step_count": catalogue.model.step_count,
                    }
                    if catalogue.model
                    else None
                ),
                # ⭐ One row per pipeline stage, as the footer prints them — read from the run's own
                # manifests, never decoded from the run_id.
                "steps": [
                    {
                        "ordinal": step.step_ordinal,
                        "name": step.step_name,
                        "representation": step.representation.value if step.representation else None,
                        "gamma": step.gamma,
                        "rho_rule": step.rho_rule.value if step.rho_rule else None,
                        "rho_ceiling": step.rho_ceiling,
                        "uses_exclusivity": step.uses_exclusivity,
                        "stage_name": step.stage_name,
                        "stage_detail": step.stage_detail,
                    }
                    for step in catalogue.steps
                ],
                "provenance_rows": pangenome.provenance_rows or [],
                "prevalence_census": catalogue.prevalence_census,
                # ⭐ The same bands counted by GENE. Divided by `genome_count` this is the page's
                # "per genome" line, and its three parts sum to the whole by construction.
                "prevalence_gene_census": catalogue.prevalence_gene_census,
                "audit_headline": catalogue.audit_headline,
                "map_projections": [
                    {
                        "representation": projection.representation.value,
                        "method": projection.projection_method,
                        "requested_metric": projection.requested_metric,
                        "extent": [
                            projection.extent_min_x,
                            projection.extent_min_y,
                            projection.extent_max_x,
                            projection.extent_max_y,
                        ],
                        "cosine_scale_factor": projection.cosine_scale_factor,
                        # ⚠ Without the null baseline a cosine has no meaning: ESM's random pairs sit
                        # at ~0.645 and Bacformer's at ~0.065, so the same "inter" reads oppositely.
                        "null_mean_cosine": projection.null_mean_cosine,
                        "null_bin_lower_edge": projection.null_bin_lower_edge,
                        "null_bin_width": projection.null_bin_width,
                        "null_bin_counts": projection.null_bin_counts,
                        # ⭐ The other half of "p12 of 12,104 loci".
                        "separation_measurable_locus_count": projection.separation_measurable_locus_count,
                        # ⭐ The whole-catalogue dust, which is a PICTURE — the descriptor only, and
                        # `null` where this representation has no sprite. Its bytes come from
                        # `/map/{rep}/scatter.png`; the viewport in here is what the client projects
                        # the six foreground dots with, and it must not compute one of its own.
                        "scatter_sprite": catalogue.scatter_sprites.get(projection.representation.value),
                    }
                    for projection in catalogue.map_projections
                ],
                "landing_locus": catalogue.landing_locus_label,
                "example_loci": catalogue.example_locus_labels,
                "example_locus_rows": catalogue.example_locus_rows,
            },
            pangenome.pangenome_id,
        )


@species_blueprint.get("/species/<species_key>/audit/residual-loci")
def get_audit_residual_loci(species_key: str):
    """Every locus grouped on context alone, and every Pfam conflict — two lists, each clickable.

    Fetched when the footer's list is opened. ⚠ The two lists are NOT disjoint: a locus can be both,
    and it then appears in both, exactly as the published footer listed it.
    """
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))
        residuals = load_audit_residuals(session, pangenome_id=pangenome.pangenome_id)

        def rows(entries):
            return [
                {
                    "label": entry.label,
                    "display_name": entry.display_name,
                    "prevalence_band": entry.prevalence_band,
                    "gene_count": entry.gene_count,
                    "uniref50_family_count": entry.uniref50_family_count,
                    "pfam_architecture_count": entry.pfam_architecture_count,
                    "syntenic_a5": entry.syntenic_a5,
                    # ⚠ DISTANCES, as stored. The footer has always shown similarities; the client
                    # converts, exactly as it does for the locus card, so there is one conversion.
                    "esm_within_medoid_distance": entry.esm_within_medoid_distance,
                    "esm_nearest_medoid_distance": entry.esm_nearest_medoid_distance,
                }
                for entry in entries
            ]

        return _immutable(
            {
                "grouped_on_context_alone": rows(residuals.grouped_on_context_alone),
                "pfam_conflicts": rows(residuals.pfam_conflicts),
            },
            pangenome.pangenome_id,
        )


def _resolve_pangenome(session, species_key: str):
    # ⛔ One statement. See `resolve_published_pangenome` for what this used to cost every route.
    return resolve_published_pangenome(session, species_key)


@species_blueprint.get("/species/<species_key>/map/<representation>/scatter.png")
def get_catalogue_scatter_sprite(species_key: str, representation: str):
    """⭐ The whole catalogue as one picture — the only endpoint that does not return JSON.

    Every other thing the map needs is a number. The dust behind the six dots is the one part that
    is O(catalogue): 889,160 positions at the design target, sent to draw a texture out of which no
    reader ever reads a value.

    ⚠ **Its ETag is the CONTENT digest, not the pangenome id.** Every JSON response here is keyed on
    the build because a build is what changes it; an image, though, is cached hard and for a long
    time by browsers and proxies we do not control, so a re-render under the same pangenome id has
    to be able to invalidate it. The client also appends the digest as `?v=`, which makes the URL
    itself immutable and the cache entry permanent.
    """
    if representation not in {member.value for member in EmbeddingRepresentation}:
        return _not_found(f"no representation {representation!r}")

    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))

        sprite = load_scatter_sprite(session, pangenome.pangenome_id, representation)
        # ⛔ A missing sprite is a 404 that SAYS SO, never an empty 200 and never a blank PNG: a
        # blank square reads as "this catalogue has no loci anywhere", which is a different claim
        # and a false one.
        if sprite is None:
            return _not_found(
                f"{species_key} has no {representation} scatter sprite — its catalogue map was "
                "never built for that representation"
            )

        etag = f'"{sprite.content_digest}"'
        if request.if_none_match.contains_weak(sprite.content_digest):
            response = current_app.response_class(status=304)
        else:
            response = current_app.response_class(sprite.image_png, mimetype=sprite.image_media_type)
        response.headers["ETag"] = etag
        # `immutable` on top of the year: the URL carries the digest, so this exact URL can never
        # describe different bytes.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


@species_blueprint.get("/species/<species_key>/loci/<path:locus_label>")
def get_locus(species_key: str, locus_label: str):
    """⭐ The hot path. One round trip, and the popover is then offline.

    `anchor` names a genome by `sample_id`; given one, the arrangement that genome carries is
    included even if it sits past the display cap.
    """
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))

        anchor_genome_id = None
        anchor = request.args.get("anchor")
        if anchor:
            from sqlalchemy import select

            from syntitude_backend.models.genome import Genome

            anchor_genome_id = session.execute(
                select(Genome.genome_id).where(Genome.sample_id == anchor)
            ).scalar_one_or_none()
            if anchor_genome_id is None:
                return _not_found(f"no genome {anchor!r}")

        try:
            detail = load_locus_detail(
                session,
                pangenome_id=pangenome.pangenome_id,
                node_label=locus_label,
                anchor_genome_id=anchor_genome_id,
            )
        except LocusNotFound as error:
            return _not_found(str(error))

        payload = serialise_locus_detail(detail)
        payload["resolved_neighbour_count"] = detail.resolved_neighbour_count
        return _immutable(payload, pangenome.pangenome_id)


@species_blueprint.get("/species/<species_key>/loci/<path:locus_label>/arrangements")
def get_locus_arrangements(species_key: str, locus_label: str):
    """Arrangements past the display cut — the full scroller, paged."""
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))
        try:
            detail = load_locus_detail(
                session,
                pangenome_id=pangenome.pangenome_id,
                node_label=locus_label,
                arrangement_limit=0,
            )
        except LocusNotFound as error:
            return _not_found(str(error))
        offset = max(0, request.args.get("offset", default=0, type=int))
        page = load_arrangement_page(
            session, locus_id=detail.locus.locus_id, offset=offset, limit=ARRANGEMENT_PAGE_LIMIT
        )
        return _immutable(
            {
                "arrangements": [
                    serialise_arrangement(arrangement, detail.neighbour_display_rows)
                    for arrangement in page
                ],
                "offset": offset,
                "total": detail.locus.total_arrangement_count,
            },
            pangenome.pangenome_id,
        )


@species_blueprint.get("/species/<species_key>/loci/<path:locus_label>/function")
def get_locus_function(species_key: str, locus_label: str):
    """The EggNOG tab — fetched on tab open, not on every walk."""
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))
        try:
            detail = load_locus_detail(
                session,
                pangenome_id=pangenome.pangenome_id,
                node_label=locus_label,
                arrangement_limit=0,
            )
        except LocusNotFound as error:
            return _not_found(str(error))
        locus = detail.locus
        grouped = load_function_block(session, locus_id=locus.locus_id)
        return _immutable(
            {
                "annotations": {
                    kind: [serialise_annotation_entry(entry) for entry in entries]
                    for kind, entries in grouped.items()
                },
                # ⛔ Coverage BEFORE every verdict, and against the LOCUS size — a share against the
                # annotated subset would read 100 % where one gene in forty carries a label.
                "coverage": {
                    "gene_count": locus.member_gene_count,
                    "cog_annotated_gene_count": locus.cog_annotated_member_count,
                    # ⛔ A COUNT, never a relation: COG ids are single-valued per gene, so two in one
                    # locus is an ordinary consequence of grouping above family level.
                    "cog_distinct_id_count": locus.cog_distinct_id_count,
                    "modal_cog_categories": locus.modal_cog_categories,
                    "ec_annotated_gene_count": locus.ec_annotated_member_count,
                    "kegg_annotated_gene_count": locus.kegg_annotated_member_count,
                    "go_annotated_gene_count": {
                        "molecular_function": locus.go_annotated_member_count_molecular_function,
                        "biological_process": locus.go_annotated_member_count_biological_process,
                        "cellular_component": locus.go_annotated_member_count_cellular_component,
                    },
                },
                "go_verdicts": {
                    # ⛔ `no_coverage` is a VALUE, not a null: fewer than two annotated members is
                    # neither agreement nor disagreement and must never be counted as either.
                    "molecular_function": _verdict_value(locus.go_verdict_molecular_function),
                    "biological_process": _verdict_value(locus.go_verdict_biological_process),
                    "cellular_component": _verdict_value(locus.go_verdict_cellular_component),
                },
            },
            pangenome.pangenome_id,
        )


def _verdict_value(verdict):
    return verdict.value if verdict is not None else None


@species_blueprint.get("/species/<species_key>/genomes/<sample_id>/loci/<path:locus_label>/sequence")
def get_gene_sequence(species_key: str, sample_id: str, locus_label: str):
    """⭐ The Sequence tab — a gene's DNA, its flanks and its protein, sliced from the original GFF.

    ⚠ **~5 kB out, where the published page pulled 1.3 MB in.** It had to: GitHub Pages applies
    `Range` to the compressed stream, so the browser fetched whole `.nseq` files and decoded DNA
    itself. A server slices the file Bakta wrote, and the custom format is retired rather than ported.

    ⛔ **Three different answers, and they must never look alike.** A genome with no gene at this
    locus is an ANSWER (`genes: []`); a gene whose bases could not be read is a FAILURE with a named
    reason; a locus or genome that does not exist is a 404. The published page's own rule, at
    `app.js:4604`: *"a sequence panel that fails silently is one a reader will read as 'this genome
    has nothing here', which is a different claim and a false one."*
    """
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))

        genome_id = session.execute(
            select(Genome.genome_id).where(Genome.sample_id == sample_id)
        ).scalar_one_or_none()
        if genome_id is None:
            return _not_found(f"no genome {sample_id!r}")
        locus_id = session.execute(
            select(Locus.locus_id).where(
                Locus.pangenome_id == pangenome.pangenome_id, Locus.node_label == locus_label
            )
        ).scalar_one_or_none()
        if locus_id is None:
            return _not_found(f"no locus {locus_label!r} in {species_key}")

        configuration = current_app.config["SYNTITUDE"]
        try:
            gff_root = configuration.artifact_roots["gff"]
        except KeyError:
            # ⚠ A configuration failure, named as one. "Not configured" and "the file is missing"
            # are indistinguishable in a 404, and only one of them is ours to fix.
            return (
                jsonify(
                    {
                        "error": "sequence_unavailable",
                        "detail": "this server has no annotation store configured, so no sequence "
                        "can be read (set SYNTITUDE_ROOT_GFF)",
                    }
                ),
                503,
            )

        try:
            rows = load_gene_sequences(
                session,
                pangenome_id=pangenome.pangenome_id,
                node_label=locus_label,
                sample_id=sample_id,
                gff_root=gff_root,
            )
        except SequenceUnavailable as error:
            # ⛔ 503, not 404 and not an empty list: the gene is there and we could not read it.
            return jsonify({"error": "sequence_unavailable", "detail": str(error)}), 503

        return _immutable(
            {
                "genome": {"sample_id": sample_id},
                "locus": {"label": locus_label},
                # ⭐ A LIST, because rho > 1 puts one genome in a locus twice — and an empty one is
                # the answer "this genome has no gene here", not a failure.
                "genes": [serialise_gene_sequence(row) for row in rows],
            },
            pangenome.pangenome_id,
        )


@species_blueprint.get("/species/<species_key>/search")
def get_search(species_key: str):
    """Substring search, with the same semantics the page has today. Replaces the 3.0 MB `HAY`."""
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))
        limit = min(request.args.get("limit", default=DEFAULT_RESULT_LIMIT, type=int), 100)
        result = search_loci(
            session,
            pangenome_id=pangenome.pangenome_id,
            query=request.args.get("q", default="", type=str),
            limit=limit,
        )
        return _immutable(
            {
                "query": result.query,
                # ⚠ Which mode answered. A 1–2 character query searches less of the haystack, and a
                # reader is entitled to know that rather than to conclude the catalogue is empty.
                "mode": result.mode,
                "truncated": result.truncated,
                "hits": [
                    {
                        "label": hit.node_label,
                        "display_name": hit.display_name,
                        "best_product": hit.best_product,
                        "gene_count": hit.member_gene_count,
                        "genome_count": hit.member_genome_count,
                        "prevalence_band": hit.prevalence_band,
                        "rank_band": hit.rank_band,
                    }
                    for hit in result.hits
                ],
            },
            pangenome.pangenome_id,
        )


@species_blueprint.get("/species/<species_key>/genomes")
def get_genomes(species_key: str):
    """The anchor control's list — `meta.genomes` + `anchorSearch` + `GENOME_N`, as one query.

    `q` is a case-insensitive literal substring of the accession (empty matches every genome) and
    `limit` defaults to 100, held to [1, 1000]. ⭐ Two statements whatever either asks for: one to
    resolve the species, one for the genomes — their counts are READ from what ingest stored, never
    aggregated here.

    ⚠ **The ETag stays `"{pangenome_id}"` although `q` and `limit` change the body.** An entity tag
    distinguishes representations of ONE resource (RFC 9110 §8.8.3), and the query string is part of
    the target URI — so `?q=SAMEA2` and `?q=SAMEA3` are two resources, each cached and revalidated
    under its own URI, and for any one URI the body changes only when the pangenome does. Folding `q`
    into the tag would add nothing a cache uses; a cache keyed on the path alone would be broken by
    `max-age` long before any ETag was consulted. `/search` relies on the same reading.
    """
    with _session() as session:
        try:
            pangenome = _resolve_pangenome(session, species_key)
        except SpeciesNotPublished as error:
            return _not_found(str(error))
        listing = list_genomes(
            session,
            pangenome,
            query=request.args.get("q", default="", type=str),
            limit=clamp_genome_limit(request.args.get("limit", type=int)),
        )
        return _immutable(
            {
                "species_key": species_key,
                "query": listing.query,
                "genome_count": listing.genome_count,
                # ⛔ Before the limit. A list cut at the limit must not read as the whole answer.
                "matched_genome_count": listing.matched_genome_count,
                "truncated": listing.truncated,
                "genomes": [
                    {
                        "sample_id": genome.sample_id,
                        "collection_genome_ordinal": genome.collection_genome_ordinal,
                        # ⛔ TWO counts, and they are different facts: loci where the genome has a
                        # gene, and loci where it sits in an arrangement — the second is what the
                        # published dropdown printed. They differ for every probe genome.
                        "locus_count": genome.locus_count,
                        "arrangement_locus_count": genome.arrangement_locus_count,
                    }
                    for genome in listing.genomes
                ],
            },
            pangenome.pangenome_id,
        )
