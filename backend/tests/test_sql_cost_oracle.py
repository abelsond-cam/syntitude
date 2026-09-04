"""The cost oracle has to be right about cost, which means testing it against a KNOWN N+1.

⛔ An instrument that under-counts is worse than no instrument: it converts "we did not measure
this" into "we measured this and it was fine". So the tests below drive a deliberate N+1 and assert
the oracle both counts it and *names* it in the failure.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from syntitude_backend.instruments.sql_cost_oracle import SqlCostOracle
from syntitude_backend.models.genome import Genome


def test_it_counts_statements_and_excludes_transaction_control(engine):
    with SqlCostOracle(engine) as report, engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.execute(text("SELECT 2"))
        connection.rollback()

    assert report.statement_count == 2, report.statements
    assert all(record.category == "select" for record in report.statements)


def test_an_n_plus_one_is_counted_as_n_plus_one(engine, _seed_ids):
    """The defect this instrument exists for, in its smallest honest form."""
    with SqlCostOracle(engine) as report, engine.connect() as connection:
        ids = connection.execute(select(Genome.genome_id)).scalars().all()
        for genome_id in ids:
            connection.execute(select(Genome.sample_id).where(Genome.genome_id == genome_id))
        connection.rollback()

    assert report.statement_count == 1 + len(ids)


def test_the_failure_message_names_the_repeated_statement(engine, _seed_ids):
    """A bare count sends the reader back to the code to guess. The listing is the instrument."""
    with SqlCostOracle(engine) as report, engine.connect() as connection:
        for _ in range(5):
            connection.execute(select(Genome.sample_id).where(Genome.genome_id == 1))
        connection.rollback()

    with pytest.raises(AssertionError) as failure:
        report.assert_at_most(1, what="the genome lookup")

    message = str(failure.value)
    assert "5.0× the logical minimum" in message
    assert "FROM genome" in message


def test_rowcount_of_minus_one_is_not_measured_and_never_counts_as_zero(engine):
    """⚠ `-1` is *the driver does not know*, which must not be summed as if it were 0 rows."""
    with SqlCostOracle(engine) as report, engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.rollback()

    report.statements.append(type(report.statements[0])(category="select", sql="SELECT ?", row_count=-1))
    assert report.row_count == report.statements[0].row_count


def test_the_listener_does_not_outlive_the_measurement(engine):
    """A leaked listener would silently fold one test's cost into the next one's budget."""
    with SqlCostOracle(engine) as first, engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.rollback()

    with engine.connect() as connection:
        connection.execute(text("SELECT 2"))
        connection.rollback()

    assert first.statement_count == 1


def test_a_raw_driver_statement_is_invisible_unless_it_reports_itself(engine):
    """⛔ The blind spot, pinned.

    SQLAlchemy's events fire only for statements SQLAlchemy executes. This test exists so that the
    limitation is a *documented, tested* property rather than something a future bulk path
    rediscovers as "the load appears to cost nothing".
    """
    from syntitude_backend.instruments.sql_cost_oracle import (
        driver_statements_are_visible,
        record_driver_statement,
    )

    assert driver_statements_are_visible() is False

    with SqlCostOracle(engine) as report, engine.connect() as connection:
        assert driver_statements_are_visible() is True
        raw = connection.connection.driver_connection
        with raw.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchall()
        unreported = report.statement_count
        record_driver_statement("copy", "COPY gene (...) FROM STDIN", 5_000)
        connection.rollback()

    assert unreported == 0, "a raw-driver statement was seen by the listener — update the docstring"
    assert report.statement_count == 1
    assert report.row_count == 5_000
    assert driver_statements_are_visible() is False
