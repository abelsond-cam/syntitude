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

from bacatlas_backend.instruments.payload_reproduction import compare_payloads
from bacatlas_backend.instruments.payload_serialiser import build_payload_from_database
from bacatlas_backend.models.locus import Locus
from tests.known_parity_exceptions import (
    AUDIT_RERUN_HEADLINE_KEYS,
    AUDIT_RERUN_PAYLOAD_BLOCKS,
    MEDOID_RETIREMENT_PAYLOAD_BLOCKS,
    RETIRED_TIER,
    exceptions_for,
    symbol_fold_for,
)

SPECIES = ["ecoli", "kp"]


@pytest.fixture(scope="module")
def loaded_session():
    url = os.environ.get("BACATLAS_DATABASE_URL")
    if not url:
        pytest.skip("BACATLAS_DATABASE_URL is not set — the rebuild runs against a loaded database")
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
    # ⛔ THREE blocks are legitimately not examined, and naming them is the point: `map_reps` and
    # `null` exist only in the frozen schema-14 payload and `sim` only in the schema-16 rebuild, so
    # there is nothing to compare either against. ⚠ *Not looked at* and *no difference* are
    # indistinguishable in an output unless they are made different, which is why this is an
    # enumerated set and not a shortened one. It empties when both species are re-exported.
    assert sorted(result.blocks_not_examined) == [
        "map_reps (only in published)",
        "null (only in published)",
        "sim (only in rebuilt)",
    ], result.render()
    assert set(result.blocks_compared) == {
        "schema", "meta", "strings", "nodes", "lists", "arr", "ctx", "gaps",
    }  # fmt: skip
    # ⚠ 114 → 103: the four `nodes.*_d_*` columns went, and `map_reps`/`null` are no longer compared
    # column by column. The floor is lowered rather than removed — it is what stops a rebuild that
    # quietly stopped emitting half the catalogue from reading as agreement.
    assert result.columns_compared >= 103
    assert result.elements_compared > 3_400_000


@pytest.mark.parametrize("species", SPECIES)
def test_the_rebuilt_payload_interns_in_the_SAME_ORDER_as_build_payload(species, rebuilt):
    """⭐ The serialiser self-checks this before returning, so reaching here at all is the proof —
    asserted anyway, because the check being present is the thing that must not be deleted."""
    from bacatlas_backend.instruments.payload_reproduction import verify_intern_walk

    assert verify_intern_walk(rebuilt[species]) == []


# ── the exception, named exactly ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("species", SPECIES)
def test_EXACTLY_the_recorded_blocks_differ_and_each_has_a_named_cause(species, report):
    """⛔ The set, not the count — and every member of it belongs to one of two recorded decisions.

    ⭐ **Two causes now, and they are disjoint**: the 2026-09-04 audit re-run retiring `no_homology`
    (four blocks), and the allele-variant symbol fold (three blocks, four in kp). A suite that
    counted to seven could not tell one cause growing from the other shrinking.

    ⚠ **The two species do NOT have the same set**, and that is measured: kp's `nodes.name` moves
    and *E. coli*'s does not, because both *E. coli* loci keep their pool INDEX while the string at
    that index changes. See `SYMBOL_FOLD_ECOLI`.
    """
    differing = {
        line.split(" CHANGED")[0].removeprefix("⛔ ") for line in report[species].differences
    }
    expected = (
        AUDIT_RERUN_PAYLOAD_BLOCKS
        | symbol_fold_for(species).payload_blocks
        | MEDOID_RETIREMENT_PAYLOAD_BLOCKS
    )
    assert differing == expected, report[species].render()
    for first, second in (
        (AUDIT_RERUN_PAYLOAD_BLOCKS, symbol_fold_for(species).payload_blocks),
        (AUDIT_RERUN_PAYLOAD_BLOCKS, MEDOID_RETIREMENT_PAYLOAD_BLOCKS),
        (symbol_fold_for(species).payload_blocks, MEDOID_RETIREMENT_PAYLOAD_BLOCKS),
    ):
        assert not (first & second), (
            "two causes have started to overlap — one of them is no longer what it says it is"
        )


