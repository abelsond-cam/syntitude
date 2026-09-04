"""Follow a run manifest's chain when the artifacts are a MIRROR of the tree that wrote them.

⛔⛔ **The problem, precisely.** A run manifest records its parent as an **absolute path on the
machine that produced it** — `/home/dca36/rds/…/probe_ecoli_kleb_200/analysis/step3b_rho_merge/
assignments/….tsv`. On CSD3 that resolves and `load_run_chain` walks the whole pipeline. On this
laptop the same string resolves to nothing, so the walk stops after one manifest and a four-step
model is recorded as a one-step one — **silently**, because a short chain is exactly what a genuinely
one-step model produces.

Measured cost of that silence: the published page's footer prints **nine** provenance rows read from
**three** manifests, naming the dedup, the ESM over-merge at γ 0.98, the Bacformer split at γ 0.5
`pairwise_max` and the global merge at γ 0.1 `ceiling`. Ingested without this adapter the database
recorded **seven** rows from **one** manifest, of which the only pipeline row said *"step 1 · dedup:
not recorded in any manifest"* and one merge step. Nothing was wrong with the ingest; the parent
files simply were not on this machine.

⭐ **The rewrite is derived, not hardcoded.** Both trees share everything from the `analysis/`
segment down — that is what makes one a mirror of the other — so the pivot is that segment and the
new root is the locator's own `processed_root`. A hardcoded `/home/dca36/…` prefix would break the
day the data moves, and would break silently in the same way.

⚠ **It is scoped to a `with` block and it is explicit.** Rebinding a library function is not a thing
to leave switched on: outside this block `run_manifest.read_manifest` means what nuna says it means.
Inside it, one clearly-named adapter says "these absolute paths are from the machine that wrote
them; our copies are here" — which is a fact about *our mirror*, not about nuna.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

#: The directory both trees share from, and the reason a rewrite is possible at all.
MIRROR_PIVOT = "analysis"


def mirror_path(remote: Path | str, processed_root: Path) -> Path | None:
    """``remote`` re-rooted into the local mirror, or ``None`` when it carries no pivot.

    ``None`` is not a failure — a path that is already local has nothing to rewrite. It is the
    caller's job to notice a chain that came out shorter than it should have.
    """
    parts = Path(remote).parts
    if MIRROR_PIVOT not in parts:
        return None
    return Path(processed_root).joinpath(*parts[parts.index(MIRROR_PIVOT) :])


@contextmanager
def manifests_resolved_against(processed_root: Path) -> Iterator[None]:
    """Resolve manifest paths into the local mirror for the length of one chain walk.

    ⛔ The local file is preferred only when the recorded path does **not** exist; a path that
    resolves as written is read as written, so running this on CSD3 changes nothing at all.
    """
    from nuna.tl.cluster import run_manifest

    original = run_manifest.read_manifest

    def resolved(assign: Path | str):
        if Path(assign).exists():
            return original(assign)
        local = mirror_path(assign, processed_root)
        return original(local) if local is not None else original(assign)

    run_manifest.read_manifest = resolved
    try:
        yield
    finally:
        run_manifest.read_manifest = original
