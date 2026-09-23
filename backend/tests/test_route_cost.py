"""What each HTTP ROUTE costs — measured at the route, not at the service behind it.

⛔⛔ **Why this file exists.** Every cost test before it measured a SERVICE (`load_locus_detail`,
`search_loci`, `load_gene_sequences`), and every one passed, while every route that is not the shell
was resolving its species through `load_species_catalogue` — the whole shell, including a GROUP BY
over every locus of the species — to learn one integer. A locus click cost ~17 statements against a
budget of 9, and search paid a whole-catalogue aggregation on every keystroke. Nothing could see it,
because the thing measured was not the thing served.

So each budget here is the service's own logical minimum PLUS ONE statement to resolve the species,
derived rather than recorded, and one property is asserted for every route at once: **only the shell
may aggregate over the catalogue.**
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

from syntitude_backend.application_factory import create_application
from syntitude_backend.configuration import Configuration
from syntitude_backend.instruments.sql_cost_oracle import SqlCostOracle

#: Resolving `species_key` → its published pangenome: one statement, on every route.
SPECIES_RESOLUTION = 1

#: `test_api_endpoints.test_a_locus_view_issues_ONE_statement_PER_TABLE_and_no_more` derives this:
#: eight tables plus one neighbour-resolution statement.
LOCUS_VIEW_MINIMUM = 9

#: ⚠ A genome PROJECTED onto the ecoli catalogue, if one is loaded. The projection is an optional
#: addition to a published catalogue, so these two tests skip rather than fail where none exists —
#: a database without a projection is a valid database.
PROJECTED_SAMPLE_ID = os.environ.get("SYNTITUDE_PROJECTED_SAMPLE_ID", "SAMN05374479")


@pytest.fixture(scope="module")
def application():
    url = os.environ.get("SYNTITUDE_DATABASE_URL")
    if not url:
        pytest.skip("SYNTITUDE_DATABASE_URL is not set — route costs are measured on a loaded database")
    create_engine(url, future=True)
    return create_application(
        Configuration(
            database_url=url,
            artifact_roots={"gff": __import__("pathlib").Path(os.environ["SYNTITUDE_ROOT_GFF"])}
            if os.environ.get("SYNTITUDE_ROOT_GFF")
            else {},
        )
    )


def _measure(application, path, **query):
    client = application.test_client()
    with SqlCostOracle(application.extensions["syntitude_database"].engine) as report:
        response = client.get(path, query_string=query)
    assert response.status_code == 200, (path, response.status_code, response.get_data(as_text=True)[:300])
    return report


def _catalogue_aggregations(report):
    """Statements that aggregate over `locus` — the census's signature."""
    return [
        record.summary()
        for record in report.statements
        if "GROUP BY" in record.sql.upper() and "FROM locus" in record.sql
    ]


def test_a_locus_CLICK_costs_the_locus_view_plus_one(application):
    report = _measure(application, "/api/v1/species/ecoli/loci/2811")
    report.assert_at_most(LOCUS_VIEW_MINIMUM + SPECIES_RESOLUTION, what="one locus click, at the route")


def test_an_ANCHORED_locus_click_adds_exactly_the_genome_lookup(application):
    report = _measure(application, "/api/v1/species/ecoli/loci/2811", anchor="SAMEA103923484")
    report.assert_at_most(
        LOCUS_VIEW_MINIMUM + SPECIES_RESOLUTION + 1, what="one anchored locus click, at the route"
    )


def test_a_PROJECTED_locus_click_adds_the_genome_lookup_and_its_placements(application):
    """⚠ Two statements more than an unanchored click, and they are DIFFERENT statements from the
    anchor's: a projected genome is in no `member_genome_ids`, so it is resolved from
    `projected_genome` and its genes at this locus are read from `projected_gene_placement`. Both
    are index scans on `(pangenome_id, …)` — the point of the budget is that neither grows with the
    catalogue."""
    report = _measure(
        application, "/api/v1/species/ecoli/loci/2811", projected=PROJECTED_SAMPLE_ID
    )
    report.assert_at_most(
        LOCUS_VIEW_MINIMUM + SPECIES_RESOLUTION + 2, what="one projected locus click, at the route"
    )


def test_the_projected_genome_LIST_is_two_statements(application):
    """One to resolve the species, one to list. It is O(projected genomes), never O(catalogue)."""
    report = _measure(application, "/api/v1/species/ecoli/projected-genomes")
    report.assert_at_most(1 + SPECIES_RESOLUTION, what="the projected-genome list, at the route")


def test_a_search_KEYSTROKE_is_two_statements(application):
    report = _measure(application, "/api/v1/species/ecoli/search", q="ligase")
    report.assert_at_most(1 + SPECIES_RESOLUTION, what="one search keystroke, at the route")


def test_the_residual_lists_are_two_statements(application):
    report = _measure(application, "/api/v1/species/kp/audit/residual-loci")
    report.assert_at_most(1 + SPECIES_RESOLUTION, what="the footer's residual lists, at the route")


@pytest.mark.parametrize(
    "query",
    [{"limit": 1}, {"limit": 1000}, {"q": "samea22", "limit": 1000}, {"q": "NOT-A-GENOME"}],
)
def test_an_anchor_picker_KEYSTROKE_is_two_statements_whatever_the_limit(application, query):
    """⛔ The per-genome counts are READ. Aggregated here they would be ~412 M rows per keystroke.

    One statement for the genomes — their matched count rides on every row via a window, so it does
    not grow with the limit, the collection or the query — plus the species resolution.
    """
    report = _measure(application, "/api/v1/species/ecoli/genomes", **query)
    report.assert_at_most(1 + SPECIES_RESOLUTION, what="one anchor-picker keystroke, at the route")
    # ⛔ And no aggregation over a membership table at all: the counts come from their own table.
    assert not [
        record.summary()
        for record in report.statements
        if "GROUP BY" in record.sql.upper()
        or "gene_locus_membership" in record.sql
        or "unnest" in record.sql.lower()
    ]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/species/ecoli/loci/2811",
        "/api/v1/species/ecoli/loci/2811/function",
        "/api/v1/species/ecoli/loci/2811/arrangements",
        "/api/v1/species/ecoli/search?q=ligase",
        "/api/v1/species/kp/audit/residual-loci",
        "/api/v1/species/ecoli/genomes?q=samea22",
        "/api/v1/species/ecoli/projected-genomes",
    ],
)
def test_ONLY_the_shell_aggregates_over_the_catalogue(application, path):
    """⛔ The property the whole file exists for, over every per-locus and per-keystroke route."""
    route, _, query = path.partition("?")
    report = _measure(application, route, **dict(pair.split("=") for pair in query.split("&") if pair))
    assert _catalogue_aggregations(report) == []


def test_and_the_shell_DOES_aggregate_so_the_property_above_is_not_vacuous(application):
    report = _measure(application, "/api/v1/species/ecoli")
    assert len(_catalogue_aggregations(report)) == 1
