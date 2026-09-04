"""The mirror adapter, checked against the real manifests and the real published provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from syntitude_backend.ingest.mirrored_manifest_chain import (
    manifests_resolved_against,
    mirror_path,
)
from tests.conftest import NUNA_DATA_ROOT, artifacts_for, requires_artifacts

CSD3 = Path(
    "/home/dca36/rds/rds-floto-bacterial-4k08a2yyQLw/david/nuna/processed/probe_ecoli_kleb_200"
    "/analysis/step3b_rho_merge/assignments/x.tsv"
)


def test_the_rewrite_pivots_on_analysis_and_is_not_a_hardcoded_prefix():
    """⭐ Derived from the segment both trees share, so it survives the data moving."""
    rewritten = mirror_path(CSD3, Path("/local/data/proc"))
    assert rewritten == Path("/local/data/proc/analysis/step3b_rho_merge/assignments/x.tsv")


def test_a_path_with_no_pivot_returns_None_rather_than_a_guess():
    """⚠ None means *nothing to rewrite*, which is not the same as *rewritten to nothing*."""
    assert mirror_path(Path("/somewhere/else/x.tsv"), Path("/local/data/proc")) is None


@requires_artifacts
@pytest.mark.parametrize("species", ["ecoli", "kp"])
def test_the_chain_reaches_THREE_manifests_and_reproduces_the_published_provenance(species):
    """⛔⛔ **The defect this adapter exists for, measured on both published catalogues.**

    Without it the walk stops at one manifest and the four-step model is recorded as one step — a
    short chain being exactly what a real one-step model produces, so nothing anywhere says so. The
    published payload's footer is the oracle: nine rows read from three manifests, byte for byte.
    """
    from nuna.tl.cluster import run_manifest
    from nuna.tl.probe.accessory_audit_run import model_provenance, parse_model_id

    artifacts = artifacts_for(species)
    published = json.loads(artifacts.published_payload.read_text())

    unadapted = run_manifest.load_run_chain(artifacts.assignment)
    with manifests_resolved_against(NUNA_DATA_ROOT / "proc"):
        chain = run_manifest.load_run_chain(artifacts.assignment)
        rows = model_provenance(
            artifacts.run_id, parse_model_id(artifacts.assignment), assign=artifacts.assignment
        )

    assert len(unadapted) == 1, "the unadapted walk should reach exactly one manifest on this machine"
    assert len(chain) == 3, f"{species}: the chain reached {len(chain)} manifests, not 3"
    assert [entry["_depth"] for entry in chain] == [0, 1, 2]
    assert [list(pair) for pair in rows] == published["meta"]["provenance"]


def test_the_adapter_is_REMOVED_on_exit_including_after_a_failure():
    """⛔ A rebinding left switched on is a library that means something else everywhere else."""
    from nuna.tl.cluster import run_manifest

    before = run_manifest.read_manifest
    with manifests_resolved_against(Path("/nowhere")):
        assert run_manifest.read_manifest is not before
    assert run_manifest.read_manifest is before

    with pytest.raises(RuntimeError):  # noqa: PT012 — the point is that the body raises
        with manifests_resolved_against(Path("/nowhere")):
            raise RuntimeError("boom")
    assert run_manifest.read_manifest is before


def test_a_path_that_RESOLVES_as_written_is_read_as_written(tmp_path):
    """⚠ On CSD3 the recorded paths are correct, so the adapter must be a no-op there."""
    from nuna.tl.cluster import run_manifest

    assignments = tmp_path / "analysis" / "step" / "assignments"
    runs = tmp_path / "analysis" / "step" / "runs"
    assignments.mkdir(parents=True)
    runs.mkdir(parents=True)
    (assignments / "r.tsv").write_text("")
    (runs / "r.json").write_text(json.dumps({"run_id": "r", "rep": "esm"}))

    with manifests_resolved_against(Path("/a/mirror/that/does/not/exist")):
        assert run_manifest.read_manifest(assignments / "r.tsv") == {"run_id": "r", "rep": "esm"}
