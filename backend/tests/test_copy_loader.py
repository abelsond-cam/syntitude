"""The COPY loader, tested against the REAL tables — including the four coercions that are traps.

⛔ Each of these is a value that would land in Postgres looking entirely plausible and meaning
something else: a NaN that compares equal to itself, an enum written by value instead of name, an
empty array collapsed to NULL, a numpy scalar the driver cannot adapt.
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import func, select

from syntitude_backend.ingest.staging_table_loader import copy_rows, replace_rows_for
from syntitude_backend.models.enumerations import PrevalenceBand, SampleIdentifierKind
from syntitude_backend.models.gene import Gene, GeneFunctionalAnnotation
from syntitude_backend.models.genome import Genome
from syntitude_backend.models.locus import Locus

GENE_COLUMNS = (
    "genome_id", "flat_index", "pathogen_species_id", "contig_index",
    "start_position", "end_position", "length_nt", "strand", "strand_is_observed",
    "gff_phase", "is_five_prime_partial", "gc_percent",
)


def _gene_row(genome_id, species_id, flat_index, **overrides):
    row = dict(
        genome_id=genome_id, flat_index=flat_index, pathogen_species_id=species_id,
        contig_index=0, start_position=1, end_position=300, length_nt=300,
        strand="+", strand_is_observed=True, gff_phase=0, is_five_prime_partial=False,
        gc_percent=51.5,
    )
    row.update(overrides)
    return tuple(row[name] for name in GENE_COLUMNS)


@pytest.fixture()
def clean_genes(session, _seed_ids):
    session.execute(Gene.__table__.delete())
    session.commit()
    yield
    session.execute(Gene.__table__.delete())
    session.commit()


def test_it_copies_rows_and_reports_what_it_wrote(session, _seed_ids, clean_genes):
    written = copy_rows(
        session, Gene.__table__, GENE_COLUMNS,
        (_gene_row(_seed_ids["genome"], _seed_ids["species"], i) for i in range(1_000)),
    )
    session.commit()

    assert written == 1_000
    assert session.execute(select(func.count()).select_from(Gene)).scalar_one() == 1_000


def test_a_nan_measurement_becomes_null_and_never_reaches_the_check(session, _seed_ids, clean_genes):
    """⚠ Postgres defines `NaN = NaN` as TRUE, so a NaN that got in is indistinguishable from data."""
    copy_rows(
        session, Gene.__table__, GENE_COLUMNS,
        [_gene_row(_seed_ids["genome"], _seed_ids["species"], 0, gc_percent=math.nan)],
    )
    session.commit()

    stored = session.execute(select(Gene.gc_percent)).scalar_one()
    assert stored is None


def test_an_enum_is_written_by_name_not_by_value(session, _seed_ids):
    """SQLAlchemy persists `.name`; the CHECK constraints were written against that spelling."""
    species_id = _seed_ids["species"]
    copy_rows(
        session, Genome.__table__,
        ("pathogen_species_id", "sample_id", "sample_id_kind", "strand_is_observed"),
        [(species_id, "SAMEA_COPY_TEST", SampleIdentifierKind.ASSEMBLY_STEM, False)],
    )
    session.commit()

    kind = session.execute(
        select(Genome.sample_id_kind).where(Genome.sample_id == "SAMEA_COPY_TEST")
    ).scalar_one()
    assert kind is SampleIdentifierKind.ASSEMBLY_STEM
    session.execute(Genome.__table__.delete().where(Genome.__table__.c.sample_id == "SAMEA_COPY_TEST"))
    session.commit()


def test_an_empty_array_is_not_null(session, _seed_ids):
    """⛔ `{}` is *annotated with nothing*; NULL is *not annotated*. Different claims."""
    genome_id, _ = _seed_ids["genome"], None
    session.execute(GeneFunctionalAnnotation.__table__.delete())
    copy_rows(
        session, GeneFunctionalAnnotation.__table__,
        ("genome_id", "flat_index", "gene_ontology_terms"),
        [(genome_id, 0, []), (genome_id, 1, None), (genome_id, 2, ["GO:0003677"])],
    )
    session.commit()

    stored = dict(
        session.execute(
            select(GeneFunctionalAnnotation.flat_index, GeneFunctionalAnnotation.gene_ontology_terms)
        ).all()
    )
    assert stored[0] == []
    assert stored[1] is None
    assert stored[2] == ["GO:0003677"]
    session.execute(GeneFunctionalAnnotation.__table__.delete())
    session.commit()


def test_a_numpy_scalar_is_adapted(session, _seed_ids, clean_genes):
    """`numpy.int64` has no text dumper; the failure otherwise names the driver, not the column."""
    numpy = pytest.importorskip("numpy")
    copy_rows(
        session, Gene.__table__, GENE_COLUMNS,
        [_gene_row(_seed_ids["genome"], _seed_ids["species"], numpy.int64(7),
                   start_position=numpy.int32(11), gc_percent=numpy.float32(48.25))],
    )
    session.commit()

    row = session.execute(select(Gene.flat_index, Gene.start_position)).one()
    assert row == (7, 11)


def test_a_mis_named_column_is_refused_before_a_row_is_sent(session, _seed_ids):
    with pytest.raises(KeyError) as failure:
        copy_rows(session, Gene.__table__, ("genome_id", "start"), [(1, 1)])
    assert "start" in str(failure.value)


def test_replace_refuses_an_unscoped_predicate(session, _seed_ids):
    """An unbounded `where` here is a table wipe the caller would see as a successful load."""
    with pytest.raises(ValueError, match="scoped predicate"):
        replace_rows_for(session, Gene.__table__, GENE_COLUMNS, [], where=None)


def test_replace_is_idempotent_at_its_own_scope(session, _seed_ids, clean_genes):
    """⭐ Re-running an ingest after a fix must not double the rows it already wrote."""
    genome_id, species_id = _seed_ids["genome"], _seed_ids["species"]
    rows = [_gene_row(genome_id, species_id, i) for i in range(50)]
    scope = Gene.__table__.c.genome_id == genome_id

    replace_rows_for(session, Gene.__table__, GENE_COLUMNS, rows, where=scope)
    session.commit()
    deleted, written = replace_rows_for(session, Gene.__table__, GENE_COLUMNS, rows, where=scope)
    session.commit()

    assert (deleted, written) == (50, 50)
    assert session.execute(select(func.count()).select_from(Gene)).scalar_one() == 50


def test_the_loader_issues_one_copy_statement_per_call(session, engine, _seed_ids, clean_genes):
    """⭐ The cost assertion: 5,000 rows must not be 5,000 statements."""
    from syntitude_backend.instruments.sql_cost_oracle import SqlCostOracle

    rows = [_gene_row(_seed_ids["genome"], _seed_ids["species"], i) for i in range(5_000)]
    with SqlCostOracle(engine) as report:
        copy_rows(session, Gene.__table__, GENE_COLUMNS, rows, batch_rows=1_000)
        session.commit()

    copies = [record for record in report.statements if record.category == "copy"]
    assert len(copies) == 1, report.statements


def test_a_locus_array_column_round_trips(session, _seed_ids):
    """`context_observed_member_counts` is ten integers in OFFSETS order, and order is the meaning."""
    counts = [97, 96, 95, 94, 93, 92, 91, 90, 89, 88]
    session.execute(Locus.__table__.delete())
    copy_rows(
        session, Locus.__table__,
        ("pangenome_id", "pathogen_species_id", "node_label", "catalogue_ordinal",
         "member_gene_count", "member_genome_count", "prevalence_band", "display_name",
         "display_name_source", "named_member_count", "context_observed_member_counts",
         "total_arrangement_count", "arrangement_member_gene_count"),
        [(_seed_ids["pangenome"], _seed_ids["species"], "0", 0, 99, 97,
          PrevalenceBand.CORE, "wzi", "bakta_symbol", 63, counts, 4, 99)],
    )
    session.commit()

    assert session.execute(select(Locus.context_observed_member_counts)).scalar_one() == counts
    session.execute(Locus.__table__.delete())
    session.commit()
