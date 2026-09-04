"""The catalogues the live pages serve — the `(species, model_label, run_id)` triples, checked in.

⛔ **The run_id is NOT the model label with the species swapped, and guessing it fails silently in
the worst way: it resolves.** The two published runs are

    ecoli   …_preclusterstrict98pm3b-3b0.5-excl_…
    kp      …_preclusterkp98pm3b-3b0.5-excl_…

`strict98` against `kp98`. Substituting `kp` for `ecoli` in the *E. coli* run_id yields a path that
does not exist — which is the lucky case. A run_id that differs only in a **default-emitted token**
would resolve to a different run's assignment and load a whole catalogue that is wrong about which
model produced it, because *"run ids emit tokens non-default-only"*: two models differing only in a
ρ rule have produced byte-identical provenance.

So the triples live here, in the repo, rather than being reconstructed by a rule. `meta.model_id` in
a published payload is the only other place they are written down, and that is an output.

⚠ Both are **`nuna4` on the superseded DAMPED weight** — the `-excl` token, decoded by
`exclusivity.form_from_run_id`, is `damped_exclusion`. `-excl` is a *prefix* of `-exclLOGP`, so
never test it with `in` / `endswith` / `.replace`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishedCatalogue:
    """One species' live catalogue, as `published.tsv` and the shipped payload agree it is."""

    species_key: str
    set_key: str
    model_label: str
    run_id: str
    #: What the shipped payload's `meta` says, so an ingest can reconcile against it rather than
    #: against a number someone remembered.
    genome_count: int
    gene_count: int
    locus_count: int


PUBLISHED_CATALOGUES: tuple[PublishedCatalogue, ...] = (
    PublishedCatalogue(
        species_key="ecoli",
        set_key="ecoli",
        model_label="ecoli_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL",
        run_id="ecoli_bacformer_clever_exploded_preclusterstrict98pm3b-3b0.5-excl_k100_g100_res0.1_seed0",
        genome_count=100,
        gene_count=489_146,
        locus_count=17_531,
    ),
    PublishedCatalogue(
        species_key="kp",
        set_key="kp",
        model_label="kp_nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL",
        # ⛔ `preclusterkp98pm3b`, NOT `preclusterstrict98pm3b`. See the module docstring.
        run_id="kp_bacformer_clever_exploded_preclusterkp98pm3b-3b0.5-excl_k100_g100_res0.1_seed0",
        genome_count=100,
        gene_count=532_851,
        locus_count=15_670,
    ),
)


def catalogue(species_key: str) -> PublishedCatalogue:
    """The published catalogue for one species, or a failure naming what is known."""
    for entry in PUBLISHED_CATALOGUES:
        if entry.species_key == species_key:
            return entry
    known = [entry.species_key for entry in PUBLISHED_CATALOGUES]
    raise KeyError(f"no published catalogue for {species_key!r}; known: {known}")
