"""Folding an allele-variant symbol onto its gene — the rule, and the property that keeps it safe.

⛔ **The rule is narrow on purpose**, so these tests are mostly about what it must NOT touch. A fold
that reached one symbol too far would rename a locus for a reason nobody could reconstruct, and
renaming is the expensive kind of wrong here.
"""

from __future__ import annotations

import pandas
import pytest

from syntitude_backend.ingest.allele_variant_symbols import fold_allele_variant, fold_symbol_column


# ── what it folds ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("symbol", "gene"),
    [
        # ⭐ Every tagged symbol in the two loaded catalogues, measured 2026-09-24. There are four.
        ("ompK36_T333N", "ompK36"),
        ("rpsJ_V57L", "rpsJ"),
        ("lon_P403L", "lon"),
        ("tufA_E379K", "tufA"),
    ],
)
def test_a_substitution_tagged_symbol_folds_onto_its_gene(symbol, gene):
    assert fold_allele_variant(symbol) == gene


def test_the_stem_may_carry_DIGITS_which_is_the_case_that_matters():
    """⛔ `ompK36` is the only one of the four where folding changes a name a reader would argue about.

    A stem pattern shaped like a classic three-letter symbol (`[a-z]{3}[A-Z]?`) matches `lon`, `rpsJ`
    and `tufA` and misses this one — passing three tests while failing the case it was written for.
    """
    assert fold_allele_variant("ompK36_T333N") == "ompK36"


# ── what it must not fold ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "symbol",
    [
        "ompC",  # no suffix at all
        "ompK36",  # the folded form itself — folding is idempotent
        "AAOCBP_22210",  # ⛔ a Bakta locus tag: the suffix has no leading residue letter
        "ABC_123",  # the same shape, upper case: still no residue letter
        "yfaA_B",  # no position
        "insH1_1",  # a copy index, NOT a substitution — two genes, not one allele
        "T333N",  # a substitution with no gene in front of it
        "_T333N",  # an empty stem
        "ompK36_T333",  # no substituted residue
        "ompK36_t333n",  # lower case: not the notation
    ],
)
def test_everything_else_is_returned_unchanged(symbol):
    assert fold_allele_variant(symbol) == symbol


def test_a_non_string_passes_straight_through():
    """⚠ Nulls reach this function by the million — `real_gene_names` blanks every locus tag."""
    assert fold_allele_variant(None) is None
    assert pandas.isna(fold_allele_variant(float("nan")))


# ── the property that keeps `named_member_count` out of it ────────────────────────────────────
def test_the_NULL_MASK_is_identical_before_and_after():
    """⛔⛔ The load-bearing property: folding rewrites a value and never its presence.

    `locus.named_member_count` is `notna().sum()` over this column, and it feeds the audit's
    gene-naming statistics. If a fold could turn a symbol into a null — or a null into a symbol —
    this module would be changing a graded number. It cannot, and this is the test that says so.
    """
    column = pandas.Series(["ompK36_T333N", None, "ompC", float("nan"), "lon_P403L", pandas.NA])
    folded = fold_symbol_column(column)
    assert list(folded.isna()) == list(column.isna())
    assert folded.notna().sum() == column.notna().sum() == 3


def test_folding_merges_the_split_vote_that_misnamed_kp_3878():
    """⭐ The whole point, on the real numbers: `ompC` 28, `ompK36_T333N` 26, `ompK36` 10.

    Exact-string counting names the locus `ompC` on a plurality of 28 while **36 genes say OmpK36**.
    Folding first, the same count names it `ompK36` — which is also what its modal product, its
    `best_product` and both of its major UniRef50 families already said.
    """
    column = pandas.Series(["ompC"] * 28 + ["ompK36_T333N"] * 26 + ["ompK36"] * 10)
    assert column.value_counts().idxmax() == "ompC"
    folded = fold_symbol_column(column)
    assert folded.value_counts().idxmax() == "ompK36"
    assert int(folded.value_counts()["ompK36"]) == 36
