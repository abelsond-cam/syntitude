r"""What a locus is CALLED and what it is DESCRIBED as — `app.js`'s rules, moved to ingest.

⭐ **This is the fan-out fix.** `displayOf` falls through the modal Bakta symbol → the locus's *whole*
Pfam list plus the Pfam name table → its *whole* product list. Rendering one locus touches a median
15–19 other loci and up to 303, because a neighbour's NAME is that transitive read. Computed once
into a NOT NULL column, the fan-out becomes `WHERE locus_id = ANY($1)` over ~20 ids.

⛔ **Never let an inferred name reach a graded statistic.** `app.js` says it in as many words:
*"NEVER let this reach n_named or any graded statistic — it is a display fallback, not an
annotation."* `named_member_count` and `bakta_gene_symbol` come from the assignment's own symbols and
are untouched by anything here.

⚠ **Three regex fidelity notes, because JS and Python `re` are not the same engine.**

1. **`re.ASCII` on every `\\b` pattern.** JavaScript's `\\b` is ASCII-only (`\\w` is `[A-Za-z0-9_]`);
   Python's is Unicode-aware by default. A Bakta product carrying an accented character would put a
   word boundary in a different place, and the swap guard would admit a candidate the page rejects.
2. **`fullmatch` where the JS pattern is anchored `^…$`.** `re.match` alone would accept a prefix.
3. **`re.escape` for the symbol**, which is a superset of the JS escape class and never a subset.

⚠ **The share denominator is the LISTED products, not the locus.** `bestProduct` sums `p[j].n` over
the entries the payload ships — capped at `TOP_PRODUCTS = 6` — so a locus with a long tail has a
denominator smaller than its member count and its 10 % floor is correspondingly easier to clear.
That is the published behaviour; computing the share against `member_gene_count` would silently
raise the bar and change what the card says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: `app.js::GENE_SHAPE` — the shape a Pfam short name's last token must have to be read as a symbol.
GENE_SHAPE = re.compile(r"[A-Z][a-z]{2}[A-Z0-9]?", re.ASCII)

#: `app.js::VAGUE`. A candidate matching this *"says less than almost anything, so it may never WIN a
#: swap"*. ⛔ Deliberately NOT applied to the modal product — replacing a vague modal with something
#: specific is the entire point of the swap.
VAGUE = re.compile(
    r"^(hypothetical|uncharacteri[sz]ed|putative|conserved|predicted)?\s*"
    r"(protein|membrane protein|lipoprotein|exported protein|secreted protein)"
    r"(\s+[A-Za-z]{3}[A-Za-z0-9]*)?$",
    re.IGNORECASE | re.ASCII,
)

#: `app.js::inferredName`'s product pattern — a symbol named right before `family` or `-like`.
PRODUCT_SYMBOL = re.compile(r"\b([A-Z][a-z]{2}[A-Z0-9]?)\b(?=\s+family\b|-like\b)", re.ASCII)

#: The minimum share of the LISTED product counts a candidate must hold to be allowed to win.
PRODUCT_SWAP_MINIMUM_SHARE = 0.1

#: `locus.display_name_source`'s vocabulary — so the page can say WHY it calls a locus what it does.
SOURCE_BAKTA_SYMBOL = "bakta_symbol"
SOURCE_PFAM_ARCHITECTURE = "pfam_architecture"
SOURCE_PRODUCT = "product"
SOURCE_LABEL = "label"


@dataclass(frozen=True)
class DisplayName:
    """What to call a locus, and on what evidence."""

    name: str
    source: str
    source_accession: str | None = None


def sole_architecture(pfam_entries: list[tuple[str, int]], pfam_names: dict) -> str | None:
    """`app.js::soleArch` — the commonest architecture's accession, but only if it has exactly one.

    ⚠ *Sole* refers to the architecture having a single accession, not to the locus having a single
    architecture. A two-domain architecture names no gene, so it is not a source for a symbol.
    """
    if not pfam_entries:
        return None
    # The list is already rank-ordered by count descending, and `app.js` keeps the first on a tie
    # (its loop advances only on a strict `>`), so rank 0 IS the answer.
    label = str(pfam_entries[0][0])
    accessions = label.split(",")
    if len(accessions) != 1:
        return None
    return accessions[0] if accessions[0] in pfam_names else None


def infer_name(
    pfam_entries: list[tuple[str, int]],
    product_entries: list[tuple[str, int]],
    pfam_names: dict,
) -> DisplayName | None:
    """`app.js::inferredName` — a gene name for a locus Bakta never named, or `None`.

    Two levels, in order. **Level one needs `pfam_names`**, which is attached at RENDER time and is
    NOT in the exported payload: skipping it silently demotes 370 *E. coli* loci to `locus <label>`,
    which looks like a data gap rather than a missing lookup table.
    """
    accession = sole_architecture(pfam_entries, pfam_names)
    if accession:
        short_name = str(pfam_names[accession][0])
        token = short_name.split("_")[-1]
        if GENE_SHAPE.fullmatch(token):
            return DisplayName(token, SOURCE_PFAM_ARCHITECTURE, accession)
    if product_entries:
        match = PRODUCT_SYMBOL.search(str(product_entries[0][0]))
        if match:
            return DisplayName(match.group(1), SOURCE_PRODUCT, None)
    return None


def display_name(
    node_label: str,
    modal_symbol: str | None,
    pfam_entries: list[tuple[str, int]],
    product_entries: list[tuple[str, int]],
    pfam_names: dict,
) -> DisplayName:
    """`app.js::displayOf` — symbol, else inferred, else `locus <label>`. Never NULL."""
    if modal_symbol:
        return DisplayName(str(modal_symbol), SOURCE_BAKTA_SYMBOL, None)
    inferred = infer_name(pfam_entries, product_entries, pfam_names)
    if inferred is not None:
        return inferred
    return DisplayName(f"locus {node_label}", SOURCE_LABEL, None)


def best_product(
    modal_symbol: str | None, product_entries: list[tuple[str, int]]
) -> str | None:
    """`app.js::bestProduct` — the most SPECIFIC product, not the commonest.

    ⛔ **Not `products[0]`.** At `rfaL` the modal is *"Ligase"* while the same locus also holds
    *"O-antigen ligase RfaL"*. A candidate may win only if it **extends** the modal string or
    **names this locus's own symbol** on a word boundary the modal does not — either way it cannot
    become a different protein, which plain "longest wins" did (`araB` matched inside *"L-arabinose
    isomerase"*).
    """
    if not product_entries:
        return None
    modal = str(product_entries[0][0])
    total = sum(int(count) for _, count in product_entries)
    symbol_pattern = (
        re.compile(rf"\b{re.escape(str(modal_symbol))}\b", re.IGNORECASE | re.ASCII)
        if modal_symbol
        else None
    )
    modal_lower = modal.lower()
    best, best_extends = None, False
    for value, count in product_entries:
        candidate = str(value)
        if candidate.lower() == modal_lower:
            continue  # case-only churn
        if total and count / total < PRODUCT_SWAP_MINIMUM_SHARE:
            continue
        if VAGUE.fullmatch(candidate.strip()):
            continue  # never swap INTO a vague product
        extends = modal_lower in candidate.lower()
        names = bool(
            symbol_pattern
            and symbol_pattern.search(candidate)
            and not symbol_pattern.search(modal)
        )
        if not extends and not names:
            continue
        if (
            best is None
            or (extends and not best_extends)
            or (extends == best_extends and len(candidate) > len(best))
        ):
            best, best_extends = candidate, extends
    return best or modal


def search_text(
    node_label: str,
    modal_symbol: str | None,
    product_entries: list[tuple[str, int]],
    uniref50_accessions: list[str],
) -> str:
    """`app.js::HAY` — symbol, label, every listed product and every listed UniRef50, lowercased.

    ⛔ **Pfam, COG, GO, EC and KEGG are deliberately absent**, because that is what the page searches
    today. Adding them is a product change and not an implementation detail: a query for `PF00593`
    would start matching, which is either an improvement or a surprise, and it is not this port's
    call to make.

    ⚠ The API must escape `%` and `_` before interpolating a query into `ILIKE '%'||q||'%'`. They
    are LIKE wildcards and plain literals to `indexOf`, so the two are **not** equivalent for a
    query containing either — and product strings contain both.
    """
    parts = [
        str(modal_symbol or ""),
        str(node_label),
        " ".join(str(value) for value, _ in product_entries),
        " ".join(str(accession) for accession in uniref50_accessions),
    ]
    return " ".join(parts).lower()
