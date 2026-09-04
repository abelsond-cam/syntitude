"""The reproduction harness, and the two traps it exists to keep apart.

⭐ Every test here runs against the **real published exports** — 17,531 ecoli loci and 15,670 kp —
because the properties being pinned are properties of how `build_payload` actually walked real data,
and a fixture cannot carry them. A pool's interning order is not derivable from its contents.
"""

from __future__ import annotations

import copy
import random

import pytest

from syntitude_backend.instruments.payload_reproduction import (
    GAP_INTERN_WALK,
    INTERN_WALK,
    UNMAPPABLE,
    compare_payloads,
    remap_pools_onto,
    verify_intern_walk,
)


# ── the walk order, proved against real data ───────────────────────────────────────────────────
@pytest.mark.parametrize("species", ["ecoli", "kp"])
def test_INTERN_WALK_describes_how_the_published_payload_was_actually_interned(
    species, exported_ecoli_payload, exported_kp_payload
):
    """⛔⛔ **The constant the whole serialiser rests on, checked against the file it describes.**

    `_Intern` assigns an index on FIRST USE, so the pools are in `build_payload`'s walk order — not
    sorted, and not recoverable from the string set. Replaying the walk must land first use on
    0, 1, 2, … with no gaps, and must reach every pooled string.

    Two species, because a walk order fitted to one catalogue would pass on one catalogue.
    """
    payload = exported_ecoli_payload if species == "ecoli" else exported_kp_payload
    assert verify_intern_walk(payload) == []


def test_the_walk_covers_every_pool_the_payload_carries_and_NAMES_any_it_does_not(
    exported_ecoli_payload,
):
    """⛔ A walk that silently skipped a pool would report a clean bill over the ones it did check."""
    pooled = set(exported_ecoli_payload["strings"]) | {"labels", "types"}
    assert pooled == set(INTERN_WALK) | set(GAP_INTERN_WALK), (
        "a pool exists in the payload with no entry in INTERN_WALK — its indices would never be "
        "remapped, and the serialiser would have no emission order for it"
    )


def test_strings_cog_holds_TWO_vocabularies_and_reading_it_as_COG_ids_is_wrong(
    exported_ecoli_payload,
):
    """⚠ `nodes.cog_cat` interns Bakta CATEGORY strings into the same pool `lists.cog.idx` then
    fills with COG **ids**. The pool therefore opens with category runs (`K`, `MV`, `DN`) and a
    reader treating `strings.cog` as a COG-id vocabulary is wrong at its head.
    """
    pool = exported_ecoli_payload["strings"]["cog"]
    categories = [s for s in pool if s.isalpha() and s.isupper() and len(s) <= 4]
    identifiers = [s for s in pool if s.startswith("COG")]
    assert categories and identifiers, "the pool should hold both vocabularies"
    # The categories come FIRST, because node_block is built before the lists loop runs.
    assert all(not s.startswith("COG") for s in pool[:50])


# ── the harness itself ─────────────────────────────────────────────────────────────────────────
def test_a_payload_compared_to_itself_is_identical_AND_states_real_coverage(exported_ecoli_payload):
    """⛔ "No differences" over four blocks and over forty read the same. The coverage is the claim."""
    report = compare_payloads(exported_ecoli_payload, copy.deepcopy(exported_ecoli_payload))
    assert report.is_byte_identical
    assert report.blocks_not_examined == []
    assert report.columns_compared > 100, report.render()
    assert report.elements_compared > 3_000_000, report.render()
    assert "arr" in report.blocks_compared and "gaps" in report.blocks_compared


def test_a_REORDERED_pool_is_not_identical_but_IS_identical_under_a_remap(exported_ecoli_payload):
    """⭐⭐ **The distinction this harness exists to draw.**

    A serialiser that emits the same strings in a different order is *correct and not identical*.
    Permuting one pool and remapping its indices consistently produces exactly that payload — and
    the report must call it what it is rather than reporting a changed catalogue.
    """
    published = exported_ecoli_payload
    rebuilt = copy.deepcopy(published)
    pool = published["strings"]["tier"]
    permutation = list(reversed(range(len(pool))))
    rebuilt["strings"]["tier"] = [pool[i] for i in permutation]
    inverse = {old: new for new, old in enumerate(permutation)}
    rebuilt["nodes"]["tier"] = [v if v < 0 else inverse[v] for v in published["nodes"]["tier"]]

    report = compare_payloads(published, rebuilt)
    assert not report.is_byte_identical, "a reordered pool must not pass as byte-identical"
    assert report.is_identical_under_remap, report.render()
    # And it must say WHICH differences the reordering explains, not merely that some do.
    assert any("strings.tier" in d for d in report.interning_only), report.render()
    assert any("nodes.tier" in d for d in report.interning_only), report.render()


