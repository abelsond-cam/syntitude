r"""Folding an allele-variant symbol onto the gene it is an allele OF — `ompK36_T333N` → `ompK36`.

⭐ **A locus is named for its commonest gene symbol, counted as an EXACT STRING.** Bakta emits a
substitution-tagged symbol for some alleles, and the tagged form is a different string from the
untagged one, so the two split one gene's vote between them. Measured on kp locus **3878**: `ompC`
28 genes, `ompK36_T333N` 26, `ompK36` 10 — the locus was named `ompC` on a plurality of 28 while
**36 genes said OmpK36**, which is the same protein under the *Klebsiella* name. Its modal product
(`OmpK36`), its `best_product` (*outer membrane porin OmpK36*) and both of its major UniRef50
families' modal symbols all said OmpK36; only the split vote did not.

⛔ **The suffix is what is matched, never the stem.** The four tagged symbols in the two loaded
catalogues are `rpsJ_V57L`, `lon_P403L`, `ompK36_T333N` and `tufA_E379K` — stems `rpsJ`, `lon`,
`tufA` and **`ompK36`**. A stem pattern shaped like a classic three-letter symbol (`[a-z]{3}[A-Z]?`)
matches the first three and misses the fourth, which is the only one where folding changes a name a
reader would argue about. So the pattern anchors on the substitution — one residue, a position, one
residue — and lets the stem be any symbol.

⚠ **It cannot match a Bakta locus tag** (`AAOCBP_22210`): the suffix must begin with a letter, and a
tag's does not. `real_gene_names` blanks those upstream in any case; this is the second lock, not
the first.

⛔ **Scope, exactly: the CATALOGUE's symbol, and nothing else.**

* `gene.bakta_gene_symbol` — the per-gene row the Sequence and arrangement views read — keeps the
  **raw** `ompK36_T333N`. The allele is a fact about one gene, and folding it there would delete
  data rather than summarise it. The fold belongs where genes are counted into a *locus*.
* `locus.named_member_count` **cannot move**, here or ever: folding rewrites a symbol's value and
  never its presence, so the count of genes carrying any symbol is identical before and after. That
  is what keeps this out of every graded statistic — `nuna`'s audit reads its own artifacts and
  never this module.
* Nothing in `nuna` changes. The gene-naming-gain statistic and the UniRef50-vs-gene-name
  fragmentation analysis go on counting exact strings, because they are measuring what Bakta said.

⚠ **The folded symbol is what the cross-tab and the locus symbol list then report**, so kp 3878's
card reads `ompK36 36 · ompC 28` rather than showing a name whose own count is smaller than a name
beneath it — which is the confusion this fold exists to end, re-created one row lower.
"""

from __future__ import annotations

import re

#: One amino-acid substitution appended to a gene symbol: `_` then residue, position, residue.
#: ⚠ `re.ASCII` deliberately — `\d` must not match a Unicode digit in an annotation we did not write.
ALLELE_VARIANT_SYMBOL = re.compile(r"^(?P<gene>[A-Za-z][A-Za-z0-9]*)_[A-Z]\d+[A-Z]$", re.ASCII)


def fold_allele_variant(symbol: object) -> object:
    """`ompK36_T333N` → `ompK36`; anything else unchanged, including `None` and every non-string."""
    if not isinstance(symbol, str):
        return symbol
    match = ALLELE_VARIANT_SYMBOL.match(symbol)
    return match.group("gene") if match else symbol


def fold_symbol_column(column):
    """A pandas symbol column with every allele variant folded onto its gene, nulls preserved.

    ⚠ Null-preserving by construction: `fold_allele_variant` returns a non-string unchanged, so
    `NaN` and `pd.NA` pass straight through and the column's null mask — which
    `named_member_count` is computed from — is identical before and after.
    """
    return column.map(fold_allele_variant)
