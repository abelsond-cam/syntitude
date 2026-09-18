"""The catalogue-level blocks the page SHELL renders — census, example chips, search rows, residuals.

Each exists because assembling the page found the API could not answer something the published page
shows on every load: the per-genome census line, a named example chip, the product under a search
hit, and the footer's two residual lists. Each test pins the new field against a number stored
independently of it, so a wrong sum or a wrong join cannot pass by agreeing with itself.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from syntitude_backend.application_factory import create_application
from syntitude_backend.configuration import Configuration
from syntitude_backend.instruments.sql_cost_oracle import SqlCostOracle
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.pathogen_species import PathogenSpecies
from syntitude_backend.services import audit_residual_service

SPECIES_KEYS = ("ecoli", "kp")


@pytest.fixture(scope="module")
def application():
    url = os.environ.get("SYNTITUDE_DATABASE_URL")
    if not url:
        pytest.skip("SYNTITUDE_DATABASE_URL is not set — these run against a loaded database")
    engine = create_engine(url, future=True)
    with Session(engine) as session:
        published = session.execute(
            select(func.count())
            .select_from(PathogenSpecies)
            .where(PathogenSpecies.published_pangenome_id.is_not(None))
        ).scalar_one()
    if published < 2:
        pytest.skip(f"only {published} species are published in {url}; run the loader with --publish")
    return create_application(Configuration(database_url=url))


@pytest.fixture(scope="module")
def client(application):
    return application.test_client()


def _pangenome_id(application, species_key):
    engine = application.extensions["syntitude_database"].engine
    with Session(engine) as session:
        return session.execute(
            select(PathogenSpecies.published_pangenome_id).where(PathogenSpecies.species_key == species_key)
        ).scalar_one()


# ── the census, by gene ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("species_key", SPECIES_KEYS)
def test_the_GENE_census_partitions_every_modelled_gene_into_exactly_one_band(client, species_key):
    """⛔ Summed against `pangenome.gene_count`, which ingest wrote from a DIFFERENT artifact.

    Every gene sits in exactly one locus and every locus in exactly one band, so the per-band gene
    totals must sum to the catalogue's gene count — the identity the page's "per genome" line relies
    on when it presents its three parts as the whole.
    """
    payload = client.get(f"/api/v1/species/{species_key}").get_json()
    genes = payload["prevalence_gene_census"]
    assert set(genes) == set(payload["prevalence_census"])
    assert sum(genes.values()) == payload["pangenome"]["gene_count"]
    # A band with loci has genes, and one with none has none: the two censuses describe one partition.
    for band, loci in payload["prevalence_census"].items():
        assert (loci == 0) == (genes[band] == 0), band


def test_the_species_response_still_costs_what_it_did(application):
    """The gene sums ride in the band statement; the census must not become two reads."""
    client = application.test_client()
    with SqlCostOracle(application.extensions["syntitude_database"].engine) as report:
        assert client.get("/api/v1/species/ecoli").status_code == 200
    grouped = [
        record.summary() for record in report.statements
        if "GROUP BY" in record.sql.upper() and "prevalence_band" in record.sql
    ]
    assert len(grouped) == 1, grouped


# ── the example chips ───────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("species_key", SPECIES_KEYS)
def test_every_example_chip_is_NAMED_and_in_the_order_the_ranking_chose(client, application, species_key):
    payload = client.get(f"/api/v1/species/{species_key}").get_json()
    rows = payload["example_locus_rows"]
    assert [row["label"] for row in rows] == payload["example_loci"]
    assert rows, "a catalogue with no example loci would leave the documentation tab's chip row empty"
    engine = application.extensions["syntitude_database"].engine
    with Session(engine) as session:
        stored = dict(
            session.execute(
                select(Locus.node_label, Locus.display_name).where(
                    Locus.pangenome_id == _pangenome_id(application, species_key),
                    Locus.node_label.in_(payload["example_loci"]),
                )
            ).all()
        )
    for row in rows:
        assert row["display_name"] == stored[row["label"]]
        # The chips exist to show loci UniRef50 files under several families (`render_page._examples`).
        assert row["uniref50_family_count"] is not None and row["uniref50_family_count"] > 1


# ── search rows ─────────────────────────────────────────────────────────────────────────────────
def test_every_search_hit_carries_the_product_the_page_prints_under_its_name(client, application):
    hits = client.get("/api/v1/species/ecoli/search", query_string={"q": "ligase", "limit": 40}).get_json()["hits"]
    assert len(hits) > 5
    engine = application.extensions["syntitude_database"].engine
    with Session(engine) as session:
        stored = dict(
            session.execute(
                select(Locus.node_label, Locus.best_product).where(
                    Locus.pangenome_id == _pangenome_id(application, "ecoli"),
                    Locus.node_label.in_([hit["label"] for hit in hits]),
                )
            ).all()
        )
    assert {hit["label"]: hit["best_product"] for hit in hits} == stored
    # ⭐ `ligase` is found MID-string in products, so at least one hit must show it there — otherwise
    # this fixture would not exercise the field at all.
    assert any("ligase" in (hit["best_product"] or "").lower() for hit in hits)


# ── the residual lists ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("species_key", SPECIES_KEYS)
def test_the_residual_lists_are_exactly_the_ones_the_AUDIT_counted(client, species_key):
    """⛔ Each list's length is checked against the audit's OWN headline, read verbatim at ingest.

    The lists are selected from per-locus tiers and the headline is a number from the audit summary —
    two artifacts. If the vendored tiers drifted from nuna's, or the tier column were mis-loaded, the
    footer would list a different set of loci from the one its own headline counts.
    """
    catalogue = client.get(f"/api/v1/species/{species_key}").get_json()
    headline = catalogue["audit_headline"]
    reply = client.get(f"/api/v1/species/{species_key}/audit/residual-loci")
    assert reply.status_code == 200
    assert reply.headers["ETag"]
    lists = reply.get_json()
    context_alone = lists["grouped_on_context_alone"]
    conflicts = lists["pfam_conflicts"]
    assert len(context_alone) == headline["synteny_only_n_clusters"] + headline["no_homology_n_clusters"]
    assert len(conflicts) == headline["pfam_conflict_n_clusters"]
    assert context_alone and conflicts, "both lists are non-empty on both probe catalogues"
    for row in context_alone + conflicts:
        assert row["gene_count"] >= 1
        assert row["prevalence_band"] in catalogue["prevalence_census"]


def test_an_unpublished_species_has_no_residuals_and_SAYS_so(client):
    reply = client.get("/api/v1/species/nosuch/audit/residual-loci")
    assert reply.status_code == 404
    assert reply.get_json()["detail"]


def test_the_residual_lists_are_ONE_statement(application):
    client = application.test_client()
    with SqlCostOracle(application.extensions["syntitude_database"].engine) as report:
        assert client.get("/api/v1/species/kp/audit/residual-loci").status_code == 200
    # Both lists come from one read of `locus`; resolving the species is separate and does not touch it.
    locus_reads = [record.summary() for record in report.statements if "FROM locus" in record.sql]
    assert len(locus_reads) == 1, locus_reads


def test_the_vendored_audit_policy_is_nuna_s_own():
    """⛔ The serving side cannot import nuna, so it carries a copy — and a copy must be checked."""
    export_payload = pytest.importorskip("nuna.tl.locus_browser.export_payload")
    assert tuple(export_payload.POLICY["failure_tiers"]) == audit_residual_service.FAILURE_TIERS
    assert export_payload.POLICY["contested_pfclass"] == audit_residual_service.CONTESTED_PFAM_CLASS


# ── the anchor, across species ──────────────────────────────────────────────────────────────────
def test_a_genome_OUTSIDE_this_catalogue_is_a_named_404_for_the_anchor_AND_the_sequence(client):
    """⛔ Unscoped, it read as "anchored, and this genome has no gene here" — about a genome that is
    not in this pangenome at all, which is a different and false claim."""
    kp_genome = client.get("/api/v1/species/kp/genomes", query_string={"limit": 1}).get_json()["genomes"][0]
    reply = client.get("/api/v1/species/ecoli/loci/2811", query_string={"anchor": kp_genome["sample_id"]})
    assert reply.status_code == 404
    assert "ecoli" in reply.get_json()["detail"]
    # ⛔⛔ And a genome of the right SPECIES that this pangenome never modelled: the database holds
    # 122 ecoli genomes against a 100-genome collection.
    engine = client.application.extensions["syntitude_database"].engine
    with Session(engine) as session:
        from syntitude_backend.models.genome import Genome
        from syntitude_backend.models.genome_collection import GenomeCollectionMembership
        from syntitude_backend.models.pangenome import Pangenome

        collection_id = session.execute(
            select(Pangenome.genome_collection_id).where(
                Pangenome.pangenome_id == _pangenome_id(client.application, "ecoli")
            )
        ).scalar_one()
        outsider = session.execute(
            select(Genome.sample_id)
            .join(PathogenSpecies, PathogenSpecies.pathogen_species_id == Genome.pathogen_species_id)
            .where(
                PathogenSpecies.species_key == "ecoli",
                Genome.genome_id.not_in(
                    select(GenomeCollectionMembership.genome_id).where(
                        GenomeCollectionMembership.genome_collection_id == collection_id
                    )
                ),
            )
            .limit(1)
        ).scalar_one()
    for path in ("/api/v1/species/ecoli/loci/2811", f"/api/v1/species/ecoli/genomes/{outsider}/loci/2811/sequence"):
        query = {"anchor": outsider} if "sequence" not in path else {}
        outside = client.get(path, query_string=query)
        assert outside.status_code == 404, (path, outside.status_code)
        assert "catalogue" in outside.get_json()["detail"]
    # …while a genome of the RIGHT catalogue still anchors.
    ecoli_genome = client.get("/api/v1/species/ecoli/genomes", query_string={"limit": 1}).get_json()["genomes"][0]
    anchored = client.get("/api/v1/species/ecoli/loci/2811", query_string={"anchor": ecoli_genome["sample_id"]})
    assert anchored.status_code == 200
    assert anchored.get_json()["anchor"]["is_anchored"] is True


# ── the popover's "outside the top N" ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("species_key", SPECIES_KEYS)
def test_wherever_a_position_left_members_out_it_lists_the_SAME_top_N(client, application, species_key):
    """⭐ The client DERIVES N from the list it was given (`TrackPanel`), because the export's
    `top_neighbours` setting is not in the database. That is exact only if every cut position lists
    the same number of occupants — pinned here over every position of both catalogues, not assumed.
    """
    from sqlalchemy import text

    engine = application.extensions["syntitude_database"].engine
    with Session(engine) as session:
        pangenome_id = _pangenome_id(application, species_key)
        rows = session.execute(
            text(
                """
                with listed as (
                  select o.locus_id, o.signed_offset, count(*) n, sum(o.member_gene_count) genes
                  from locus_offset_occupant o join locus l on l.locus_id = o.locus_id
                  where l.pangenome_id = :p group by 1, 2),
                obs as (
                  select l.locus_id, s.off, l.context_observed_member_counts[s.i] observed
                  from locus l,
                       (select i, (array[-5,-4,-3,-2,-1,1,2,3,4,5])[i] off from generate_series(1, 10) i) s
                  where l.pangenome_id = :p)
                select listed.n, count(*) from obs
                join listed on listed.locus_id = obs.locus_id and listed.signed_offset = obs.off
                where obs.observed > listed.genes group by 1
                """
            ),
            {"p": pangenome_id},
        ).all()
    counts = dict(rows)
    assert counts, "no position left anyone out — the derivation is untested on this catalogue"
    assert len(counts) == 1, f"cut positions list different numbers of occupants: {counts}"
    # ⚠ And it is the export's own setting as the published payload records it.
    import json

    from tests.conftest import PUBLISHED_SITE_CATALOGUE_DIR

    published = json.loads((PUBLISHED_SITE_CATALOGUE_DIR / f"{species_key}.json").read_text())
    assert next(iter(counts)) == published["meta"]["top_neighbours"]
