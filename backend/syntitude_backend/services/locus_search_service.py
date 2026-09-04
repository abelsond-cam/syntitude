r"""Search — `pg_trgm`, preserving today's EXACT substring semantics rather than approximating them.

⭐ **This is the genuine win of the rebuild.** `serving_at_scale.md` §6 flags that static prefix
buckets **lose mid-word substring** (`ligase` finds *O-antigen ligase RfaL*) and declines to choose
between them and trigram postings. Postgres removes the decision: a GIN index with `gin_trgm_ops`
accelerates `LIKE '%q%'` directly, so `app.js`'s `HAY[i].indexOf(q)` is **preserved, not
approximated**.

⛔ **A LITERAL substring match, never `%` or `similarity()`.** Those are fuzzy ranking — a different
query, returning loci that contain no such substring at all. The trigram index accelerates both, so
choosing the wrong one costs nothing and silently changes what search means.
⚠ Plain `LIKE` and not `ILIKE`, because `search_text` is stored **already lowercased** and the query
is lowercased here: on a lowercased haystack the two are equivalent and `LIKE` is the cheaper of
them. That equivalence depends on the column's contents, so it is stated here rather than assumed.

⛔⛔ **`%` and `_` MUST be escaped before interpolation.** They are LIKE wildcards and plain literals
to `indexOf`, so `ILIKE '%'||q||'%'` is **not** equivalent to today's search for a query containing
either — and both occur in real product strings (`50S ribosomal protein L7/L12`, `tRNA-modifying
GTPase`, and any query a reader pastes). Unescaped, `_` matches any character and `%` matches
anything at all, so a search for `rpl_` would return loci that do not contain `rpl_`.

⚠ **Queries of 1–2 characters cannot use a trigram index** — a trigram needs three. Those fall back
to a prefix match, and the response SAYS which mode it used rather than silently returning less.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Integer, case, func, literal, select
from sqlalchemy.orm import Session

from syntitude_backend.models.locus import Locus

#: Below this length a trigram index cannot help, so the query becomes a prefix match.
TRIGRAM_MINIMUM_LENGTH = 3

#: The escape character for LIKE metacharacters. Backslash, declared explicitly in the SQL so the
#: behaviour does not depend on `standard_conforming_strings`.
LIKE_ESCAPE = "\\"

#: How many hits a response carries. The page shows a dropdown, not a result set.
DEFAULT_RESULT_LIMIT = 25


@dataclass
class SearchHit:
    """One search result, with the rank band that ordered it."""

    node_label: str
    display_name: str
    member_gene_count: int
    member_genome_count: int
    prevalence_band: str
    #: 0 exact symbol · 1 symbol prefix · 2 symbol substring · 3 elsewhere in the haystack.
    #: The same four bands `app.js::search` uses, so the ordering a reader learned still holds.
    rank_band: int


@dataclass
class SearchResult:
    """The hits, and how they were found — so a fallback is never silent."""

    hits: list
    query: str
    mode: str
    truncated: bool


def escape_like_pattern(value: str, escape: str = LIKE_ESCAPE) -> str:
    r"""Escape `%`, `_` and the escape character itself, so a query is matched LITERALLY.

    ⛔ The escape character goes first, or escaping `%` would then escape the backslash it just
    added. Getting that order wrong turns `100%` into a pattern matching almost everything.
    """
    return (
        value.replace(escape, escape + escape)
        .replace("%", escape + "%")
        .replace("_", escape + "_")
    )


def search_loci(
    session: Session,
    *,
    pangenome_id: int,
    query: str,
    limit: int = DEFAULT_RESULT_LIMIT,
) -> SearchResult:
    """Substring search over the materialised haystack, ranked as the page ranks it."""
    cleaned = query.strip().lower()
    if not cleaned:
        return SearchResult(hits=[], query=query, mode="empty", truncated=False)

    escaped = escape_like_pattern(cleaned)
    if len(cleaned) < TRIGRAM_MINIMUM_LENGTH:
        # ⚠ Named, and returned to the caller: a 1–2 character query genuinely searches less of the
        # haystack than a longer one, and a reader is entitled to know that rather than to conclude
        # the catalogue holds nothing.
        mode = "prefix"
        pattern = f"{escaped}%"
    else:
        mode = "substring"
        pattern = f"%{escaped}%"

    # ⚠ An explicit CASE, because the four bands are a contract with the reader: the ordering a
    # reader learned from the live page has to keep holding, so it is spelled out rather than
    # arrived at arithmetically.
    symbol = func.coalesce(func.lower(Locus.bakta_gene_symbol), literal(""))
    rank_band = case(
        (symbol == cleaned, 0),
        (symbol.like(f"{escaped}%", escape=LIKE_ESCAPE), 1),
        (symbol.like(f"%{escaped}%", escape=LIKE_ESCAPE), 2),
        else_=3,
    ).cast(Integer)

    statement = (
        select(
            Locus.node_label,
            Locus.display_name,
            Locus.member_gene_count,
            Locus.member_genome_count,
            Locus.prevalence_band,
            rank_band.label("rank_band"),
        )
        .where(
            Locus.pangenome_id == pangenome_id,
            Locus.search_text.like(pattern, escape=LIKE_ESCAPE),
        )
        # `app.js`: rank band, then the larger locus first.
        .order_by(rank_band, Locus.member_gene_count.desc(), Locus.catalogue_ordinal)
        .limit(limit + 1)
    )
    rows = session.execute(statement).all()
    truncated = len(rows) > limit
    hits = [
        SearchHit(
            node_label=label,
            display_name=name,
            member_gene_count=genes,
            member_genome_count=genomes,
            prevalence_band=band.value,
            rank_band=int(band_value),
        )
        for label, name, genes, genomes, band, band_value in rows[:limit]
    ]
    return SearchResult(hits=hits, query=query, mode=mode, truncated=truncated)
