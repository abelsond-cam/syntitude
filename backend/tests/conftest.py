"""Fixtures for the backend suite.

The minimal chain species → collection → model → pangenome → locus, built once per module. It
exists because the constraints worth testing are on the REAL tables: a hand-written temp table with
a lookalike CHECK proves only that Postgres can evaluate a CHECK, which was never in doubt.
"""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import syntitude_backend.models  # noqa: F401  (registers every table on the metadata)
from syntitude_backend.database import Base
from syntitude_backend.ingest.artifact_locator import CatalogueArtifacts
from syntitude_backend.ingest.published_catalogues import catalogue as published_catalogue
from syntitude_backend.models.enumerations import (
    ExclusivityForm,
    ExclusivityFormSource,
    PrevalenceBand,
    RosterLineage,
    SampleIdentifierKind,
)
from syntitude_backend.models.genome import Genome
from syntitude_backend.models.genome_collection import GenomeCollection
from syntitude_backend.models.locus import Locus
from syntitude_backend.models.nuna_model import NunaModel
from syntitude_backend.models.pangenome import Pangenome
from syntitude_backend.models.pathogen_species import PathogenSpecies

PROBE_URL = os.environ.get(
    "SYNTITUDE_PROBE_DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('USER', 'postgres')}@localhost:5432/syntitude_schema_probe",
)

#: The ten signed offsets, `0` deliberately absent.
TEN_ZEROS = [0] * 10


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(PROBE_URL, future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"probe database unavailable at {PROBE_URL}: {error}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture(scope="module")
def _seed_ids(engine):
    """Commit the shared seed ONCE per module, and hand back plain ids.

    ⚠ Ids, not ORM objects: an object created in a closed session is detached, and every attribute
    access then raises somewhere unrelated to the test that is actually failing.
    """
    with Session(engine) as session:
        ids = _build_seed(session)
        session.commit()
    return ids


@pytest.fixture()
def seeded(session, _seed_ids):
    """The shared seed, re-attached to this test's session."""
    return {
        "species": session.get(PathogenSpecies, _seed_ids["species"]),
        "genome": session.get(Genome, _seed_ids["genome"]),
        "collection": session.get(GenomeCollection, _seed_ids["collection"]),
        "model": session.get(NunaModel, _seed_ids["model"]),
        "pangenome": session.get(Pangenome, _seed_ids["pangenome"]),
    }


def _build_seed(session):
    """One species, one genome, one collection, one model, one pangenome."""
    species = PathogenSpecies(species_key="probe", scientific_name="Escherichia coli")
    session.add(species)
    session.flush()

    genome = Genome(
        pathogen_species_id=species.pathogen_species_id,
        sample_id="SAMEA0000001",
        sample_id_kind=SampleIdentifierKind.BIOSAMPLE,
        strand_is_observed=True,
    )
    collection = GenomeCollection(
        pathogen_species_id=species.pathogen_species_id,
        collection_key="probe_ecoli",
        roster_lineage=RosterLineage.PROBE_BIOSAMPLE,
        genome_count=100,
    )
    model = NunaModel(
        model_key="nuna4",
        label="nuna4_g2_0.98_3b0.5rhoPAIRMAX_step4g0.1rhoCEIL",
        exclusivity_form=ExclusivityForm.DAMPED_EXCLUSION,
    )
    session.add_all([genome, collection, model])
    session.flush()

    pangenome = Pangenome(
        run_id="probe_run_res0.1_seed0",
        ingest_generation=1,
        pathogen_species_id=species.pathogen_species_id,
        genome_collection_id=collection.genome_collection_id,
        nuna_model_id=model.nuna_model_id,
        exclusivity_form=ExclusivityForm.DAMPED_EXCLUSION,
        exclusivity_form_source=ExclusivityFormSource.RUN_MANIFEST,
        run_id_exclusivity_token="-excl",
        genome_count=100,
        gene_count=489146,
        locus_count=1,
    )
    session.add(pangenome)
    session.flush()
    return {
        "species": species.pathogen_species_id,
        "genome": genome.genome_id,
        "collection": collection.genome_collection_id,
        "model": model.nuna_model_id,
        "pangenome": pangenome.pangenome_id,
    }


def make_locus(seeded, *, ordinal=0, label="0", **overrides):
    """A minimally-valid Locus, so a test can vary exactly the column it is about."""
    fields = dict(
        pangenome_id=seeded["pangenome"].pangenome_id,
        pathogen_species_id=seeded["species"].pathogen_species_id,
        node_label=label,
        catalogue_ordinal=ordinal,
        member_gene_count=99,
        member_genome_count=97,
        prevalence_band=PrevalenceBand.CORE,
        display_name="wzi",
        display_name_source="bakta_symbol",
        named_member_count=63,
        context_observed_member_counts=TEN_ZEROS,
        total_arrangement_count=4,
    )
    fields.update(overrides)
    return Locus(**fields)


# ── the local artifact mirror ──────────────────────────────────────────────────────────────────
#: Where the cluster artifacts are mirrored on this machine. ⚠ Overridable, because a machine that
#: does not have them must SKIP rather than fail — the mirror is ~150 MB of pulled files and is not
#: a checked-in fixture.
NUNA_DATA_ROOT = Path(os.environ.get("SYNTITUDE_NUNA_DATA_ROOT", "~/developer/nuna/data")).expanduser()

#: ⭐ The SITE catalogue, not the export. `data/{species}.json` in this repo is what `render_site`
#: shipped, so it alone carries `meta.landing`, `meta.examples` and the vendored `pfam_names` —
#: `render` MUTATES the payload and the site build is the only caller that serialises afterwards.
#: The export under `data/browser/` has none of the three, which is why it cannot be this oracle.
PUBLISHED_SITE_CATALOGUE_DIR = Path(__file__).resolve().parents[2] / "data"

requires_artifacts = pytest.mark.skipif(
    not (NUNA_DATA_ROOT / "proc" / "embeddings" / "meta").is_dir(),
    reason=f"the cluster artifact mirror is not present at {NUNA_DATA_ROOT}",
)


def artifacts_for(species_key: str) -> "CatalogueArtifacts":
    """The published catalogue's artifacts, addressed from the checked-in triple — never guessed."""
    entry = published_catalogue(species_key)
    return CatalogueArtifacts(
        data_root=NUNA_DATA_ROOT,
        set_key=entry.set_key,
        model_label=entry.model_label,
        run_id=entry.run_id,
        species_key=entry.species_key,
    )


@pytest.fixture(scope="session")
def ecoli_artifacts():
    if not (NUNA_DATA_ROOT / "proc" / "embeddings" / "meta").is_dir():
        pytest.skip(f"the cluster artifact mirror is not present at {NUNA_DATA_ROOT}")
    return artifacts_for("ecoli")


@pytest.fixture(scope="session")
def published_ecoli_site_catalogue():
    """The shipped `ecoli.json`, decoded — the acceptance oracle for everything derived."""
    path = PUBLISHED_SITE_CATALOGUE_DIR / "ecoli.json"
    if not path.exists():
        pytest.skip(f"the published site catalogue is not present at {path}")
    return json.loads(path.read_text())
