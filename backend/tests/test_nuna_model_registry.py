"""The registry ingest: does `nuna_model_step` say what the model actually is?

Every assertion here is against `CLAUDE.md`'s own five-step table, which is the published statement
of what `nuna5` is. If this file and that table ever disagree, one of them is wrong about the model
of record — which is exactly the disagreement worth failing a build over.
"""

import pytest

from syntitude_backend.ingest.ingest_nuna_model_registry import (
    STEP2_RHO_CEILING,
    expand_model_steps,
    ingest_model_registry,
    model_key_for_audit_label,
    model_key_for_label,
    rho_rule_is_effectively_off,
)
from syntitude_backend.models.enumerations import EmbeddingRepresentation, ExclusivityForm, RhoRule
from syntitude_backend.models.nuna_model import NunaModel, NunaModelStep

nuna_pipeline = pytest.importorskip(
    "nuna.tl.cluster.nuna_pipeline",
    reason="the registry ingest reads MODELS; nuna is the ingest extra, not a serving dependency",
)
MODELS = nuna_pipeline.MODELS


def steps_by_name(model_key):
    return {step.step_name: step for step in expand_model_steps(MODELS[model_key])}


def test_nuna5_is_the_five_step_chain_CLAUDE_md_describes():
    steps = steps_by_name("nuna5")
    assert list(steps) == ["step1_dedup", "step2", "step3b", "step3c", "step4"]
    assert steps["step2"].gamma == 0.98
    assert steps["step3b"].gamma == 0.5
    assert steps["step3c"].gamma == 0.2
    assert steps["step4"].gamma == 0.5
    assert steps["step2"].representation is EmbeddingRepresentation.ESM
    assert all(
        steps[name].representation is EmbeddingRepresentation.BACFORMER
        for name in ("step3b", "step3c", "step4")
    )


def test_no_two_steps_of_nuna5_share_a_gamma_rho_pair():
    """The whole reason these columns are on the STEP and not on the model."""
    pairs = [
        (step.gamma, step.rho_rule, step.rho_ceiling)
        for step in expand_model_steps(MODELS["nuna5"])
        if step.gamma is not None
    ]
    assert len(pairs) == len(set(pairs))


def test_step_2_carries_the_literal_1e9_ceiling_the_column_was_widened_for():
    assert steps_by_name("nuna5")["step2"].rho_ceiling == STEP2_RHO_CEILING == 1e9


def test_step_3b_is_pairwise_max_and_carries_NO_exclusivity():
    """A precondition, not a preference — `grouped_rho_cpm` refuses the combination outright."""
    step = steps_by_name("nuna5")["step3b"]
    assert step.rho_rule is RhoRule.PAIRWISE_MAX
    assert step.uses_exclusivity is False


def test_the_two_exclusivity_forms_produce_DIFFERENT_edge_weights():
    """`f` caps at 1 so it multiplies `s`; the damped form multiplies after `mᵢmⱼ`, as published."""
    assert steps_by_name("nuna5")["step4"].edge_weight_expression == "f·mᵢmⱼ"
    assert steps_by_name("nuna5damped")["step4"].edge_weight_expression == "s·mᵢmⱼ·(1−P₀)"


def test_nuna4_has_no_step_3c_and_merges_at_gamma_0_point_1():
    steps = steps_by_name("nuna4")
    assert "step3c" not in steps
    assert steps["step4"].gamma == 0.1


def test_the_dedup_step_has_no_cpm_parameters_at_all():
    """It runs in a different environment and has no manifest; NULL is the honest shape, not 0."""
    step = steps_by_name("nuna5")["step1_dedup"]
    assert (step.gamma, step.rho_rule, step.rho_ceiling, step.node_mode) == (None, None, None, None)


def test_a_split_step_4_gives_4b_no_rho_continue_because_it_gets_no_exclusivity():
    """`_merge_pass` passes `--rho-continue` only inside its `if excl` block."""
    steps = steps_by_name("nuna6d")
    assert [n for n in steps if n.startswith("step4")] == ["step4b", "step4c", "step4d"]
    assert steps["step4b"].uses_exclusivity is False
    assert steps["step4b"].rho_continue is None
    assert steps["step4c"].uses_exclusivity is True


def test_every_model_in_the_registry_expands_without_raising():
    """Coverage, stated: the registry is the vocabulary of the whole system, so all of it is loaded."""
    expanded = {key: expand_model_steps(spec) for key, spec in MODELS.items()}
    assert len(expanded) == len(MODELS) >= 13
    assert all(len(steps) >= 4 for steps in expanded.values())


# ── the OFF normalisation ──────────────────────────────────────────────────────────────────────
def test_a_ceiling_of_1e9_reads_as_rho_off_whatever_the_rule_string_says():
    """The manifest records `ceiling` for step 2 and the model means OFF. Not a disagreement."""
    assert rho_rule_is_effectively_off("ceiling", 1e9) is True
    assert rho_rule_is_effectively_off("off", None) is True
    assert rho_rule_is_effectively_off("ceiling", 1.0) is False
    assert rho_rule_is_effectively_off("pairwise_max", 1.0) is False


# ── label resolution ───────────────────────────────────────────────────────────────────────────
def test_the_audit_label_is_the_registry_label_with_the_set_token_prefixed():
    key = model_key_for_audit_label("ecoli_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL", "ecoli", MODELS)
    assert key == "nuna4"
    assert model_key_for_audit_label(
        "kp_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL", "kp", MODELS
    ) == "nuna4"


def test_an_unknown_label_raises_naming_what_is_known_rather_than_guessing():
    with pytest.raises(KeyError, match="no MODELS entry"):
        model_key_for_label("nuna9_the_one_that_never_ran", MODELS)


def test_a_label_without_its_set_token_is_refused():
    with pytest.raises(ValueError, match="does not begin with the set token"):
        model_key_for_audit_label("nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL", "ecoli", MODELS)


# ── against the real tables ────────────────────────────────────────────────────────────────────
def test_the_whole_registry_loads_into_postgres_and_reloads_idempotently(session):
    first = ingest_model_registry(session, models=MODELS)
    session.flush()
    written = session.query(NunaModelStep).count()
    assert written == sum(len(expand_model_steps(spec)) for spec in MODELS.values())

    second = ingest_model_registry(session, models=MODELS)
    session.flush()
    assert second == first, "a re-ingest must keep every nuna_model_id — pangenomes point at them"
    assert session.query(NunaModelStep).count() == written, "steps were duplicated, not replaced"


def test_the_registry_row_records_the_form_that_names_the_model(session):
    ingest_model_registry(session, models=MODELS)
    session.flush()
    rows = {row.model_key: row for row in session.query(NunaModel).all()}
    assert rows["nuna5"].exclusivity_form is ExclusivityForm.EXCLUSION
    assert rows["nuna5damped"].exclusivity_form is ExclusivityForm.DAMPED_EXCLUSION
    assert rows["nuna4"].exclusivity_form is ExclusivityForm.DAMPED_EXCLUSION
