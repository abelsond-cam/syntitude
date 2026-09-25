"""Every region the drawn track needs arrives with the locus — not just the two beside the focal gene.

⛔⛔ **Found by LOOKING at the rebuilt page beside the published one.** The locus response carried
only the gaps the focal locus is an endpoint of, so the track drew two intergenic regions and packed
the other nine genes edge to edge — which reads as *"these genes are adjacent, with nothing between
them"*, a claim the data does not make, on every locus. No test could see it: every assertion about
gaps was about the focal pair, and the rebuilt page renders a perfectly plausible track either way.

The oracle here is the gap table itself, read independently: for every pair of loci drawn side by
side in any listed arrangement, if the database HOLDS a region for that pair, the response must
carry it.
"""

from __future__ import annotations

import os
import random

import pytest
from sqlalchemy import create_engine, select, tuple_
from sqlalchemy.orm import Session

from syntitude_backend.application_factory import create_application
from syntitude_backend.configuration import Configuration
from syntitude_backend.models.intergenic_gap import IntergenicGap
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.pathogen_species import PathogenSpecies

#: Loci per species. Seeded, so a failure names loci that fail again.
SAMPLE = 150


@pytest.fixture(scope="module")
def application():
    url = os.environ.get("SYNTITUDE_DATABASE_URL")
    if not url:
        pytest.skip("SYNTITUDE_DATABASE_URL is not set — this runs against a loaded database")
    create_engine(url, future=True)
    return create_application(Configuration(database_url=url))


def _pair(a, b) -> tuple:
    """Order-free, and ⚠ NOT a frozenset: tandem copies put a locus beside ITSELF, and a set of one
    element would silently turn that pair into something else."""
    return (a, b) if a <= b else (b, a)


def _drawn_label_pairs(response: dict) -> set[tuple]:
    """Adjacent pairs in every listed arrangement, as LABELS — contig ends break adjacency."""
    focal = response["locus"]["label"]
    pairs = set()
    for arrangement in response["arrangements"]["listed"]:
        slots = [slot["locus"] for slot in arrangement["slots"]]
        window = slots[:5] + [focal] + slots[5:]
        for left, right in zip(window, window[1:], strict=False):
            if left is not None and right is not None:
                pairs.add(_pair(left, right))
    return pairs


@pytest.mark.parametrize("species_key", ["ecoli", "kp"])
def test_every_region_the_track_draws_is_in_the_response(application, species_key):
    engine = application.extensions["syntitude_database"].engine
    client = application.test_client()
    with Session(engine) as session:
        pangenome_id = session.execute(
            select(PathogenSpecies.default_pangenome_id).where(PathogenSpecies.species_key == species_key)
        ).scalar_one()
        labels = [
            label
            for (label,) in session.execute(
                select(Locus.node_label).where(Locus.pangenome_id == pangenome_id).order_by(Locus.catalogue_ordinal)
            )
        ]
        chosen = random.Random(20260918).sample(labels, SAMPLE)
        id_by_label = dict(
            session.execute(select(Locus.node_label, Locus.locus_id).where(Locus.pangenome_id == pangenome_id)).all()
        )

        drawn_pairs = 0
        stored_pairs = 0
        beyond_the_focal = 0
        for label in chosen:
            response = client.get(f"/api/v1/species/{species_key}/loci/{label}").get_json()
            carried = {_pair(*gap["flanking_loci"]) for gap in response["intergenic_gaps"]}
            # ⛔ No gap may arrive half-labelled: the client cannot key it and silently drops it.
            assert all(None not in gap["flanking_loci"] for gap in response["intergenic_gaps"]), label
            wanted = _drawn_label_pairs(response)
            drawn_pairs += len(wanted)
            ids = [(id_by_label[a], id_by_label[b]) for a, b in wanted]
            ids += [(b, a) for a, b in ids]
            stored = {
                (a, b)
                for a, b in session.execute(
                    select(IntergenicGap.flanking_locus_id_a, IntergenicGap.flanking_locus_id_b).where(
                        IntergenicGap.pangenome_id == pangenome_id,
                        tuple_(IntergenicGap.flanking_locus_id_a, IntergenicGap.flanking_locus_id_b).in_(ids),
                    )
                )
            } if ids else set()
            label_by_id = {value: key for key, value in id_by_label.items()}
            stored_labels = {_pair(label_by_id[a], label_by_id[b]) for a, b in stored}
            stored_pairs += len(stored_labels)
            beyond_the_focal += sum(1 for pair in stored_labels if label not in pair)
            missing = stored_labels - carried
            assert not missing, f"{species_key} locus {label}: {len(missing)} drawn regions not carried"

    # ⛔ Coverage before the verdict — and specifically the pairs the old query could never return.
    assert drawn_pairs > SAMPLE * 5, drawn_pairs
    assert stored_pairs > SAMPLE * 3, stored_pairs
    assert beyond_the_focal > SAMPLE, (
        f"only {beyond_the_focal} stored regions away from the focal gene — the sample does not exercise the bug"
    )