def test_a_remap_CANNOT_absorb_a_changed_number(exported_ecoli_payload):
    """⛔ The diagnosis must not become an excuse. A remap only ever removes differences it can
    explain; a wrong value stays a difference, or the harness would launder real defects."""
    published = exported_ecoli_payload
    rebuilt = copy.deepcopy(published)
    rebuilt["nodes"]["len_nt"][7] = published["nodes"]["len_nt"][7] + 1

    report = compare_payloads(published, rebuilt)
    assert not report.is_byte_identical
    assert not report.is_identical_under_remap, report.render()
    assert any("nodes.len_nt" in d for d in report.differences)
    assert not any("nodes.len_nt" in d for d in report.interning_only), (
        "the remap claimed to explain a changed measurement — it can only explain an index"
    )


def test_a_string_the_reference_does_not_have_stays_UNMAPPABLE(exported_ecoli_payload):
    """⚠ A remap that quietly dropped an unknown string would turn a new value into a match."""
    published = exported_ecoli_payload
    rebuilt = copy.deepcopy(published)
    rebuilt["strings"]["tier"] = list(published["strings"]["tier"]) + ["a_tier_that_never_existed"]
    rebuilt["nodes"]["tier"] = list(published["nodes"]["tier"])
    rebuilt["nodes"]["tier"][3] = len(published["strings"]["tier"])

    remapped = remap_pools_onto(rebuilt, published)
    assert remapped["nodes"]["tier"][3] == UNMAPPABLE
    report = compare_payloads(published, rebuilt)
    assert not report.is_identical_under_remap, report.render()


def test_a_block_present_in_only_one_payload_is_NOT_EXAMINED_not_compared(exported_ecoli_payload):
    """⛔ *Not looked at* and *no difference* must be different outputs — this repo's own rule."""
    rebuilt = copy.deepcopy(exported_ecoli_payload)
    del rebuilt["gaps"]
    report = compare_payloads(exported_ecoli_payload, rebuilt)
    assert any(entry.startswith("gaps") for entry in report.blocks_not_examined), report.render()
    assert "gaps" not in report.blocks_compared
    assert "NOT EXAMINED" in report.render()


# ── the wrong-file trap, made executable ───────────────────────────────────────────────────────
def test_the_SITE_catalogue_is_the_wrong_oracle_and_differs_in_exactly_the_known_ways(
    exported_ecoli_payload, published_ecoli_site_catalogue
):
    """⛔⛔ **The trap that costs a day if it is discovered rather than recorded.**

    Both files are legitimately in use. `data/browser/…json` is the export; `syntitude/data/
    ecoli.json` is that payload after `render_page` mutated it. Diffing a rebuild against the second
    reports differences that are all correct behaviour. Pinned as a test so the difference is a
    fact rather than a comment — and so a future `render` that mutates something *else* is caught.
    """
    export, site = exported_ecoli_payload, published_ecoli_site_catalogue
    added_blocks = set(site) - set(export)
    added_meta = set(site["meta"]) - set(export["meta"])
    assert added_blocks == {"cog_names", "go_names", "pfam_names"}
    assert added_meta == {"landing", "examples"}

    # ⚠ The COST of using the wrong file, measured rather than remembered: three ADDED blocks and
    # two changed meta keys, five reports that are all correct behaviour. `render` computes
    # `landing`/`examples` from the interest ranking at site-build time, so a rebuild that did not
    # also run the ranking would look wrong for a reason that has nothing to do with the database.
    # The direction is the realistic mistake: the SITE file passed as `--before`, a rebuild that
    # has none of render's additions as `--after`.
    naive = compare_payloads(site, export)
    assert len(naive.differences) == 5, naive.render()
    assert sum("REMOVED top-level block" in d for d in naive.differences) == 3, naive.render()
    assert sum(d.startswith("⛔ meta.") for d in naive.differences) == 2, naive.render()

    # Everything OUTSIDE those five is byte-identical — which is why the export is sufficient, and
    # why `render`'s mutation being purely additive is a fact worth pinning rather than assuming.
    trimmed = {k: v for k, v in site.items() if k in export}
    trimmed["meta"] = {k: v for k, v in site["meta"].items() if k not in added_meta}
    report = compare_payloads(export, trimmed)
    assert report.is_byte_identical, report.render()


# ── a property, not a snapshot ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_permuting_ANY_pool_is_always_diagnosed_as_interning_and_never_as_content(
    seed, exported_ecoli_payload
):
    """⭐ The diagnosis holds for every pool, not the one it was written against — so a pool added
    later is covered by construction rather than by someone remembering to extend a list."""
    rng = random.Random(seed)
    published = exported_ecoli_payload
    rebuilt = copy.deepcopy(published)
    for pool, paths in INTERN_WALK.items():
        table = published["strings"][pool]
        permutation = list(range(len(table)))
        rng.shuffle(permutation)
        rebuilt["strings"][pool] = [table[i] for i in permutation]
        inverse = {old: new for new, old in enumerate(permutation)}
        for path in paths:
            node = rebuilt
            for key in path[:-1]:
                node = node[key]
            source = published
            for key in path:
                source = source[key]
            node[path[-1]] = [v if v < 0 else inverse[v] for v in source]

    report = compare_payloads(published, rebuilt)
    assert not report.is_byte_identical
    assert report.is_identical_under_remap, report.render()
