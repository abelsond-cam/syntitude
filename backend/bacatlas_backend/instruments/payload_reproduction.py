"""Compare a payload rebuilt from the database against the one that was published.

⭐ **What this instrument is for.** The database is meant to be a *lossless superset* of the JSON
catalogue the static site ships. That claim is only worth something if it is checked against the real
17,531-locus payload, so this rebuilds the payload from Postgres and diffs it block by block with
:func:`nuna.eval.verify_payload_invariance.diff_payloads` — the oracle David asked for when the
export was written, reused rather than re-implemented.

⛔ **The file to diff against is the EXPORT, not the site catalogue.** ``data/browser/
locus_browser_{set}_{label}.json`` is what :func:`build_payload` emitted. ``syntitude/data/
{species}.json`` is that file *after* ``render_page`` mutated it: three extra blocks
(``cog_names``, ``go_names``, ``pfam_names``) and two extra ``meta`` keys (``landing``,
``examples``) that ``build_payload`` never produced. Both are legitimately in use, for different
things — which is exactly why pointing at the wrong one yields five spurious block differences and
no signal at all.

⭐⭐ **The interning problem, and why a difference here has two very different meanings.**
``_Intern`` assigns a string its index **on first use**, so ``strings.sym`` is in whatever order
``build_payload`` happened to walk the data — not sorted, and not derivable from the string set. A
serialiser that emits the same strings in a different order is **correct and not identical**, and
every ``idx`` column then differs too, so a column-wise diff reports the whole payload changed and
tells the reader nothing.

So this instrument answers two questions rather than one:

* is the rebuilt payload **byte-identical**? — the strong claim, and the exit criterion; and
* if not, is it **identical under a pool remap**? — i.e. the same catalogue, interned in a
  different order, which is a very different defect from a wrong number.

⚠ **Coverage is stated before any difference is reported.** A harness that compared four blocks and
said "no differences" would be indistinguishable from one that compared forty — this project's own
rule, learnt from a diff loop that ``continue``d past missing columns and reported "0 differ" while
skipping exactly the columns that had changed (``4ab35ca``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: ⭐⭐ **THE WALK ORDER — one constant, serving two masters.**
#:
#: Every payload column that holds an index into a ``strings`` pool, listed **in the order
#: ``build_payload`` interns them**. It is read two ways:
#:
#: * the serialiser emits in this order, which is what makes its pools byte-identical; and
#: * this instrument uses it to remap pools when diagnosing a difference.
#:
#: ⛔ The order is not decoration and not alphabetical — it is the evaluation order of
#: ``build_payload``'s ``node_block`` dict literal (top to bottom), then its
#: ``for f, col, pool in (...)`` loop, then the ``top_u50`` second pass that adds to three pools
#: which already have entries. ``test_payload_reproduction`` proves this constant against the
#: published payload by replaying it and asserting first use lands on 0, 1, 2, … — so a reordering
#: here fails against real data rather than passing quietly.
#:
#: ⚠ ``cog`` is one pool holding **two vocabularies**: ``nodes.cog_cat`` writes category strings
#: (``K``, ``MV``, ``DN`` — Bakta writes a *set* as a letter run) and ``lists.cog.idx`` then writes
#: COG *ids* into the same table. Reading ``strings.cog`` as a COG-id vocabulary is wrong at its
#: first 118 entries.
INTERN_WALK: dict[str, tuple[tuple[str, ...], ...]] = {
    "sym": (("nodes", "name"), ("lists", "sym", "idx"), ("lists", "u50", "sym")),
    "prod": (("lists", "prod", "idx"), ("lists", "u50", "prod")),
    "u50": (("lists", "u50", "idx"),),
    "pfam": (("lists", "pfam", "idx"), ("lists", "u50", "arch")),
    "tier": (("nodes", "tier"),),
    "pfclass": (("nodes", "pfclass"),),
    "cog": (("nodes", "cog_cat"), ("lists", "cog", "idx")),
    "go": (("lists", "go", "idx"),),
    "ec": (("lists", "ec", "idx"),),
    "kegg": (("lists", "kegg", "idx"),),
    "goclass": (("nodes", "go_0"), ("nodes", "go_1"), ("nodes", "go_2")),
}

#: The ``gaps`` block carries **its own two pools**, local to the block and not in ``strings`` —
#: they are built by :func:`intergenic_block`'s own ``_Intern`` pair, walked in gap-row order.
GAP_INTERN_WALK: dict[str, tuple[tuple[str, ...], ...]] = {
    "labels": (("gaps", "flab"),),
    "types": (("gaps", "ftyp"),),
}

#: Where each pool's string table lives, so a remap can find it.
POOL_TABLE: dict[str, tuple[str, ...]] = {
    **{pool: ("strings", pool) for pool in INTERN_WALK},
    **{pool: ("gaps", pool) for pool in GAP_INTERN_WALK},
}

#: Differ between any two exports of the same catalogue and say nothing about it. Named rather than
#: tolerated by a fuzzy comparison — the same rule, and the same two names, as the oracle itself.
VOLATILE_META = ("built", "git_sha")


def _at(payload: dict, path: tuple[str, ...]) -> Any:
    """The value at a dotted path, or ``None`` if any step is missing."""
    node: Any = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _set_at(payload: dict, path: tuple[str, ...], value: Any) -> None:
    node: Any = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def verify_intern_walk(payload: dict) -> list[str]:
    """Check that :data:`INTERN_WALK` really describes how this payload was interned.

    ⭐ Replays the walk and asserts that the **first occurrence** of each index is the next unused
    integer — which is precisely what ``_Intern.idx`` guarantees and what a wrong walk order breaks.
    A pool whose walk is right yields 0, 1, 2, … with no gaps and covers the whole table.

    Returns the failures; empty means the constant is an accurate description of this file. This is
    the check that makes the constant self-verifying rather than a comment.
    """
    failures: list[str] = []
    for pool, paths in {**INTERN_WALK, **GAP_INTERN_WALK}.items():
        table = _at(payload, POOL_TABLE[pool])
        if table is None:
            continue  # an optional block (`gaps`, `map_reps`) this payload does not carry
        expected, seen = 0, set()
        for path in paths:
            values = _at(payload, path)
            if values is None:
                failures.append(f"{pool}: {'.'.join(path)} is absent — the walk cannot be replayed")
                continue
            for position, value in enumerate(values):
                # ⚠ -1 is `_Intern.idx(None)` — an absent string, never an index into the table.
                if value < 0 or value in seen:
                    continue
                if value != expected:
                    failures.append(
                        f"{pool}: at {'.'.join(path)}[{position}] first use is index {value}, "
                        f"expected {expected} — INTERN_WALK does not describe this payload"
                    )
                    break
                seen.add(value)
                expected += 1
            else:
                continue
            break
        if expected != len(table):
            failures.append(
                f"{pool}: the walk reaches {expected:,} of {len(table):,} pooled strings — "
                "a column that writes into this pool is missing from INTERN_WALK"
            )
    return failures


#: A rebuilt index whose string is absent from the reference pool. Chosen so it can never compare
#: equal to a real index, and so a reader seeing it in a diff knows it is this and not an off-by-one.
UNMAPPABLE = -999_999


def remap_pools_onto(payload: dict, reference: dict) -> dict:
    """``payload`` rewritten into ``reference``'s index space — a **diagnosis, never a fix**.

    ⛔ This exists to tell two failures apart, not to make one pass. If a payload only matches after
    a remap, it is the same catalogue interned in a different order: real information, and NOT the
    exit criterion. Byte-identity is the claim; this says how far short a failure fell.

    Strings absent from the reference pool map to :data:`UNMAPPABLE`, so a genuine content
    difference stays a difference instead of being quietly absorbed by the remapping.
    """
    import copy

    out = copy.deepcopy(payload)
    for pool, paths in {**INTERN_WALK, **GAP_INTERN_WALK}.items():
        mine, theirs = _at(payload, POOL_TABLE[pool]), _at(reference, POOL_TABLE[pool])
        if mine is None or theirs is None:
            continue
        target = {string: index for index, string in enumerate(theirs)}
        translation = [target.get(string, UNMAPPABLE) for string in mine]
        for path in paths:
            values = _at(payload, path)
            if values is None:
                continue
            _set_at(out, path, [v if v < 0 else translation[v] for v in values])
        _set_at(out, POOL_TABLE[pool], list(theirs))
    return out


def _count(value: Any) -> tuple[int, int]:
    """``(columns, elements)`` beneath a block — what the comparison actually examined."""
    if isinstance(value, list):
        return 1, len(value)
    if isinstance(value, dict):
        columns = elements = 0
        for child in value.values():
            c, e = _count(child)
            columns += c
            elements += e
        return columns, elements
    return 1, 1


@dataclass
class ReproductionReport:
    """What was compared, what differed, and — when something did — what kind of difference it is."""

    blocks_compared: list[str] = field(default_factory=list)
    blocks_not_examined: list[str] = field(default_factory=list)
    columns_compared: int = 0
    elements_compared: int = 0
    differences: list[str] = field(default_factory=list)
    interning_only: list[str] = field(default_factory=list)
    intern_walk_failures: list[str] = field(default_factory=list)

    @property
    def is_byte_identical(self) -> bool:
        """The exit criterion: every block outside the two volatile meta fields reproduced exactly."""
        return not self.differences

    @property
    def is_identical_under_remap(self) -> bool:
        """The same catalogue, interned in a different order — correct, and not the claim.

        ⚠ True only when EVERY difference is explained by the remap. One unexplained difference is
        a content difference, and a payload with one wrong number plus a reordered pool is not
        "identical under a remap" — it is wrong.
        """
        return bool(self.differences) and len(self.interning_only) == len(self.differences)

    def render(self) -> str:
        """Coverage first, always — a difference count means nothing without what was examined."""
        lines = [
            f"payload reproduction: {len(self.blocks_compared)} blocks, "
            f"{self.columns_compared:,} columns, {self.elements_compared:,} elements compared "
            f"({', '.join('meta.' + m for m in VOLATILE_META)} excluded as volatile)",
            f"  blocks: {', '.join(self.blocks_compared)}",
        ]
        if self.blocks_not_examined:
            lines.append(f"  ⚠ NOT EXAMINED: {', '.join(self.blocks_not_examined)}")
        for failure in self.intern_walk_failures:
            lines.append(f"  ⚠ INTERN_WALK: {failure}")
        if self.is_byte_identical:
            lines.append("  ✔ byte-identical to the published payload")
            return "\n".join(lines)
        lines.append(f"  ✘ {len(self.differences)} difference(s):")
        lines.extend(f"      {d}" for d in self.differences[:40])
        if len(self.differences) > 40:
            lines.append(f"      … and {len(self.differences) - 40:,} more")
        if self.interning_only:
            lines.append(
                f"  ⓘ {len(self.interning_only)} of these VANISH under a pool remap — the catalogue "
                "is the same, the interning order is not:"
            )
            lines.extend(f"      {d}" for d in self.interning_only[:12])
        return "\n".join(lines)


def compare_payloads(published: dict, rebuilt: dict) -> ReproductionReport:
    """Diff a rebuilt payload against the published one, and diagnose whatever differs.

    Uses nuna's own :func:`diff_payloads` for the comparison itself — the oracle, not a second
    implementation of it — and adds the two things it does not carry: a coverage statement, and the
    interning-versus-content diagnosis.
    """
    from nuna.eval.verify_payload_invariance import diff_payloads

    report = ReproductionReport()
    for block in sorted(set(published) | set(rebuilt)):
        if block in ("schema", "meta"):
            report.blocks_compared.append(block)
            continue
        if block not in published or block not in rebuilt:
            report.blocks_not_examined.append(
                f"{block} (only in {'published' if block in published else 'rebuilt'})"
            )
            continue
        report.blocks_compared.append(block)
        columns, elements = _count(published[block])
        report.columns_compared += columns
        report.elements_compared += elements

    report.intern_walk_failures = verify_intern_walk(published)
    report.differences = diff_payloads(published, rebuilt)
    if report.differences:
        remapped = diff_payloads(published, remap_pools_onto(rebuilt, published))
        # ⚠ Set difference, not a count: a remap can only ever REMOVE differences, so anything the
        # remapped diff still reports is a genuine content difference and stays in `differences`.
        still = set(remapped)
        report.interning_only = [d for d in report.differences if d not in still]
    return report
