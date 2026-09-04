"""The roster: the ordinal `arr.gid` indexes into, and the two ways it can be silently wrong.

Both failures here are invisible in the data — an ordering that is one place out renames every
genome on the page, and a collection with a hole in it does the same from the first gap onward.
Neither raises anywhere downstream, so each is asserted at the point it is created.
"""

import pytest
from sqlalchemy import select

from syntitude_backend.ingest.artifact_locator import CatalogueArtifacts
from syntitude_backend.ingest.ingest_genome_collection_roster import (
    RosterError,
    genome_id_by_ordinal,
    ingest_genome_collection,
    read_genome_vocabulary,
)
from syntitude_backend.ingest.ingest_pathogen_species import ingest_pathogen_species
from syntitude_backend.models.enumerations import SampleIdentifierKind
from syntitude_backend.models.genome import Genome
from syntitude_backend.models.genome_collection import GenomeCollection, GenomeCollectionMembership

pandas = pytest.importorskip("pandas", reason="the ingest extra")


def _stage_genome_rows(session, species_id, sample_ids):
    """The genome layer, reduced to what the roster join needs — one row per accession."""
    session.add_all(
        [
            Genome(
                pathogen_species_id=species_id,
                sample_id=sample_id,
                sample_id_kind=SampleIdentifierKind.BIOSAMPLE,
            )
            for sample_id in sample_ids
        ]
    )
    session.flush()


def _fake_universe(tmp_path, sample_ids):
    """A `{set}_close_seq.parquet` with a chosen vocabulary, in the real directory shape."""
    root = tmp_path / "data"
    (root / "proc" / "mmseqs").mkdir(parents=True)
    pandas.DataFrame(
        {"sample_id": sample_ids, "flat_index": list(range(len(sample_ids)))}
    ).to_parquet(root / "proc" / "mmseqs" / "probe_close_seq.parquet")
    return CatalogueArtifacts(
        data_root=root, set_key="probe", model_label="probe_model", run_id="probe_run"
    )


# ── the vocabulary ─────────────────────────────────────────────────────────────────────────────
def test_the_vocabulary_is_the_UNIVERSE_sorted_and_it_matches_the_published_counts(
    ecoli_artifacts, published_ecoli_site_catalogue
):
    """⛔ `meta.genomes` is a published contract. This is the list `arr.gid` indexes into."""
    samples, n_genes = read_genome_vocabulary(ecoli_artifacts)
    assert samples == published_ecoli_site_catalogue["meta"]["genomes"]
    assert len(samples) == published_ecoli_site_catalogue["meta"]["n_genomes"] == 100
    assert n_genes == published_ecoli_site_catalogue["meta"]["n_genes"] == 489_146


def test_the_vocabulary_is_sorted_and_distinct_and_that_is_asserted_not_assumed(ecoli_artifacts):
    samples, _ = read_genome_vocabulary(ecoli_artifacts)
    assert samples == sorted(samples)
    assert len(set(samples)) == len(samples)


# ── the two silent failures ────────────────────────────────────────────────────────────────────
def test_a_roster_genome_with_no_genome_row_is_REFUSED_rather_than_skipped(session, tmp_path):
    """A hole would shift every membership after it by one, and nothing downstream could tell."""
    species_ids = ingest_pathogen_species(session)
    session.flush()
    _stage_genome_rows(session, species_ids["ecoli"], ["SAM_A", "SAM_B"])
    artifacts = _fake_universe(tmp_path, ["SAM_A", "SAM_B", "SAM_MISSING"])
    with pytest.raises(RosterError, match="no `genome` row"):
        ingest_genome_collection(session, artifacts, pathogen_species_id=species_ids["ecoli"])


def test_ordinals_with_a_hole_in_them_are_refused_by_the_READER_too(session, seeded):
    """Written straight to the table, because that is the state a partial delete would leave."""
    collection = session.get(GenomeCollection, seeded["collection"].genome_collection_id)
    session.add(
        GenomeCollectionMembership(
            genome_collection_id=collection.genome_collection_id,
            genome_id=seeded["genome"].genome_id,
            collection_genome_ordinal=7,
        )
    )
    session.flush()
    with pytest.raises(RosterError, match="not 0"):
        genome_id_by_ordinal(session, collection.genome_collection_id)


# ── the ordering, end to end ───────────────────────────────────────────────────────────────────
def test_the_ordinal_follows_the_SORTED_vocabulary_and_not_the_file_order(session, tmp_path):
    """The parquet is written deliberately out of order; the ordinals must not inherit it."""
    species_ids = ingest_pathogen_species(session)
    session.flush()
    _stage_genome_rows(session, species_ids["ecoli"], ["SAM_C", "SAM_A", "SAM_B"])
    artifacts = _fake_universe(tmp_path, ["SAM_C", "SAM_A", "SAM_B"])
    collection_id, report = ingest_genome_collection(
        session, artifacts, pathogen_species_id=species_ids["ecoli"]
    )
    session.flush()
    assert report.genome_count == 3
    ordered = session.execute(
        select(GenomeCollectionMembership.requested_sample_id)
        .where(GenomeCollectionMembership.genome_collection_id == collection_id)
        .order_by(GenomeCollectionMembership.collection_genome_ordinal)
    ).scalars().all()
    assert ordered == ["SAM_A", "SAM_B", "SAM_C"]


def test_the_real_ecoli_roster_reproduces_meta_genomes_and_reloads_without_duplicating(
    session, ecoli_artifacts, published_ecoli_site_catalogue
):
    species_ids = ingest_pathogen_species(session)
    session.flush()
    samples, _ = read_genome_vocabulary(ecoli_artifacts)
    _stage_genome_rows(session, species_ids["ecoli"], samples)

    first, report = ingest_genome_collection(
        session, ecoli_artifacts, pathogen_species_id=species_ids["ecoli"]
    )
    session.flush()
    assert (report.genome_count, report.members_written, report.unresolved_sample_ids) == (100, 100, [])

    second, _ = ingest_genome_collection(
        session, ecoli_artifacts, pathogen_species_id=species_ids["ecoli"]
    )
    session.flush()
    assert second == first, "a re-ingest must keep the collection id — pangenomes point at it"

    ordered = session.execute(
        select(GenomeCollectionMembership.requested_sample_id)
        .where(GenomeCollectionMembership.genome_collection_id == first)
        .order_by(GenomeCollectionMembership.collection_genome_ordinal)
    ).scalars().all()
    assert len(ordered) == 100, "membership must be REPLACED wholesale, never merged"
    assert ordered == published_ecoli_site_catalogue["meta"]["genomes"]
    assert len(genome_id_by_ordinal(session, first)) == 100
