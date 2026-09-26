"""Count the SQL a unit of work issues, so a cost bug fails a test instead of a server.

⛔ **WHY THIS EXISTS, AND WHY IT IS BUILT BEFORE THE SECOND ENDPOINT.** This project's own scar,
recorded in ``nuna/tests/conftest.py``: *"Fifteen of the ~24 bug fixes between 2026-08-26 and
2026-08-28 were one bug wearing different clothes — an operation that returns the right answer while
doing k times more work than it needs… Correctness had an oracle at every scale; cost had one at
none."*

An N+1 query is exactly that bug in its database costume, and it is invisible to every correctness
test: the response is byte-identical whether the locus card's twenty neighbours arrive in one
indexed fetch or in twenty round trips. It shows up only as a page that is fine at 17,531 loci and
unusable at 889,160 — by which time the shape is load-bearing in the front end too.

⭐ **Assert a ratio against a logical minimum computed from the inputs, never a recorded snapshot.**
``statements <= 4`` for one locus view, not ``statements == 11``. A snapshot has to be re-baselined
every time a fixture changes, and re-baselining is the move that blesses a regression. A ratio holds
at any catalogue size, and its failure says *"you issued 6.2× the statements you needed"* — which
names the bug rather than reporting that a number moved.

⚠ **Statements, not milliseconds.** Timing on a warm 17,531-locus fixture measures the laptop, and
the whole point is to catch at 100 genomes what would only hurt at 80,000. A statement count is
scale-free in exactly the way a duration is not.

⛔ **THE BLIND SPOT, AND WHY IT IS NAMED HERE RATHER THAN DISCOVERED LATER.** SQLAlchemy's
``after_cursor_execute`` fires only for statements SQLAlchemy itself executes. Work issued straight
against the DBAPI cursor — which is the only way to run ``COPY … FROM STDIN`` — is **invisible to
it**. The first version of this module counted zero statements for a 5,000-row bulk load and would
have reported that load as free.

That failure mode is the one an instrument must not have: it converts *"we did not measure this"*
into *"we measured this and it was fine"*. So a raw-driver path does not get to be silent — it calls
:func:`record_driver_statement` and appears in the report like anything else, and
:meth:`SqlCostReport.assert_at_most` counts it against the same budget. Anything added later that
reaches past SQLAlchemy must do the same; :func:`driver_statements_are_visible` exists so a test can
assert that it did.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass, field

from sqlalchemy import event
from sqlalchemy.engine import Engine

#: Leading keyword → category. Anything unmatched is counted under ``other``, deliberately: a
#: statement this does not recognise must still be COUNTED, or a new access path could hide in it.
_LEADING_KEYWORD = re.compile(r"^\s*(?:/\*.*?\*/\s*)*(\w+)", re.DOTALL)

_TRANSACTION_CONTROL = frozenset({"begin", "commit", "rollback", "savepoint", "release", "set", "reset"})

#: The report currently collecting, if any. A ContextVar rather than a module global so two
#: measurements cannot bleed into each other under concurrency, and so a raw-driver path can find
#: the active report without being handed it through five call frames.
_ACTIVE_REPORT: ContextVar[SqlCostReport | None] = ContextVar("active_sql_cost_report", default=None)


def record_driver_statement(category: str, sql: str, row_count: int) -> None:
    """Report work issued straight against the DBAPI cursor, which SQLAlchemy's events cannot see.

    A no-op when nothing is measuring, so production paths pay one ContextVar read.
    """
    report = _ACTIVE_REPORT.get()
    if report is not None:
        report.statements.append(StatementRecord(category=category, sql=sql, row_count=row_count))


def driver_statements_are_visible() -> bool:
    """Whether a raw-driver path would currently be recorded — i.e. whether a measurement is open."""
    return _ACTIVE_REPORT.get() is not None


@dataclass
class StatementRecord:
    """One statement, as issued."""

    category: str
    sql: str
    row_count: int

    def summary(self, width: int = 120) -> str:
        """One line naming the statement, whitespace-collapsed and clipped for a failure message."""
        collapsed = " ".join(self.sql.split())
        clipped = collapsed if len(collapsed) <= width else collapsed[: width - 1] + "…"
        return f"[{self.category}] rows={self.row_count:>7} {clipped}"


@dataclass
class SqlCostReport:
    """What one unit of work actually cost the database.

    ⚠ ``statement_count`` deliberately EXCLUDES transaction control (``BEGIN``/``COMMIT``/``SET``).
    Those are issued by the pool and the session lifecycle, not by the query the test is about, and
    counting them makes every bound depend on how the fixture opened its session.
    """

    statements: list[StatementRecord] = field(default_factory=list)
    transaction_control_count: int = 0

    @property
    def statement_count(self) -> int:
        """Statements issued, EXCLUDING transaction control — see the class docstring."""
        return len(self.statements)

    @property
    def row_count(self) -> int:
        """Rows the server handed back. ⚠ ``-1`` (unknown) contributes 0, never −1."""
        return sum(record.row_count for record in self.statements if record.row_count > 0)

    def of_category(self, category: str) -> list[StatementRecord]:
        """Every statement of one category, e.g. ``copy`` or ``select``."""
        return [record for record in self.statements if record.category == category]

    def assert_at_most(self, statement_budget: int, *, what: str) -> None:
        """Fail with the statements themselves, not just the count.

        ⛔ The message prints every statement issued. A bare ``11 != 4`` sends the reader back to
        the code to guess which access path repeated; the list names it on the spot, which is the
        difference between an instrument and an assertion.
        """
        if self.statement_count <= statement_budget:
            return
        ratio = self.statement_count / statement_budget if statement_budget else float("inf")
        listing = "\n  ".join(record.summary() for record in self.statements)
        raise AssertionError(
            f"{what} issued {self.statement_count} statements against a budget of {statement_budget} "
            f"({ratio:.1f}× the logical minimum). The statements, in order:\n  {listing}"
        )

    def assert_rows_at_most(self, row_budget: int, *, what: str) -> None:
        """The other half: a single statement can be the whole cost bug on its own."""
        if self.row_count <= row_budget:
            return
        ratio = self.row_count / row_budget if row_budget else float("inf")
        listing = "\n  ".join(record.summary() for record in self.statements)
        raise AssertionError(
            f"{what} returned {self.row_count:,} rows against a budget of {row_budget:,} "
            f"({ratio:.1f}× the logical minimum). The statements, in order:\n  {listing}"
        )

    def __str__(self) -> str:
        return f"<SqlCostReport {self.statement_count} statements, {self.row_count:,} rows>"


def _categorise(sql: str) -> str:
    match = _LEADING_KEYWORD.match(sql)
    return match.group(1).lower() if match else "other"


class SqlCostOracle:
    """Attach to an engine, count everything, detach.

    Used as a context manager so the listeners cannot outlive the measurement — a leaked listener
    would silently make every later test's counts include the earlier one's.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self.report = SqlCostReport()

    def __enter__(self) -> SqlCostReport:
        event.listen(self._engine, "after_cursor_execute", self._after_cursor_execute)
        self._token = _ACTIVE_REPORT.set(self.report)
        return self.report

    def __exit__(self, *_exc_info) -> None:
        _ACTIVE_REPORT.reset(self._token)
        event.remove(self._engine, "after_cursor_execute", self._after_cursor_execute)

    def _after_cursor_execute(self, _conn, cursor, statement, _parameters, _context, executemany) -> None:
        category = _categorise(statement)
        if category in _TRANSACTION_CONTROL:
            self.report.transaction_control_count += 1
            return
        # ⚠ `executemany` is ONE round trip in psycopg3's pipeline but N statements' worth of work,
        # and a loader that used it where COPY belongs is exactly a cost bug. Counted as one
        # statement and flagged in the category, so a budget of 1 cannot hide a batch of 100,000.
        self.report.statements.append(
            StatementRecord(
                category=f"{category}:many" if executemany else category,
                sql=statement,
                row_count=_row_count(cursor),
            )
        )


def _row_count(cursor) -> int:
    """``cursor.rowcount``, defensively.

    ⚠ It is ``-1`` for a statement whose row count the driver does not know, and that is *not
    measured* rather than *zero rows* — so it is carried through as ``-1`` and excluded from the
    sum rather than being counted as 0, which would understate a real cost.
    """
    try:
        count = cursor.rowcount
    except Exception:  # noqa: BLE001 — a driver that will not answer must not break the measurement
        return -1
    return int(count) if count is not None else -1