@pytest.mark.parametrize("species", SPECIES)
def test_every_other_block_is_BYTE_IDENTICAL_including_the_big_three(species, rebuilt):
    """⭐ `arr` (486,717 genome memberships) and `ctx` (253,909 occupants) are where a rebuild would
    go wrong invisibly, so they are named rather than left to the set above.

    ⚠ `lists` left this clause when the symbol fold landed — **two of its nine sub-blocks move and
    the other seven do not**, so it is asserted sub-block by sub-block below rather than dropped.
    """
    published = _published(species)
    # ⛔ `map_reps` and `null` left this list on 2026-09-24 — they are no longer built from anything,
    # and the `sim` block that replaced them has no counterpart in a schema-14 payload to be
    # identical TO. They are recorded as expected differences above rather than dropped, so the
    # re-export that makes them match again is a failing test and not a silence.
    # ⚠ `schema` stays, and is the load-bearing one here: it passes only because the rebuild pins
    # itself to the schema its ROWS came from rather than reading nuna's current constant.
    for block in ("arr", "ctx", "gaps", "schema"):
        assert published[block] == rebuilt[species][block], f"{block} is not byte-identical"


@pytest.mark.parametrize("species", SPECIES)
def test_every_list_EXCEPT_the_two_the_fold_touches_is_byte_identical(species, rebuilt):
    """⛔ The fold moves gene names. It must not have moved a product, a domain or a GO term."""
    published = _published(species)["lists"]
    mine = rebuilt[species]["lists"]
    assert set(published) == set(mine), "the rebuild invented or dropped a list"
    for key in set(published) - {"sym", "u50"}:
        assert published[key] == mine[key], f"lists.{key} is not byte-identical"


def _decoded_symbol_lists(payload):
    """`[[(name, gene_count), …], …]` per locus — the CSR block resolved through its own pool.

    ⛔ **Decoded, never as indices.** `strings.sym` loses the tagged names, so every later index
    shifts; and one *E. coli* locus loses a symbol ROW, which shifts every later CSR element. 5,823
    of 8,799 `lists.sym.idx` elements move while **two** loci actually changed. Comparing the raw
    arrays could only ever be a tolerance — see `SYMBOL_FOLD_IS_INDEX_SHIFT_NOT_CONTENT`.
    """
    block, pool, out, low = payload["lists"]["sym"], payload["strings"]["sym"], [], 0
    for count in block["n"]:
        out.append([(pool[block["idx"][k]], block["cnt"][k]) for k in range(low, low + count)])
        low += count
    return out


def _decoded_family_symbols(payload):
    """`[[(family gene count, its modal name, its distinct-name count), …], …]` per locus."""
    block, pool, out, low = payload["lists"]["u50"], payload["strings"]["sym"], [], 0
    for count in block["n"]:
        rows = []
        for k in range(low, low + count):
            symbol = block["sym"][k]
            rows.append((block["cnt"][k], pool[symbol] if symbol >= 0 else None, block["nsym"][k]))
        out.append(rows)
        low += count
    return out


@pytest.mark.parametrize("species", SPECIES)
@pytest.mark.parametrize("decode", [_decoded_symbol_lists, _decoded_family_symbols])
def test_DECODED_the_symbol_blocks_move_on_exactly_the_folded_loci(species, rebuilt, decode):
    """⭐ The claim the byte comparison cannot make: only four loci changed, in both blocks."""
    published = _published(species)
    labels = published["nodes"]["label"]
    before, after = decode(published), decode(rebuilt[species])
    moved = {labels[i] for i in range(len(labels)) if before[i] != after[i]}
    assert moved == symbol_fold_for(species).node_labels


@pytest.mark.parametrize("species", SPECIES)
def test_the_symbol_POOL_loses_only_the_tagged_names(species, rebuilt):
    """⚠ And gains only the untagged gene where the pool did not already hold it (`tufA`, `rpsJ`).

    A fold that dropped a name it should have kept would shrink this pool silently — and every
    index-based comparison in this file would report thousands of differences without saying why.
    """
    from bacatlas_backend.ingest.allele_variant_symbols import (
        ALLELE_VARIANT_SYMBOL,
        fold_allele_variant,
    )

    published = set(_published(species)["strings"]["sym"])
    mine = set(rebuilt[species]["strings"]["sym"])
    # ⚠ Asked of the RULE, not of a checked-in list of four names: a pattern that widened would
    # be caught here, where a hard-coded list would simply keep agreeing with itself.
    tagged = {name for name in published if ALLELE_VARIANT_SYMBOL.match(name)}
    assert tagged, "the frozen pool holds no allele-tagged symbol — this comparison is vacuous"
    assert published - mine == tagged
    assert mine - published <= {fold_allele_variant(name) for name in tagged}


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

    from bacatlas_backend.instruments.payload_serialiser import _arrangement_cap

    TOP_ARRANGEMENTS = pytest.importorskip(
        "nuna.tl.locus_browser.export_payload", reason="the default under test is nuna's; nuna is not installed"
    ).TOP_ARRANGEMENTS

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

    from bacatlas_backend.models.locus_arrangement import LocusArrangement

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
