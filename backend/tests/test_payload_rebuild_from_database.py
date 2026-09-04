"""⭐⭐ **Can the database reproduce the catalogue the static site ships?**

This is S1's exit criterion, and it is answered against the real published exports — 17,531 *E.
coli* loci and 15,670 kp — not a fixture. The rebuild is graded with nuna's own
`verify_payload_invariance.diff_payloads`, the oracle David asked for when the export was written.

**The answer: yes, with one named exception.** 114 columns and 3.84 M elements reproduce
byte-for-byte on both species. Four blocks do not, and all four are the 2026-09-04 audit re-run
retiring `no_homology` — recorded in `known_parity_exceptions`, asserted here as an exact set.

⛔ **Never a tolerance.** Each clause below says which loci, which keys, which string. A suite that
allowed "four differences" could not tell this from four hundred.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from syntitude_backend.instruments.payload_reproduction import compare_payloads
from syntitude_backend.instruments.payload_serialiser import build_payload_from_database
from syntitude_backend.models.locus import Locus
from tests.known_parity_exceptions import (
    AUDIT_RERUN_HEADLINE_KEYS,
    AUDIT_RERUN_PAYLOAD_BLOCKS,
    RETIRED_TIER,
    exceptions_for,
)

SPECIES = ["ecoli", "kp"]


@pytest.fixture(scope="module")
def loaded_session():
    url = os.environ.get("SYNTITUDE_DATABASE_URL")
    if not url:
        pytest.skip("SYNTITUDE_DATABASE_URL is not set — the rebuild runs against a loaded database")
    engine = create_engine(url, future=True)
    with Session(engine) as session:
        if session.execute(select(func.count()).select_from(Locus)).scalar_one() < 30_000:
            pytest.skip("both published catalogues must be loaded")
        yield session


@pytest.fixture(scope="module")
def rebuilt(loaded_session, request):
    return {species: build_payload_from_database(loaded_session, species) for species in SPECIES}


def _published(species):
    import json

    from tests.conftest import artifacts_for

    return json.loads(artifacts_for(species).published_payload.read_text())


@pytest.fixture(scope="module")
def report(rebuilt):
    return {species: compare_payloads(_published(species), rebuilt[species]) for species in SPECIES}


# ── coverage first, always ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("species", SPECIES)
def test_the_rebuild_examines_EVERY_block_and_states_what_it_compared(species, report):
    """⛔ "Four differences" over four blocks and over forty read the same. Coverage is the claim."""
    result = report[species]
    assert result.blocks_not_examined == [], result.render()
    assert set(result.blocks_compared) == {
        "schema", "meta", "strings", "nodes", "lists", "arr", "map_reps", "ctx", "gaps", "null",
    }  # fmt: skip
    assert result.columns_compared >= 114
    assert result.elements_compared > 3_400_000


@pytest.mark.parametrize("species", SPECIES)
def test_the_rebuilt_payload_interns_in_the_SAME_ORDER_as_build_payload(species, rebuilt):
    """⭐ The serialiser self-checks this before returning, so reaching here at all is the proof —
    asserted anyway, because the check being present is the thing that must not be deleted."""
    from syntitude_backend.instruments.payload_reproduction import verify_intern_walk

    assert verify_intern_walk(rebuilt[species]) == []


# ── the exception, named exactly ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("species", SPECIES)
def test_EXACTLY_four_blocks_differ_and_all_four_are_the_audit_re_run(species, report):
    """⛔ The set, not the count."""
    differing = {
        line.split(" CHANGED")[0].removeprefix("⛔ ") for line in report[species].differences
    }
    assert differing == AUDIT_RERUN_PAYLOAD_BLOCKS, report[species].render()


@pytest.mark.parametrize("species", SPECIES)
def test_every_other_block_is_BYTE_IDENTICAL_including_the_big_three(species, rebuilt):
    """⭐ `arr` (486,717 genome memberships), `ctx` (253,909 occupants) and `lists` are where a
    rebuild would go wrong invisibly, so they are named rather than left to the set above."""
    published = _published(species)
    for block in ("arr", "ctx", "lists", "gaps", "map_reps", "null", "schema"):
        assert published[block] == rebuilt[species][block], f"{block} is not byte-identical"


@pytest.mark.parametrize("species", SPECIES)
def test_nodes_tier_differs_on_exactly_the_loci_the_registry_names(species, rebuilt):
    published = _published(species)
    exception = exceptions_for(species, "collapse_tier")
    moved = {
        published["nodes"]["label"][index]
        for index, (before, after) in enumerate(
            zip(published["nodes"]["tier"], rebuilt[species]["nodes"]["tier"], strict=True)
        )
        if before != after
    }
    assert moved == exception.node_labels
    for label in moved:
        index = published["nodes"]["label"].index(label)
        assert published["strings"]["tier"][published["nodes"]["tier"][index]] == exception.frozen_value
        after = rebuilt[species]["nodes"]["tier"][index]
        assert rebuilt[species]["strings"]["tier"][after] == exception.current_value


@pytest.mark.parametrize("species", SPECIES)
def test_strings_tier_differs_ONLY_by_the_retired_name_and_no_index_shifts(species, rebuilt):
    """⚠ `no_homology` was interned LAST, so dropping it shifts no other index. That is luck rather
    than design — which is exactly why it is asserted instead of assumed."""
    published = _published(species)["strings"]["tier"]
    mine = rebuilt[species]["strings"]["tier"]
    assert set(published) - set(mine) == {RETIRED_TIER}
    assert mine == [name for name in published if name != RETIRED_TIER]


@pytest.mark.parametrize("species", SPECIES)
def test_meta_audit_differs_on_SIX_headline_keys_and_the_graded_lists_do_NOT_move(species, rebuilt):
    """⛔⛔ `failures` must not move: `synteny_only` and `no_homology` are BOTH failure tiers, so
    the graded set is identical and only its composition changed. A rebuild that shrank the failure
    list would be quietly reporting a better model than the one that was published."""
    published, mine = _published(species)["meta"]["audit"], rebuilt[species]["meta"]["audit"]
    assert published["label"] == mine["label"]
    assert published["sources"] == mine["sources"]
    assert published["failures"] == mine["failures"]
    assert published["contested"] == mine["contested"]
    moved = {key for key in published["headline"] if published["headline"][key] != mine["headline"][key]}
    assert moved == AUDIT_RERUN_HEADLINE_KEYS


@pytest.mark.parametrize("species", SPECIES)
def test_meta_omitted_gains_the_seqid_omission_and_nothing_else(species, rebuilt):
    """⚠ The database can say *the audit did not measure this*; the older payload had no way to."""
    published, mine = _published(species)["meta"]["omitted"], rebuilt[species]["meta"]["omitted"]
    assert published == {}
    assert set(mine) == {"seqid_to_medoid"}


@pytest.mark.parametrize("species", SPECIES)
def test_the_rest_of_meta_is_identical_including_the_genome_VOCABULARY(species, rebuilt):
    """⛔ `meta.genomes` is what `arr.gid` indexes into — one element out of place renames every
    genome on every arrangement, and every name it then shows is a real genome."""
    published, mine = _published(species)["meta"], rebuilt[species]["meta"]
    for key in sorted(set(published) - {"built", "git_sha", "audit", "omitted"}):
        assert published[key] == mine[key], f"meta.{key}"
    assert mine["genomes"] == published["genomes"]
    assert len(mine["genomes"]) == mine["n_genomes"]


# ── the cap, which is read from the data and not from nuna's default ───────────────────────────
def test_the_arrangement_cap_is_recovered_from_the_DATA_not_from_nunas_default():
    """⛔⛔ `TOP_ARRANGEMENTS` is nuna's default (4) and **both published exports overrode it to run
    uncapped**, shipping `0`. Taking the constant emits 4 for a catalogue that shipped 0 — and 0 vs
    4 is the difference between *"a rarer neighbourhood exists but was not shipped"* and *"there are
    no others"*, which is the only reason the field is in the payload at all.
    """
    from types import SimpleNamespace

    from nuna.tl.locus_browser.export_payload import TOP_ARRANGEMENTS

    from syntitude_backend.instruments.payload_serialiser import _arrangement_cap

    assert TOP_ARRANGEMENTS == 4, "the point of this test is that the default is NOT what shipped"

    uncapped = [SimpleNamespace(total_arrangement_count=n) for n in (1, 7, 3)]
    assert _arrangement_cap(uncapped, [1, 7, 3]) == 0

    capped = [SimpleNamespace(total_arrangement_count=n) for n in (2, 37, 4)]
    assert _arrangement_cap(capped, [2, 4, 4]) == 4

    # ⚠ A locus that listed NOTHING reveals no cap. 847 real loci are in this state — their genes
    # never reached a window — and counting them as "cut to zero" makes an uncapped catalogue
    # report a cap of 0, which is the encoding for uncapped. The two ends of the scale collide.
    none_listed = [SimpleNamespace(total_arrangement_count=n) for n in (0, 5, 3)]
    assert _arrangement_cap(none_listed, [0, 5, 3]) == 0


def test_the_published_catalogues_really_are_uncapped_on_every_locus(loaded_session):
    """The claim `_arrangement_cap` returns 0 on, checked directly against all 33,201 loci."""
    from sqlalchemy import func

    from syntitude_backend.models.locus_arrangement import LocusArrangement

    listed = (
        select(LocusArrangement.locus_id, func.count().label("n"))
        .group_by(LocusArrangement.locus_id)
        .subquery()
    )
    mismatched = loaded_session.execute(
        select(func.count())
        .select_from(Locus)
        .outerjoin(listed, listed.c.locus_id == Locus.locus_id)
        # ⚠ COALESCE, not `<>`: 847 loci have no row, and `NULL <> n` is NULL, not TRUE — a
        # NULL-unsafe comparison reports "0 mismatches" over rows it never actually examined.
        .where(Locus.total_arrangement_count != func.coalesce(listed.c.n, 0))
    ).scalar_one()
    assert mismatched == 0
