"""The locator, against the REAL store — because its whole job is knowing where things are.

⛔ A locator tested only against a synthetic tree proves that `Path.__truediv__` works. Every
assertion here resolves a path the published *E. coli* catalogue was actually built from, and the
three filename traps are each pinned by a case that would fail without them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from syntitude_backend.ingest.artifact_locator import (
    REPRESENTATIONS,
    CatalogueArtifacts,
    MissingArtifacts,
)

#: The local mirror of the cluster artifacts. Overridable, because the med school box and any
#: second developer will not have it at a path chosen on one laptop.
DATA_ROOT = Path(os.environ.get("SYNTITUDE_NUNA_DATA_ROOT", "~/developer/nuna/data")).expanduser()
MODEL_LABEL = "ecoli_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL"
RUN_ID = "ecoli_bacformer_clever_exploded_preclusterstrict98pm3b-3b0.5-excl_k100_g100_res0.1_seed0"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT / "proc" / "embeddings" / "meta").is_dir(),
    reason=f"the cluster artifact mirror is not present at {DATA_ROOT}",
)


@pytest.fixture(scope="module")
def ecoli():
    return CatalogueArtifacts(
        data_root=DATA_ROOT, set_key="ecoli", model_label=MODEL_LABEL, run_id=RUN_ID
    )


def test_every_required_artifact_of_the_published_catalogue_resolves(ecoli):
    """Coverage before the claim: the count is asserted, not just the absence of a failure."""
    optional = ecoli.verify()
    assert len(ecoli.required()) == 7 + 6 * len(REPRESENTATIONS) == 19
    assert optional == {"cluster_table": True, "published_payload": True}


def test_all_missing_artifacts_are_named_at_once(ecoli):
    """⛔ One `FileNotFoundError` per run means finding a second gap costs a second run."""
    broken = CatalogueArtifacts(
        data_root=DATA_ROOT, set_key="kp", model_label="kp_nonexistent_model", run_id="kp_nonexistent_run"
    )
    with pytest.raises(MissingArtifacts) as failure:
        broken.verify()

    roles = {role for role, _, _ in failure.value.missing}
    assert {"assignment", "run_manifest", "homology_waterfall", "audit_summary"} <= roles
    assert "supplies" in str(failure.value), "the message does not say what each absent file was for"


def test_the_output_filename_doubles_the_set_token(ecoli):
    """⚠ `locus_browser_ecoli_ecoli_nuna4_…` — a locator assuming one `ecoli` finds nothing."""
    assert ecoli.published_payload.name == f"locus_browser_ecoli_{MODEL_LABEL}.json"
    assert ecoli.published_payload.name.count("ecoli") >= 2
    assert ecoli.published_payload.exists()


def test_the_map_siblings_are_addressed_RELATIVE_to_the_map(ecoli):
    """⛔ `_sibling`'s rule, and the reason a map cannot be paired with another run's geometry."""
    for representation in REPRESENTATIONS:
        catalogue_map = ecoli.catalogue_map(representation)
        for kind in ("node_neighbours", "locus_cos6"):
            sibling = ecoli.map_sibling(representation, kind)
            assert sibling.parent == catalogue_map.parent
            assert sibling.name == catalogue_map.name.replace("_catalogue_map_", f"_{kind}_")
            assert sibling.exists(), sibling


def test_the_meta_sidecars_carry_what_the_csvs_do_not(ecoli):
    """The `.meta` files are the ONLY record of the representation and projection method."""
    for representation in REPRESENTATIONS:
        text = ecoli.catalogue_map_metadata(representation).read_text()
        assert f"rep={representation}" in text
        assert "how=" in text and "metric=" in text
        assert f"model={MODEL_LABEL}" in text
        assert "mean=" in ecoli.null_baseline_metadata(representation).read_text()


def test_a_label_that_does_not_match_its_set_is_refused_up_front(ecoli):
    """Both resolve to paths that exist for a DIFFERENT catalogue, so the check cannot be deferred."""
    with pytest.raises(ValueError, match="does not begin with the set token"):
        CatalogueArtifacts(data_root=DATA_ROOT, set_key="kp", model_label=MODEL_LABEL, run_id=RUN_ID)


def test_the_payload_is_reachable_but_is_named_as_an_oracle(ecoli):
    """⛔ It is not in `required()`, because ingesting it would make the acceptance test circular."""
    roles = {role for role, _, _ in ecoli.required()}
    assert "published_payload" not in roles
    assert "published_payload" in {role for role, _, _ in ecoli.optional()}


def test_the_per_genome_store_holds_five_kinds_for_every_genome(ecoli):
    """⚠ `_noncoding` sits in the same directory and collides with naive globbing."""
    stems = {path.name for path in ecoli.per_genome_root.glob("*.parquet")}
    sample_ids = {name.rsplit("_", 1)[0] for name in stems}
    assert len(sample_ids) == 280, f"{len(sample_ids)} genomes in the store"
    for kind in ("meta", "product", "strand", "dbxref", "noncoding"):
        present = sum(1 for sample_id in sample_ids if ecoli.per_genome(sample_id, kind).exists())
        assert present == 280, f"{kind}: {present}/280"


def test_the_waterfall_is_required_even_though_the_audit_never_names_it(ecoli):
    """⛔ `meta.audit.sources` lists two files; the export read three. It is not the locator."""
    import json

    payload = json.loads(ecoli.published_payload.read_text())
    named = payload["meta"]["audit"]["sources"]
    assert not any("waterfall" in source for source in named), "the audit now names it — update the docstring"
    assert "homology_waterfall" in {role for role, _, _ in ecoli.required()}
    assert ecoli.homology_waterfall.exists()
