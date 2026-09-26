"""Load the public reference vocabularies the catalogue joins against.

⛔ **Global, not per pangenome.** A Pfam family is the same family in every species and every model,
so this runs once and is idempotent — nothing here is keyed by `pangenome_id`, and re-running it
after a new catalogue lands is a no-op rather than a duplicate.

⚠ **Read through `nuna.tl.locus_browser.vendor_reference`, never by parsing the gzip here.** That
module is deliberately the single reader of `pfam_names.tsv.gz`: three call sites wanted the table
and three private parsers is exactly the drift that lets two of them disagree about which column the
clan is in. Ingest becomes a fourth reader only through the same door.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bacatlas_backend.models.reference_vocabulary import PfamFamily

#: ⛔ The vendored table's field name → our column. Read POSITIONALLY would be a silent
#: transposition waiting to happen — `clan` and `clan_id` are adjacent, one is an accession and the
#: other a readable id, and swapping them produces a page that looks entirely plausible. The
#: positions are taken from `vendor_reference.FIELDS` at load time, so a reordered table follows.
PFAM_COLUMN_FOR_FIELD = {
    "short_name": "short_name",
    "description": "description",
    "interpro": "interpro_accession",
    "interpro_name": "interpro_name",
    "clan": "clan_accession",
    "clan_id": "clan_name",
}

#: Every column the upsert writes — the mapping's values, in one place, so the SET clause below and
#: the row builder cannot drift apart.
PFAM_COLUMNS = tuple(PFAM_COLUMN_FOR_FIELD.values())


@dataclass(frozen=True)
class VocabularyReport:
    """What was loaded, for the reconciliation the CLI prints."""

    pfam_families_read: int
    pfam_families_in_table: int
    #: ⚠ Fields named above that the vendored table no longer has — reported rather than swallowed,
    #: because a column that quietly becomes empty everywhere reads as "Pfam has no clans".
    unmapped_fields: tuple[str, ...] = ()

    def render(self) -> str:
        """One line for the ingest report, naming any Pfam field the vendored table did not map."""
        line = (
            f"pfam reference: {self.pfam_families_read:,} families read, "
            f"{self.pfam_families_in_table:,} in the table"
        )
        if self.unmapped_fields:
            line += f" — ⚠ absent from the vendored table: {', '.join(self.unmapped_fields)}"
        return line


def load_pfam_reference(session: Session) -> VocabularyReport:
    """Upsert every Pfam-A family from the vendored reference.

    Returns counts rather than raising on an absent table: the reference is **optional everywhere**
    in nuna — the page falls back to bare accessions and the audit's clan map falls back to identity
    — so an absent table must degrade the chips, not fail the load. ⚠ It still reports zero, so a
    silently missing reference is visible in the run output rather than inferred from blank chips
    three screens later.
    """
    from nuna.tl.locus_browser.vendor_reference import FIELDS, pfam_reference

    # ⛔ Resolve each field's POSITION from nuna's own FIELDS tuple, by name. A field nuna has
    # dropped simply yields an empty column; one it has added is ignored until named above.
    position_of = {field: FIELDS.index(field) for field in PFAM_COLUMN_FOR_FIELD if field in FIELDS}
    missing = sorted(set(PFAM_COLUMN_FOR_FIELD) - set(position_of))

    reference = pfam_reference()
    rows = [
        {
            "pfam_accession": accession,
            # Padded by the reader, so a short row degrades to empty strings rather than raising.
            **{
                column: _text(fields, position_of.get(field, -1))
                for field, column in PFAM_COLUMN_FOR_FIELD.items()
            },
        }
        for accession, fields in reference.items()
    ]

    if rows:
        for start in range(0, len(rows), 5_000):
            batch = rows[start : start + 5_000]
            statement = insert(PfamFamily).values(batch)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[PfamFamily.pfam_accession],
                    set_={column: statement.excluded[column] for column in PFAM_COLUMNS},
                )
            )

    in_table = session.execute(select(func.count()).select_from(PfamFamily)).scalar_one()
    return VocabularyReport(
        pfam_families_read=len(rows),
        pfam_families_in_table=int(in_table),
        unmapped_fields=tuple(missing),
    )


def _text(fields: tuple[str, ...], index: int) -> str:
    """One field, as text, tolerating an absent field (`-1`) or a row padded shorter than expected."""
    return "" if index < 0 or index >= len(fields) else (fields[index] or "")
