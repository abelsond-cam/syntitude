"""The genomes a species' anchor control can offer — `meta.genomes` + `anchorSearch` + `GENOME_N`.

⭐ **An 80,000-element resident array becomes a query.** The published page shipped every accession
in `meta.genomes`, filtered it in the browser, and counted each genome's loci on first opening of the
box by walking its whole membership index. Here the filter is one statement and the counts are READ,
from `pangenome_genome_locus_count`, which ingest wrote — never aggregated per request, because the
aggregate is over ~412 M membership rows at the design target and this runs on every keystroke.

⛔ **The query means what `anchorSearch` meant** (`app.js::anchorSearch`): the query is trimmed and
upper-cased, a genome matches when its upper-cased accession CONTAINS it as a literal substring, and
an empty query matches every genome. Two details carry that exactly:

* **`strpos`, not `LIKE`.** `%` and `_` are wildcards to `LIKE` and plain characters to `indexOf`, so
  a `LIKE` needs escaping to mean the same thing (`locus_search_service` does it); `strpos` is a
  literal substring test with nothing to escape.
* **The query is upper-cased in Python, not in SQL.** Python's `str.upper` and JavaScript's
  `toUpperCase` both apply the full Unicode case mapping (`ß` → `SS`); a server-side `upper()` under a
  libc collation maps character by character and would not. Accessions are ASCII, where Postgres'
  `upper()` agrees with both — so that side stays in SQL.

⚠ **Ordered by `collection_genome_ordinal`**, the order `meta.genomes` published and the dropdown
listed. It is stored, never re-derived by sorting accessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, over, select
from sqlalchemy.orm import Session

from syntitude_backend.models.genome import Genome
from syntitude_backend.models.genome_collection import GenomeCollectionMembership
from syntitude_backend.models.pangenome import Pangenome
from syntitude_backend.models.pangenome_genome_locus_count import PangenomeGenomeLocusCount

#: What a request gets without asking. The page listed all 100; the design target is 80,000.
DEFAULT_GENOME_LIMIT = 100

#: The clamp. ⚠ A LIMIT, not a page: `truncated` says when there is more, and the reader narrows the
#: query rather than scrolling 80,000 accessions.
MAXIMUM_GENOME_LIMIT = 1000


@dataclass
class ListedGenome:
    """One genome the anchor control can offer, with both of its locus counts."""

    sample_id: str
    collection_genome_ordinal: int
    #: Distinct loci where the genome has ≥ 1 gene.
    locus_count: int
    #: Distinct loci where it sits in some arrangement — the published dropdown's "N loci".
    arrangement_locus_count: int


@dataclass
class GenomeListing:
    """The matching genomes, and enough counts that a short list is never mistaken for a whole one."""

    query: str
    genome_count: int
    #: ⛔ Matches BEFORE the limit. Without it a list cut at 100 reads as "100 genomes match".
    matched_genome_count: int
    genomes: list[ListedGenome] = field(default_factory=list)

    @property
    def truncated(self) -> bool:
        """More genomes matched than the limit let through."""
        return self.matched_genome_count > len(self.genomes)


def clamp_genome_limit(requested: int | None) -> int:
    """`limit` as asked, held to [1, `MAXIMUM_GENOME_LIMIT`]; absent means the default."""
    if requested is None:
        return DEFAULT_GENOME_LIMIT
    return max(1, min(MAXIMUM_GENOME_LIMIT, requested))


def list_genomes(session: Session, pangenome: Pangenome, *, query: str, limit: int) -> GenomeListing:
    """Every genome of the pangenome's collection whose accession contains `query` — ONE statement.

    ⭐ `count(*) OVER ()` is evaluated before `LIMIT`, so the number of matches rides on every row the
    limit keeps and the statement count does not grow with the limit, the collection or the query.
    Zero rows back means zero matched.
    """
    trimmed = (query or "").strip()
    matched = over(func.count())
    statement = (
        select(
            Genome.sample_id,
            GenomeCollectionMembership.collection_genome_ordinal,
            PangenomeGenomeLocusCount.locus_count,
            PangenomeGenomeLocusCount.arrangement_locus_count,
            matched,
        )
        .join(Genome, Genome.genome_id == PangenomeGenomeLocusCount.genome_id)
        .join(
            GenomeCollectionMembership,
            (GenomeCollectionMembership.genome_id == PangenomeGenomeLocusCount.genome_id)
            & (GenomeCollectionMembership.genome_collection_id == pangenome.genome_collection_id),
        )
        .where(PangenomeGenomeLocusCount.pangenome_id == pangenome.pangenome_id)
        .order_by(GenomeCollectionMembership.collection_genome_ordinal)
        .limit(limit)
    )
    if trimmed:
        # ⛔ Literal substring, case-folded as `anchorSearch` folds it — see the module docstring.
        statement = statement.where(func.strpos(func.upper(Genome.sample_id), trimmed.upper()) > 0)

    rows = session.execute(statement).all()
    return GenomeListing(
        query=trimmed,
        genome_count=pangenome.genome_count,
        matched_genome_count=rows[0][4] if rows else 0,
        genomes=[
            ListedGenome(
                sample_id=sample_id,
                collection_genome_ordinal=ordinal,
                locus_count=locus_count,
                arrangement_locus_count=arrangement_locus_count,
            )
            for sample_id, ordinal, locus_count, arrangement_locus_count, _ in rows
        ],
    )
