"""``StringPool`` must be indistinguishable from ``export_payload._Intern``, quirks and all.

⛔ Every test here compares against the REAL class rather than against a description of it. A
re-implementation checked against its own docstring proves nothing; this project's payloads were
interned by `_Intern`, so `_Intern` is the oracle.
"""

from __future__ import annotations

import math

import pytest

from syntitude_backend.instruments.payload_string_pool import ABSENT, StringPool


@pytest.fixture()
def reference():
    from nuna.tl.locus_browser.export_payload import _Intern

    return _Intern()


def _agree(pool: StringPool, intern, values) -> None:
    assert [pool.index(v) for v in values] == [intern.idx(v) for v in values]
    assert pool.values == intern.values


def test_it_matches_Intern_on_ordinary_strings_including_repeats(reference):
    _agree(StringPool(), reference, ["fimA", "lacZ", "fimA", "ompA", "lacZ", "fimA"])


def test_None_and_non_finite_floats_are_ABSENT_and_never_enter_the_table(reference):
    pool = StringPool()
    _agree(pool, reference, [None, float("nan"), float("inf"), -float("inf"), None])
    assert pool.values == []
    assert pool.index(None) == ABSENT


def test_a_measured_zero_is_a_VALUE_and_an_empty_string_is_a_VALUE(reference):
    """⚠ The absence rule catches ``None`` and NaN only. ``0.0`` and ``""`` are real strings."""
    pool = StringPool()
    _agree(pool, reference, [0.0, "", "0.0"])
    # ⛔ `str(0.0)` is `"0.0"`, so the float and the string are ONE entry — the coercion quirk.
    assert pool.values == ["0.0", ""]


def test_str_coercion_COLLIDES_an_int_with_its_string_and_that_is_the_published_behaviour(reference):
    """⛔ Not a bug to fix. 256 published catalogues were interned this way."""
    pool = StringPool()
    _agree(pool, reference, [5, "5", 5.0])
    assert pool.values == ["5", "5.0"]


def test_a_numpy_float32_nan_is_INTERNED_as_the_string_nan_and_a_float64_nan_is_not(reference):
    """⚠ The quirk that would differ by exactly one string and say nothing about why.

    ``np.float64`` subclasses ``float`` so the non-finite test catches it; ``np.float32`` does not.
    """
    np = pytest.importorskip("numpy")
    pool = StringPool()
    _agree(pool, reference, [np.float64("nan"), np.float32("nan")])
    assert pool.values == ["nan"], "float32 NaN must intern; float64 NaN must not"


def test_pandas_NA_interns_as_its_repr_because_it_is_neither_None_nor_a_float(reference):
    pd = pytest.importorskip("pandas")
    pool = StringPool()
    _agree(pool, reference, [pd.NA])
    assert pool.values == ["<NA>"]


def test_first_use_assigns_the_index_which_is_why_walk_ORDER_is_the_whole_problem(reference):
    """⭐ The property the serialiser rests on: index == position of first use, nothing else."""
    pool, other = StringPool(), StringPool()
    forwards = ["a", "b", "c"]
    assert pool.indices(forwards) == [0, 1, 2]
    assert other.indices(reversed(forwards)) == [0, 1, 2]
    # Same set, same indices, DIFFERENT tables — which is exactly the failure mode being guarded.
    assert pool.values != other.values


def test_indices_interns_left_to_right(reference):
    pool = StringPool()
    assert pool.indices(["z", "y", "z"]) == [0, 1, 0]
    assert pool.indices([None, "x"]) == [ABSENT, 2]
    assert len(pool) == 3


def test_math_isfinite_and_numpy_isfinite_agree_on_every_value_Intern_can_see():
    """⚠ `_Intern` uses `np.isfinite`; this uses `math.isfinite`. They must not diverge on floats."""
    np = pytest.importorskip("numpy")
    for value in (0.0, -0.0, 1e308, -1e308, float("nan"), float("inf"), -float("inf"), 1.5):
        assert math.isfinite(value) == bool(np.isfinite(value))
