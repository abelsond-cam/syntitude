"""Where the database is KNOWN to differ from the frozen page, each one named and explained.

⛔ **This file exists so that "parity" never becomes a tolerance.** A suite that passes with a
percentage bound has stopped being a parity test: it cannot distinguish two loci that moved for a
recorded reason from two hundred that moved because an ingest is wrong. So every exception here is
an explicit set of locus labels with the reason, and a suite that finds a difference OUTSIDE these
sets fails.

⚠ Each entry also asserts its own size. If an exception ever covers more loci than it was written
for, that is a new difference wearing an old label, and it must fail rather than be absorbed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParityException:
    """One recorded difference between the frozen page and what the current artifacts produce."""

    species_key: str
    column: str
    node_labels: frozenset[str]
    frozen_value: str
    current_value: str
    reason: str


#: ⛔ **The published pages were built on 2026-08-25 at git `41e94f4`; the local audit artifacts were
#: regenerated on 2026-09-04 to produce the cluster tables that had never been written.** The re-run
#: overwrote the waterfall CSV and the audit summary, and they are not byte-identical to the ones
#: the pages were built from.
#:
#: The whole of that difference is the retirement of one tier name. `no_homology` **is retired by
#: decision** — it meant *not measured*, not *nothing found* — so the current code no longer emits
#: it, and the two loci that carried it sit at `synteny_only`, which is where the evidence always
#: put them. `synteny_only` names the EVIDENCE, not a mistake.
#:
#: Measured over all 12,104 loci that carry a tier: **12,102 identical, 2 differ.** Every other
#: audit-headline key is identical except the six that are arithmetic consequences of those two
#: loci (`synteny_only_n_clusters` 8→10, `synteny_only_n_genes` 164→168, `synteny_only_gene_rate`,
#: and the three `no_homology_*` keys going to zero).
AUDIT_TIER_RETIREMENT = ParityException(
    species_key="ecoli",
    column="collapse_tier",
    node_labels=frozenset({"10252", "10515"}),
    frozen_value="no_homology",
    current_value="synteny_only",
    reason=(
        "`no_homology` is retired — it meant *not measured*, not *nothing found*. The published "
        "page predates the retirement; the current artifacts postdate it. Two loci, both moving to "
        "`synteny_only`, which is what the evidence always said."
    ),
)

#: ⚠ **The same retirement, in kp — SIX loci, not two.** Jobs 34897030/34897031 re-ran both species
#: in the same pair, so this was always going to be two entries; it was written as one because only
#: *E. coli* had been measured. Found by running the parity suite over kp, which is the whole reason
#: the suite is parameterised over both species rather than over the one that was convenient.
#: Same cause, same direction, same single tier name: **15,664 of 15,670 identical, 6 differ.**
AUDIT_TIER_RETIREMENT_KP = ParityException(
    species_key="kp",
    column="collapse_tier",
    node_labels=frozenset({"8391", "8467", "9756", "9968", "10070", "10289"}),
    frozen_value="no_homology",
    current_value="synteny_only",
    reason=AUDIT_TIER_RETIREMENT.reason.replace("Two loci", "Six loci"),
)

#: Everything, indexed for a suite to consult.
KNOWN_PARITY_EXCEPTIONS: tuple[ParityException, ...] = (
    AUDIT_TIER_RETIREMENT,
    AUDIT_TIER_RETIREMENT_KP,
)


def exceptions_for(species_key: str, column: str) -> ParityException | None:
    """The recorded exception for one (species, column), or `None` if there is none."""
    for exception in KNOWN_PARITY_EXCEPTIONS:
        if exception.species_key == species_key and exception.column == column:
            return exception
    return None
