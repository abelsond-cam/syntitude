"""The model definition and its per-step parameters.

⭐ **Every parameter that varies by step lives on the STEP, not on the model.** γ, the ρ rule, the ρ
ceiling, ρ exit, ρ continue, the representation, the node mode and whether a step uses the
exclusivity weight are all per-step; a schema putting any of them on `nuna_model` asserts something
false about every multi-step chain. `nuna5` has five steps and no two share a γ/ρ pair.

These rows are what the browser's footer already prints, via
`accessory_audit_run.model_provenance` → `_provenance_from_chain`.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from syntitude_backend.database import Base
from syntitude_backend.models.enumerations import (
    EmbeddingRepresentation,
    ExclusivityForm,
    ExclusivityFormSource,
    RhoRule,
)


class NunaModel(Base):
    """One entry in `nuna_pipeline.MODELS` — `nuna5`, `nuna5damped`, `nuna4`, …

    Only what is true of the chain **as a whole**. Anything that differs between steps is on
    :class:`NunaModelStep`.
    """

    __tablename__ = "nuna_model"
    __table_args__ = (UniqueConstraint("model_key"),)

    nuna_model_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: The registry key. ⛔ `nuna5` CHANGED MEANING on 2026-08-24 — it now names the standard
    #: exclusion, and the damped chain is `nuna5damped`. Any number attributed to "nuna5" in a
    #: document written before that date means `nuna5damped`.
    model_key: Mapped[str] = mapped_column(String(64), nullable=False)

    #: `ModelSpec.label` — the full on-disk model label, which addresses the audit artifacts.
    label: Mapped[str] = mapped_column(String(256), nullable=False)

    dedup_identity: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    dedup_coverage: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    #: k applies to EVERY step, which is why it is here and γ is not.
    knn_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⛔ First-class, NOT NULL, and never re-derived from a run_id after ingest.
    #: `-excl` is a PREFIX of `-exclLOGP`; four readers got this wrong silently in one day.
    #: `exclusivity.form_from_run_id` is the only permitted decoder.
    exclusivity_form: Mapped[ExclusivityForm] = mapped_column(nullable=False)

    merge_algorithm: Mapped[str | None] = mapped_column(String(128), nullable=True)
    graph_construction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    step_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    registry_source_git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    steps: Mapped[list["NunaModelStep"]] = relationship(
        back_populates="nuna_model", order_by="NunaModelStep.step_ordinal", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NunaModel {self.model_key} ({self.exclusivity_form.value})>"


class NunaModelStep(Base):
    """One step of the chain, with its own γ, its own ρ rail, and its own representation."""

    __tablename__ = "nuna_model_step"
    __table_args__ = (UniqueConstraint("nuna_model_id", "step_ordinal"),)

    nuna_model_step_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nuna_model_id: Mapped[int] = mapped_column(
        ForeignKey("nuna_model.nuna_model_id", ondelete="CASCADE"), nullable=False
    )

    step_ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: `step1_dedup`, `step2`, `step3b`, `step3c`, `step4`, `step4b`, `step4c`, `step4d`.
    step_name: Mapped[str] = mapped_column(String(32), nullable=False)

    representation: Mapped[EmbeddingRepresentation | None] = mapped_column(nullable=True)

    #: ⭐ The resolution. NULL only on the dedup step, which is not a CPM pass at all.
    gamma: Mapped[float | None] = mapped_column(Numeric(8, 5), nullable=True)

    #: ⭐ The ρ rail. `grouped_rho_cpm` REFUSES ceiling+exclusivity's precondition under
    #: `pairwise_max`, because that rule deliberately admits colliding pairs and the exclusivity
    #: weight reads only endpoint genome counts — meaningful only where edges are genome-disjoint.
    rho_rule: Mapped[RhoRule | None] = mapped_column(nullable=True)
    rho_ceiling: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    rho_exit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rho_continue: Mapped[str | None] = mapped_column(String(16), nullable=True)

    #: `mmseq` | `precluster` | `native`.
    node_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uses_exclusivity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: `s·mᵢmⱼ` or `f·mᵢmⱼ`. ⚠ The two exclusivity forms enter the expression at DIFFERENT points
    #: and must: `damped_exclusion` multiplies AFTER `mᵢmⱼ` exactly as published, while `f` caps at
    #: 1 so it must hit `s` BEFORE `mᵢmⱼ` or γ means something different at every node size.
    edge_weight_expression: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: `gene_count`. A column because dropping it while keeping the weight changes what γ means at
    #: every node size — so it is a fact about a step, not a constant.
    node_sizes: Mapped[str | None] = mapped_column(String(32), nullable=True)

    #: The two strings the browser footer prints verbatim, from `run_manifest.stage_name` /
    #: `stage_detail`. Stored rather than formatted, so the page and the database cannot disagree.
    stage_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stage_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: ⚠ How this row was determined. Run ids emit tokens NON-DEFAULT-ONLY, so an absent token means
    #: "whatever the default was when that run was made" and is not recoverable from the id at all.
    #: A row read from a manifest and a row guessed from a token are different evidence, and the
    #: fallback has to say so on its face.
    provenance_source: Mapped[ExclusivityFormSource | None] = mapped_column(nullable=True)

    nuna_model: Mapped[NunaModel] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<NunaModelStep {self.step_name} γ={self.gamma} ρ={self.rho_rule}>"
