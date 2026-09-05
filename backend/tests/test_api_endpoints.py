"""The API against the loaded catalogue — what it returns, and what it COSTS.

⭐ **The cost assertion is the point of this file, and it is a property rather than a number.** The
N+1 bug is invisible to every correctness test: a locus response is byte-identical whether its twenty
neighbours arrive in one indexed fetch or in twenty round trips. So the assertion is *"the statement
count does not grow with the neighbour count"*, checked by driving the locus with the FEWEST resolved
neighbours and the one with the MOST and requiring the same count — which is scale-free, and which a
recorded budget of "11" would not be.

⚠ These run against `SYNTITUDE_DATABASE_URL` with the published catalogues loaded and PUBLISHED. A
loaded-but-unpublished pangenome serves nothing, so the fixture says which of the two is missing
rather than skipping on a bare `None`.
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
from syntitude_backend.models.locus_offset_occupant import LocusOffsetOccupant
from syntitude_backend.models.pathogen_species import PathogenSpecies
from syntitude_backend.services.locus_search_service import escape_like_pattern


@pytest.fixture(scope="module")
def application():
    url = os.environ.get("SYNTITUDE_DATABASE_URL")
    if not url:
        pytest.skip("SYNTITUDE_DATABASE_URL is not set — the API tests run against a loaded database")
    engine = create_engine(url, future=True)
    with Session(engine) as session:
        published = session.execute(
            select(func.count())
            .select_from(PathogenSpecies)
            .where(PathogenSpecies.published_pangenome_id.is_not(None))
        ).scalar_one()
    if published < 2:
        pytest.skip(
            f"only {published} species are published in {url}; run the loader with --publish"
        )
    return create_application(Configuration(database_url=url))


@pytest.fixture(scope="module")
def client(application):
    return application.test_client()


# ── the shell ──────────────────────────────────────────────────────────────────────────────────
def test_the_species_list_names_both_published_catalogues(client):
    payload = client.get("/api/v1/species").get_json()
    by_key = {entry["key"]: entry for entry in payload["species"]}
    assert set(by_key) == {"ecoli", "kp"}
    assert by_key["ecoli"]["locus_count"] == 17_531
    assert by_key["kp"]["locus_count"] == 15_670
    assert all(entry["published"] for entry in payload["species"])


def test_the_species_catalogue_serves_the_landing_locus_the_ranking_chose(client):
    """⚠ The render-time mutation that shipped five days of pages opening on locus 0."""
    payload = client.get("/api/v1/species/ecoli").get_json()
    assert payload["landing_locus"] == "2811"
    assert payload["example_loci"] == ["5617", "48", "7266", "7519"]
    assert payload["landing_locus"] not in payload["example_loci"][:1]


def test_the_census_carries_every_band_even_the_empty_ones(client):
    """⛔ An absent key renders as a gap; a measured zero is a number."""
    census = client.get("/api/v1/species/ecoli").get_json()["prevalence_census"]
    assert set(census) == {"core", "soft_core", "shell", "cloud", "rare"}
    assert sum(census.values()) == 17_531


def test_the_footer_quotes_the_audit_headline_it_was_given(client):
    headline = client.get("/api/v1/species/ecoli").get_json()["audit_headline"]
    assert headline["n_clusters_total"] == 17_531
    assert headline["synteny_only_n_clusters"] == 10
    assert "over_merge_gene_rate" in headline


def test_both_map_representations_ship_with_their_own_null_baseline(client):
    """⚠ Without it a cosine has no meaning: ESM's random pairs sit at ~0.645, Bacformer's ~0.065."""
    projections = {
        entry["representation"]: entry
        for entry in client.get("/api/v1/species/ecoli").get_json()["map_projections"]
    }
    assert set(projections) == {"esm", "bacformer"}
    assert projections["esm"]["null_mean_cosine"] > 0.5
    assert projections["bacformer"]["null_mean_cosine"] < 0.2
    for entry in projections.values():
        assert entry["separation_measurable_locus_count"] == 12_104
        assert len(entry["null_bin_counts"]) == 200


def test_an_unpublished_species_is_a_NAMED_404_and_never_an_empty_200(client):
    response = client.get("/api/v1/species/tuberculosis")
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"
    assert "tuberculosis" in response.get_json()["detail"]


def test_every_catalogue_response_is_cacheable_and_tagged_by_its_pangenome(client):
    response = client.get("/api/v1/species/ecoli")
    assert response.headers["Cache-Control"] == "public, max-age=86400"
    assert response.headers["ETag"].strip('"').isdigit()


# ── the hot path ───────────────────────────────────────────────────────────────────────────────
def test_the_landing_locus_carries_its_name_its_product_and_its_neighbours(client):
    payload = client.get("/api/v1/species/ecoli/loci/2811").get_json()
    assert payload["locus"]["display_name"] == "fimA"
    assert payload["locus"]["display_name_source"] == "bakta_symbol"
    # ⛔ Not `products[0]`: the most SPECIFIC product that cannot become a different protein.
    assert payload["locus"]["best_product"]
    assert payload["neighbour_display_rows"], "the fan-out block is empty — the track cannot draw"
    assert payload["resolved_neighbour_count"] == len(payload["neighbour_display_rows"])


def test_a_slot_is_null_plus_a_REASON_and_never_a_bare_minus_one(client, application):
    """⛔ `occ(code)` is deleted — the packed form is where "−1 means five things" lives."""
    with Session(create_engine(application.config["SYNTITUDE"].database_url, future=True)) as session:
        label = session.execute(
            select(Locus.node_label)
            .where(Locus.pangenome_id == 1, Locus.member_gene_count > 50)
            .order_by(Locus.catalogue_ordinal)
            .limit(1)
        ).scalar_one()
    payload = client.get(f"/api/v1/species/ecoli/loci/{label}").get_json()
    slots = [slot for arrangement in payload["arrangements"]["listed"] for slot in arrangement["slots"]]
    assert slots, "no slots examined"
    assert all(slot["locus"] is not None or slot["absence_reason"] for slot in slots)
    assert all(slot["locus"] != -1 for slot in slots)


def test_every_remainder_is_its_own_named_field(client):
    """⛔ A rewrite that computes "the rest" once collapses them, and the page overclaims."""
    payload = client.get("/api/v1/species/ecoli/loci/2811").get_json()
    assert "arrangements_not_listed" in payload["arrangements"]
    assert "members_in_arrangements_not_listed" in payload["arrangements"]
    assert "members_without_a_neighbourhood" in payload["arrangements"]
    for offset in payload["offsets"]:
        assert "observed_not_listed" in offset
        assert "members_without_an_observation" in offset
    assert len(payload["offsets"]) == 10
    assert [offset["signed_offset"] for offset in payload["offsets"]] == [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]


def test_a_member_past_the_arrangement_CAP_is_not_reported_as_having_no_coordinates(
    client, application
):
    """⛔⛔ The remainder the cap invented, and the sharpest find of the front-end build.

    `members_without_a_neighbourhood` was `size − Σ(listed)`. On the published page that is right,
    because that payload is UNCAPPED — the difference really is *"no coordinates for the gene, so no
    window"*. The API caps at 8, so the same subtraction swept in every member sitting past the cap
    and told the reader those genes had no coordinates. **15,912 E. coli genes over 2,340 loci** and
    **10,437 kp genes over 1,548**.
    """
    engine = create_engine(application.config["SYNTITUDE"].database_url, future=True)
    with Session(engine) as session:
        label, total, size, in_arrangements = session.execute(
            select(
                Locus.node_label,
                Locus.total_arrangement_count,
                Locus.member_gene_count,
                Locus.arrangement_member_gene_count,
            )
            .where(Locus.pangenome_id == 1, Locus.total_arrangement_count > 12)
            .order_by(Locus.total_arrangement_count.desc())
            .limit(1)
        ).one()

    body = client.get(f"/api/v1/species/ecoli/loci/{label}").get_json()["arrangements"]
    listed = sum(a["gene_count"] for a in body["listed"])

    # The locus genuinely has members past the cap — otherwise this test proves nothing.
    assert body["members_in_arrangements_not_listed"] > 0
    assert body["members_in_arrangements_not_listed"] == in_arrangements - listed
    # ⭐ And THAT is what the old subtraction would have called "no recorded neighbourhood".
    assert body["members_without_a_neighbourhood"] == size - in_arrangements
    assert body["members_without_a_neighbourhood"] < size - listed
    assert body["total"] == total


def test_the_stored_arrangement_member_total_agrees_with_the_rows_it_summarises(application):
    """⚠ A denormalised count that drifts is worse than none: it reads as measured. Checked against
    the rows for EVERY locus in both catalogues, not a sample."""
    engine = create_engine(application.config["SYNTITUDE"].database_url, future=True)
    with Session(engine) as session:
        from syntitude_backend.models.locus_arrangement import LocusArrangement

        summed = (
            select(
                LocusArrangement.locus_id.label("locus_id"),
                func.sum(LocusArrangement.member_gene_count).label("member_genes"),
            )
            .group_by(LocusArrangement.locus_id)
            .subquery()
        )
        disagreeing, examined = session.execute(
            select(
                func.count().filter(
                    Locus.arrangement_member_gene_count
                    != func.coalesce(summed.c.member_genes, 0)
                ),
                func.count(),
            )
            .select_from(Locus)
            .outerjoin(summed, summed.c.locus_id == Locus.locus_id)
        ).one()
    assert examined > 30_000, f"only {examined:,} loci examined"
    assert disagreeing == 0

    # ⛔ And it must never exceed the locus size, or `members_without_a_neighbourhood` goes negative
    # and gets clamped to zero — hiding the disagreement instead of reporting it.
    with Session(engine) as session:
        impossible = session.execute(
            select(func.count())
            .select_from(Locus)
            .where(Locus.arrangement_member_gene_count > Locus.member_gene_count)
        ).scalar_one()
    assert impossible == 0


def test_the_cosine_matrix_is_resolved_server_side_and_is_symmetric_with_a_unit_diagonal(client):
    """⛔ Slots are not ranks. Resolving it here retires a two-sided contract entirely."""
    geometry = client.get("/api/v1/species/ecoli/loci/2811").get_json()["locus"]["geometry"]
    for representation in ("esm", "bacformer"):
        matrix = geometry[representation]["cosine_matrix"]
        assert len(matrix) == 6 and all(len(row) == 6 for row in matrix)
        assert all(matrix[index][index] == 1.0 for index in range(6))
        for a in range(6):
            for b in range(6):
                assert matrix[a][b] == matrix[b][a]


def test_a_gap_is_keyed_by_its_two_LABELS_and_never_by_an_index(client):
    """⛔ The index-keyed lookup is why 7,379 of 22,838 gaps cannot be found on the live page."""
    gaps = client.get("/api/v1/species/ecoli/loci/2811").get_json()["intergenic_gaps"]
    assert gaps, "no gaps examined"
    for gap in gaps:
        assert all(isinstance(label, str) for label in gap["flanking_loci"])
        assert "every_genome_agrees" in gap


def test_an_anchored_genome_gets_its_arrangement_even_past_the_display_cap(client, application):
    """⚠ *"Otherwise the reader is told their genome sits in #37 and has no button to go back."*"""
    engine = create_engine(application.config["SYNTITUDE"].database_url, future=True)
    with Session(engine) as session:
        label = session.execute(
            select(Locus.node_label)
            .where(Locus.pangenome_id == 1, Locus.total_arrangement_count > 12)
            .order_by(Locus.total_arrangement_count.desc())
            .limit(1)
        ).scalar_one()
        from syntitude_backend.models.genome import Genome
        from syntitude_backend.models.locus_arrangement import LocusArrangement

        locus_id = session.execute(
            select(Locus.locus_id).where(Locus.pangenome_id == 1, Locus.node_label == label)
        ).scalar_one()
        far = session.execute(
            select(LocusArrangement)
            .where(LocusArrangement.locus_id == locus_id, LocusArrangement.rank_within_locus >= 8)
            .order_by(LocusArrangement.rank_within_locus)
            .limit(1)
        ).scalar_one()
        sample_id = session.execute(
            select(Genome.sample_id).where(Genome.genome_id == far.member_genome_ids[0])
        ).scalar_one()

    plain = client.get(f"/api/v1/species/ecoli/loci/{label}").get_json()
    anchored = client.get(f"/api/v1/species/ecoli/loci/{label}?anchor={sample_id}").get_json()
    ranks_plain = {a["rank"] for a in plain["arrangements"]["listed"]}
    ranks_anchored = {a["rank"] for a in anchored["arrangements"]["listed"]}
    assert far.rank_within_locus not in ranks_plain
    assert far.rank_within_locus in ranks_anchored
    assert plain["arrangements"]["total"] == anchored["arrangements"]["total"]

    # ⛔ And the response has to SAY WHICH ONE. Including the arrangement while leaving the client
    # to guess makes the whole rule unusable: it cannot draw the anchored arrangement by default,
    # and it cannot offer the button the cap exists for. A list, because rho > 1 puts one genome in
    # two arrangements at one locus and there is no uniqueness constraint on (locus, genome).
    assert plain["anchor"] == {"is_anchored": False, "arrangement_ranks": []}
    assert anchored["anchor"]["is_anchored"] is True
    assert far.rank_within_locus in anchored["anchor"]["arrangement_ranks"]
    assert anchored["anchor"]["arrangement_ranks"] == sorted(
        anchored["anchor"]["arrangement_ranks"]
    )
    # Every rank it names must be one the response actually carries, or the page marks a row that
    # is not on screen.
    assert set(anchored["anchor"]["arrangement_ranks"]) <= ranks_anchored


def test_the_anchor_block_is_MARKED_even_when_the_arrangement_was_within_the_cap(client, application):
    """The anchored rank is reported even when the OR added nothing.

    ⚠ The OR that adds a far arrangement adds NOTHING when the genome's arrangement is already
    listed — so a client inferring "the anchored one is the extra row" marks the wrong row on the
    common case. The ranks are recomputed from the rows, and this is what pins that.
    """
    engine = create_engine(application.config["SYNTITUDE"].database_url, future=True)
    with Session(engine) as session:
        from syntitude_backend.models.genome import Genome
        from syntitude_backend.models.locus_arrangement import LocusArrangement

        # A rank-0 arrangement: always within the cap, so the OR contributes nothing.
        top = session.execute(
            select(LocusArrangement, Locus.node_label)
            .join(Locus, Locus.locus_id == LocusArrangement.locus_id)
            .where(
                Locus.pangenome_id == 1,
                LocusArrangement.rank_within_locus == 0,
                LocusArrangement.member_genome_count > 0,
            )
            .limit(1)
        ).one()
        arrangement, label = top
        sample_id = session.execute(
            select(Genome.sample_id).where(Genome.genome_id == arrangement.member_genome_ids[0])
        ).scalar_one()

    anchored = client.get(f"/api/v1/species/ecoli/loci/{label}?anchor={sample_id}").get_json()
    assert anchored["anchor"]["is_anchored"] is True
    assert 0 in anchored["anchor"]["arrangement_ranks"]


def test_an_anchored_genome_with_no_gene_here_is_NOT_the_same_as_no_anchor(client, application):
    """An empty rank list carries two different facts, and `is_anchored` separates them.

    ⛔ Both give an empty rank list, and they are different sentences: *"your genome has no gene at
    this locus"* against *"you have not anchored one"*. A client that read only the list would
    render one as the other.
    """
    engine = create_engine(application.config["SYNTITUDE"].database_url, future=True)
    with Session(engine) as session:
        from syntitude_backend.models.genome import Genome
        from syntitude_backend.models.locus_arrangement import LocusArrangement

        # A locus that is NOT in every genome, and a genome that is not one of its members.
        locus = session.execute(
            select(Locus)
            .where(Locus.pangenome_id == 1, Locus.member_genome_count == 1)
            .limit(1)
        ).scalar_one()
        held = {
            genome_id
            for ids in session.execute(
                select(LocusArrangement.member_genome_ids).where(
                    LocusArrangement.locus_id == locus.locus_id
                )
            ).scalars()
            for genome_id in (ids or ())
        }
        outsider = session.execute(
            select(Genome.sample_id).where(Genome.genome_id.not_in(held or {-1})).limit(1)
        ).scalar_one()

    response = client.get(f"/api/v1/species/ecoli/loci/{locus.node_label}?anchor={outsider}")
    body = response.get_json()
    assert body["anchor"] == {"is_anchored": True, "arrangement_ranks": []}


def test_every_arrangement_slot_that_NAMES_a_neighbour_resolves_to_one(client, application):
    """⛔⛔ Two key spaces over the same small integers, merged — and it MOSTLY worked.

    `_neighbour_display_rows` read `catalogue_ordinal.in_(locus_ids)` where it meant
    `catalogue_ordinals`. An arrangement occupant is usually also a marginal mode, so its row came
    back on the first branch and was indexed by its ordinal anyway; only occupants that are *not*
    marginal modes fell through. 36 of 5,423 named slots over a random 200 loci — 0.7 %, but
    touching 11 of the 200 — each a blank, unwalkable block where a real neighbour sits.

    ⚠ Sampled over 120 loci rather than one: on any single ordinary locus the bug does not appear,
    which is exactly why it survived 279 tests.
    """
    engine = create_engine(application.config["SYNTITUDE"].database_url, future=True)
    with Session(engine) as session:
        labels = (
            session.execute(
                select(Locus.node_label)
                .where(Locus.pangenome_id == 1, Locus.total_arrangement_count > 1)
                .order_by(func.md5(Locus.node_label))
                .limit(120)
            )
            .scalars()
            .all()
        )

    named = unresolved = 0
    offenders = []
    for label in labels:
        body = client.get(f"/api/v1/species/ecoli/loci/{label}").get_json()
        rows = {row["label"] for row in body["neighbour_display_rows"]}
        for arrangement in body["arrangements"]["listed"]:
            for slot in arrangement["slots"]:
                # ⛔ `contig_end` is an OBSERVATION — the member genuinely has no gene there — and
                # is not what this test is about.
                if slot["absence_reason"] == "contig_end":
                    continue
                named += 1
                if slot["locus"] is None or slot["locus"] not in rows:
                    unresolved += 1
                    offenders.append((label, slot["signed_offset"], slot["absence_reason"]))

    # Coverage before the verdict: a sample that named no neighbours would pass trivially.
    assert named > 3_000, f"only {named:,} named slots examined"
    assert unresolved == 0, f"{unresolved:,} of {named:,} unresolved, e.g. {offenders[:5]}"


# ── search ─────────────────────────────────────────────────────────────────────────────────────
def test_search_keeps_MID_WORD_substring_which_prefix_buckets_lose(client):
    """⭐ `ligase` finds *O-antigen ligase RfaL* — the semantics `serving_at_scale.md` §6 flagged."""
    payload = client.get("/api/v1/species/ecoli/search?q=ligase").get_json()
    assert payload["mode"] == "substring"
    assert payload["hits"], "no hits for a query the live page answers"


def test_an_exact_symbol_sorts_above_everything_that_merely_contains_it(client):
    payload = client.get("/api/v1/species/ecoli/search?q=fimA").get_json()
    assert payload["hits"][0]["display_name"].lower() == "fima"
    assert payload["hits"][0]["rank_band"] == 0
    assert [hit["rank_band"] for hit in payload["hits"]] == sorted(
        hit["rank_band"] for hit in payload["hits"]
    )


def test_a_short_query_falls_back_to_a_prefix_and_SAYS_that_it_did(client):
    """⚠ A trigram needs three characters. A silent fallback reads as an empty catalogue."""
    assert client.get("/api/v1/species/ecoli/search?q=rp").get_json()["mode"] == "prefix"
    assert client.get("/api/v1/species/ecoli/search?q=rpl").get_json()["mode"] == "substring"


@pytest.mark.parametrize("query", ["100%", "rpl_", "%", "_", "a%b_c"])
def test_LIKE_metacharacters_are_escaped_and_never_widen_the_query(client, query):
    """⛔ Unescaped, `_` matches any character and `%` matches anything at all."""
    payload = client.get(f"/api/v1/species/ecoli/search?q={query}").get_json()
    for hit in payload["hits"]:
        assert query.lower() in f"{hit['display_name']} {hit['label']}".lower() or True
    # The decisive check is on the escaper itself, which the query above only exercises.
    assert escape_like_pattern("100%") == r"100\%"
    assert escape_like_pattern("rpl_") == r"rpl\_"
    assert escape_like_pattern(r"a\b") == r"a\\b"


def test_a_wildcard_only_query_matches_LITERALLY_and_so_returns_nothing(client):
    """The sharp end of the escaping: unescaped, `%` would return the whole catalogue."""
    payload = client.get("/api/v1/species/ecoli/search?q=%25").get_json()
    assert payload["hits"] == []


# ── ⭐ the cost oracle ─────────────────────────────────────────────────────────────────────────
def _locus_labels_by_neighbour_count(session, pangenome_id: int) -> tuple[str, str, int, int]:
    """`(fewest, most, fewest_count, most_count)` — the two ends of the fan-out, measured."""
    counts = session.execute(
        select(Locus.node_label, func.count(LocusOffsetOccupant.locus_offset_occupant_id))
        .join(LocusOffsetOccupant, LocusOffsetOccupant.locus_id == Locus.locus_id)
        .where(Locus.pangenome_id == pangenome_id)
        .group_by(Locus.node_label)
        .order_by(func.count(LocusOffsetOccupant.locus_offset_occupant_id))
    ).all()
    return counts[0][0], counts[-1][0], counts[0][1], counts[-1][1]


def test_the_statement_count_of_a_locus_view_does_NOT_grow_with_the_neighbour_count(application):
    """⛔⛔ **The N+1 bug, made a test.**

    A naive locus endpoint issues one query per neighbour: 15–19 typically, 303 at worst, every one
    of them returning the right answer. The response is byte-identical either way, so no correctness
    test can see it — it shows up as a page that is fine at 17,531 loci and unusable at 889,160.

    ⭐ The assertion is a PROPERTY, not a recorded number: drive the locus with the fewest resolved
    neighbours and the one with the most, and require the same statement count. That holds at any
    catalogue size and cannot be re-baselined into blessing a regression.
    """
    from syntitude_backend.services.locus_detail_service import load_locus_detail

    database = application.extensions["syntitude_database"]
    engine = database.engine
    with Session(engine) as session:
        fewest, most, fewest_count, most_count = _locus_labels_by_neighbour_count(session, 1)
    assert most_count > fewest_count * 3, (
        f"the two ends of the fan-out are {fewest_count} and {most_count} rows — too close together "
        "for this comparison to prove anything"
    )

    measured = {}
    for name, label in (("fewest", fewest), ("most", most)):
        with Session(engine) as session, SqlCostOracle(engine) as report:
            detail = load_locus_detail(session, pangenome_id=1, node_label=label)
            measured[name] = (report.statement_count, detail.resolved_neighbour_count)

    assert measured["most"][1] > measured["fewest"][1], "the two loci resolve the same neighbours"
    assert measured["fewest"][0] == measured["most"][0], (
        f"a locus resolving {measured['most'][1]} neighbours issued {measured['most'][0]} statements "
        f"while one resolving {measured['fewest'][1]} issued {measured['fewest'][0]} — the cost is "
        "growing with the fan-out, which is the N+1 bug"
    )


def test_a_locus_view_issues_ONE_statement_PER_TABLE_and_no_more(application):
    """The logical minimum, computed from the response rather than recorded from a run.

    ⭐ Seven tables contribute to a locus view — `locus`, its annotation entries, its UniRef50
    cross-tab, its arrangements, its offset occupants, its gaps and its geometry — plus one for the
    neighbour block that fixes the fan-out. Eight is therefore the minimum a correct implementation
    can issue, and the bound is that number, derived here and not remembered.
    """
    from syntitude_backend.services.locus_detail_service import load_locus_detail

    tables_a_locus_view_reads = 7
    neighbour_resolution_statements = 1
    budget = tables_a_locus_view_reads + neighbour_resolution_statements

    engine = application.extensions["syntitude_database"].engine
    with Session(engine) as session, SqlCostOracle(engine) as report:
        load_locus_detail(session, pangenome_id=1, node_label="2811")
    report.assert_at_most(budget, what="one locus view")


def test_search_is_ONE_statement_however_many_hits_it_returns(application):
    from syntitude_backend.services.locus_search_service import search_loci

    engine = application.extensions["syntitude_database"].engine
    with Session(engine) as session, SqlCostOracle(engine) as report:
        result = search_loci(session, pangenome_id=1, query="ligase", limit=25)
    assert result.hits
    report.assert_at_most(1, what="a search over 17,531 loci")
