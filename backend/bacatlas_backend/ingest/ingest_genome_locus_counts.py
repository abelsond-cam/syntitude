"""Each genome's two locus counts for one pangenome — written once, read on every picker keystroke.

⭐ **Counted from the rows just written, in the same transaction, not from the frames.** Both counts
are read back out of `gene_locus_membership` and `locus_arrangement.member_genome_ids` — the rows the
API serves — so the number the picker prints cannot describe a different catalogue from the one the
locus view draws, and a membership row a loader dropped cannot be counted anyway.

⚠ **O(genes), once per ingest, and that is the point.** At the 80,000-genome design target this is
one pass over ~412 M membership rows and the same number of unnested array entries — minutes, at
ingest — where the page's `genomeCounts()` was the same pass on first opening of the box and a
per-request aggregate would be it on every keystroke.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

#: ⭐ The definition of record. `pangenome_id` is the only parameter.
#:
#: ⛔ `count(DISTINCT locus_id)` on BOTH sides, never `count(*)`: a genome at ρ > 1 has two genes at
#: one locus and can occupy two of its arrangements, so a row count is the genome's gene total — a
#: plausible number a little too large, and one nothing on the page could contradict.
#:
#: ⚠ Driven from the COLLECTION, with outer joins: a genome that contributed no gene still gets a row
#: with two zeros, because the picker lists every genome it can anchor and a missing row would drop
#: one silently rather than say it is in nothing.
#:
#: ⚠ The migration that created the table carries a frozen copy of this for its backfill (a migration
#: must not import code that keeps changing); `test_genome_listing_endpoint` recomputes this against
#: the stored rows so the two cannot drift apart unseen.
GENOME_LOCUS_COUNT_SELECT = """
    SELECT member.genome_id,
           coalesce(present.locus_count, 0) AS locus_count,
           coalesce(arranged.arrangement_locus_count, 0) AS arrangement_locus_count
      FROM pangenome p
      JOIN genome_collection_membership member
        ON member.genome_collection_id = p.genome_collection_id
      LEFT JOIN (SELECT genome_id, count(DISTINCT locus_id) AS locus_count
                   FROM gene_locus_membership
                  WHERE pangenome_id = :pangenome_id
                  GROUP BY genome_id) present
        ON present.genome_id = member.genome_id
      LEFT JOIN (SELECT arranged_genome_id AS genome_id,
                        count(DISTINCT a.locus_id) AS arrangement_locus_count
                   FROM locus_arrangement a
                  CROSS JOIN LATERAL unnest(a.member_genome_ids) AS arranged_genome_id
                  WHERE a.pangenome_id = :pangenome_id
                  GROUP BY arranged_genome_id) arranged
        ON arranged.genome_id = member.genome_id
     WHERE p.pangenome_id = :pangenome_id
"""


def write_genome_locus_counts(session: Session, pangenome_id: int) -> int:
    """One row per collection genome for this pangenome, in ONE statement. Returns rows written.

    ⚠ Call it AFTER the arrangements and the gene memberships are loaded — it counts what is there.
    The caller deletes the pangenome's previous rows first (`_delete_pangenome_layer`), so a re-ingest
    replaces them wholesale like every other table in the layer.
    """
    result = session.execute(
        text(
            "INSERT INTO pangenome_genome_locus_count "
            "(pangenome_id, genome_id, locus_count, arrangement_locus_count) "
            "SELECT :pangenome_id, counted.genome_id, counted.locus_count, "
            "counted.arrangement_locus_count "
            f"FROM ({GENOME_LOCUS_COUNT_SELECT}) AS counted"
        ),
        {"pangenome_id": pangenome_id},
    )
    return result.rowcount
