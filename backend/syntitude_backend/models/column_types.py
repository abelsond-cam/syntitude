"""Shared column helpers — the two that encode a trap, and nothing else.

Kept separate from the models so each rule is stated once and cited many times, rather than
re-typed and eventually re-typed wrong.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column


def measurement() -> Mapped[float | None]:
    """A float that may be **not measured**.

    ⛔ **NULL means not measured; 0.0 means measured zero.** They are different findings and the
    payload has always kept them apart — floats are ``null`` where absent, *never* ``0.0``, *"which
    would read as a measurement"*. ``u50_impurity`` is NULL below 5 labelled members; the seqid
    columns are NULL under ``--skip-seqid-to-medoid``.

    Pair every one of these with :func:`nan_guards` in the table's ``__table_args__``.
    """
    return mapped_column(Float, nullable=True)


def nan_guards(*column_names: str) -> tuple[CheckConstraint, ...]:
    """``CHECK`` constraints forbidding NaN in each named column.

    ⚠ The test is ``<> 'NaN'`` and **not** ``col = col``, because **Postgres defines ``NaN = NaN``
    as TRUE** so that float columns can be indexed and sorted. The obvious IEEE-754
    self-inequality check silently passes every NaN — which is the failure this guard exists to
    catch, so getting the guard itself wrong would be quietly perfect.
    """
    return tuple(
        CheckConstraint(
            f"{name} IS NULL OR {name} <> 'NaN'::double precision",
            name=f"{name}_is_not_nan",
        )
        for name in column_names
    )


def nan_to_none(value) -> float | None:
    """Coerce a NaN to ``None`` at the ingest boundary, so the CHECK never has to fire.

    The constraint is the backstop; this is the intent. A NaN reaching the database means an ingest
    path forgot to call this, and the write then fails loudly on the row that carried it — which is
    the right outcome, but a slower one to diagnose than never sending it.
    """
    if value is None:
        return None
    number = float(value)
    return None if number != number else number
