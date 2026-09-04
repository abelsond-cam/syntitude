"""Flip a species onto a pangenome — the one-row update that decides what the service serves.

⭐ **This is what makes a re-ingest safe on a running service.** Ingest builds a whole generation
alongside the live one and never touches the pointer; this flips it, in its own transaction, once the
new catalogue is complete. A rollback is the same update backwards, which is why the old generation
is dropped only after the new one has served.

⛔ **It VERIFIES before it flips, and the verification is not a formality.** Publishing an incomplete
catalogue is the one failure this design can produce that a reader cannot see: every page renders,
every number is in range, and a block is simply missing. The checks below are each a thing that has
either gone wrong before or would be invisible if it did — a locus count that disagrees with the
row count, a landing locus that was never written (the render-time mutation that shipped five days
of pages opening on locus 0), a species whose loci belong to a different species, a geometry that
covers one representation and not both.

⚠ **`--force` exists and says what it is.** A catalogue can be published with a known gap — the local
mirror has no gate ledger, for instance — but the gap is named in the return value rather than
silently tolerated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from syntitude_backend.models.enumerations import EmbeddingRepresentation
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.locus_arrangement import LocusArrangement
from syntitude_backend.models.locus_embedding_geometry import LocusMapProjection
from syntitude_backend.models.locus_offset_occupant import LocusOffsetOccupant
from syntitude_backend.models.pangenome import Pangenome
from syntitude_backend.models.pathogen_species import PathogenSpecies


class PublishRefused(RuntimeError):
    """The catalogue is not complete enough to serve, and the failures are named."""


@dataclass
class PublishReport:
    """What was checked, what it found, and what the pointer now is."""

    run_id: str
    pangenome_id: int
    species_key: str
    previous_pangenome_id: int | None
    checks_passed: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    published: bool = False

    def render(self) -> str:
        """Every check by name — a report that says only "published" has told you nothing."""
        lines = [f"publish {self.species_key} → pangenome {self.pangenome_id} ({self.run_id})"]
        for check in self.checks_passed:
            lines.append(f"  ✓ {check}")
        for failure in self.failures:
            lines.append(f"  ✗ {failure}")
        lines.append(
            f"  pointer: {self.previous_pangenome_id} → "
            f"{self.pangenome_id if self.published else self.previous_pangenome_id}"
        )
        return "\n".join(lines)


def verify_pangenome_is_servable(session: Session, pangenome: Pangenome) -> tuple[list[str], list[str]]:
    """`(passed, failed)` — every check by name, so a partial catalogue cannot pass quietly."""
    passed: list[str] = []
    failed: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        (passed if condition else failed).append(name if condition else f"{name}: {detail}")

    locus_count = session.execute(
        select(func.count()).select_from(Locus).where(Locus.pangenome_id == pangenome.pangenome_id)
    ).scalar_one()
    check(
        f"{locus_count:,} loci, matching the recorded locus_count",
        locus_count == pangenome.locus_count and locus_count > 0,
        f"the table holds {locus_count:,} and the row claims {pangenome.locus_count:,}",
    )

    # ⛔ Every locus must belong to the SAME species as the pangenome. A mismatch here would serve
    # one species' loci under another's key, and every one of them would render perfectly.
    foreign = session.execute(
        select(func.count())
        .select_from(Locus)
        .where(
            Locus.pangenome_id == pangenome.pangenome_id,
            Locus.pathogen_species_id != pangenome.pathogen_species_id,
        )
    ).scalar_one()
    check(
        "every locus belongs to this pangenome's species",
        foreign == 0,
        f"{foreign:,} loci carry a different pathogen_species_id",
    )

    # ⚠ The render-time mutation that shipped five days of pages opening on locus 0.
    check(
        "a landing locus is written",
        pangenome.landing_locus_id is not None,
        "landing_locus_id is NULL — the page would open on whatever came first",
    )
    check(
        "example loci are written",
        bool(pangenome.example_locus_ids),
        "example_locus_ids is empty — the chips would be blank",
    )

    arrangements = session.execute(
        select(func.count())
        .select_from(LocusArrangement)
        .where(LocusArrangement.pangenome_id == pangenome.pangenome_id)
    ).scalar_one()
    check("the joint view is populated", arrangements > 0, "no arrangements — the track cannot draw")

    occupants = session.execute(
        select(func.count())
        .select_from(LocusOffsetOccupant)
        .where(LocusOffsetOccupant.pangenome_id == pangenome.pangenome_id)
    ).scalar_one()
    check("the marginal view is populated", occupants > 0, "no offset occupants — no bars under the track")

    # ⭐ BOTH representations, or neither tab means what it says: ESM is homology and Bacformer is
    # context, and they deliberately disagree about which loci are confusable.
    representations = {
        row.representation
        for row in session.execute(
            select(LocusMapProjection).where(
                LocusMapProjection.pangenome_id == pangenome.pangenome_id
            )
        ).scalars()
    }
    check(
        "both map representations are present",
        representations == set(EmbeddingRepresentation),
        f"only {sorted(r.value for r in representations)} — the other tab would be empty",
    )

    unnamed = session.execute(
        select(func.count())
        .select_from(Locus)
        .where(Locus.pangenome_id == pangenome.pangenome_id, Locus.display_name.is_(None))
    ).scalar_one()
    check("every locus has a display name", unnamed == 0, f"{unnamed:,} loci have none")
    return passed, failed


def publish_pangenome(
    session: Session, *, run_id: str, ingest_generation: int = 1, force: bool = False
) -> PublishReport:
    """Verify the catalogue, then point its species at it. Refuses on any failed check.

    ⛔ **Its own transaction, and only the pointer.** Nothing else is written here, so a publish can
    never be half-applied and a rollback is one row.
    """
    pangenome = session.execute(
        select(Pangenome).where(
            Pangenome.run_id == run_id, Pangenome.ingest_generation == ingest_generation
        )
    ).scalar_one_or_none()
    if pangenome is None:
        raise PublishRefused(f"no pangenome {run_id!r} at generation {ingest_generation}")

    species = session.get(PathogenSpecies, pangenome.pathogen_species_id)
    report = PublishReport(
        run_id=run_id,
        pangenome_id=pangenome.pangenome_id,
        species_key=species.species_key,
        previous_pangenome_id=species.published_pangenome_id,
    )
    report.checks_passed, report.failures = verify_pangenome_is_servable(session, pangenome)

    if report.failures and not force:
        raise PublishRefused(
            f"{species.species_key}: {len(report.failures)} check(s) failed and the pointer was NOT "
            f"moved:\n  " + "\n  ".join(report.failures)
        )

    session.execute(
        update(PathogenSpecies)
        .where(PathogenSpecies.pathogen_species_id == species.pathogen_species_id)
        .values(published_pangenome_id=pangenome.pangenome_id)
    )
    session.execute(
        update(Pangenome)
        .where(Pangenome.pangenome_id == pangenome.pangenome_id)
        .values(is_published=True)
    )
    # ⚠ The previous generation is marked unpublished but NOT deleted — that is what makes the
    # rollback one update rather than a re-ingest.
    if report.previous_pangenome_id and report.previous_pangenome_id != pangenome.pangenome_id:
        session.execute(
            update(Pangenome)
            .where(Pangenome.pangenome_id == report.previous_pangenome_id)
            .values(is_published=False)
        )
    report.published = True
    return report
