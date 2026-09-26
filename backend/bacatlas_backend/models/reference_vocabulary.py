"""Public reference tables the catalogue JOINS against — owned by nobody here, versioned by us.

⛔ **Not a pangenome's data, and not a generic key/value table.** A Pfam family has six specific
fields the page reads individually — the short name it is chipped with, the description a hover
shows, and the InterPro entry a reader following a domain actually wants — so a generic
`(vocabulary, key, value)` shape would flatten exactly the structure the page needs and turn every
render into six lookups. Other vocabularies get their own tables here when they earn one.

⚠ **KEGG is absent deliberately and stays absent**: its licence permits linking, not
redistribution. KEGG ids are present in `locus_annotation_entry` and never named.
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bacatlas_backend.database import Base


class PfamFamily(Base):
    """One Pfam-A family: what it is called, what it is, and where it sits in InterPro and its clan.

    Vendored from `nuna.tl.locus_browser.vendor_reference`, which is the **single reader** of
    `pfam_names.tsv.gz` — three call sites wanted it and three private gzip parsers is exactly the
    drift that lets two of them disagree about which column the clan is in.

    ⚠ **A clanless family has an empty `clan_accession`, and that is not an identity.** Only ~46 %
    of families are in a clan at all, so mapping the clanless to a shared blank would make any two
    of them look like the same superfamily — the common case, not the corner. `clan_of` in nuna maps
    a clanless family to *itself* for that reason; nothing here may collapse them.
    """

    __tablename__ = "pfam_family"
    __table_args__ = (
        # The page resolves chips by accession; a reader searching InterPro comes the other way.
        Index("ix_pfam_family__interpro_accession", "interpro_accession"),
    )

    #: `PF00126` — **version-stripped**, as `pfam_reference` strips it. An annotation carrying
    #: `PF00126.29` must be cut at the dot before it is looked up here or it silently misses.
    pfam_accession: Mapped[str] = mapped_column(String(16), primary_key=True)
    #: `Sigma70_r2` — what the chip says. Empty string where the table has none, never NULL: the
    #: vendored reader pads short rows rather than skipping them.
    short_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: ⭐ Preferred over the Pfam entry for the link: it is the integrated record, and the page a
    #: reader following a domain actually wants. Empty where there is no integrated entry.
    interpro_accession: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    interpro_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    clan_accession: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    clan_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    def __repr__(self) -> str:
        return f"<PfamFamily {self.pfam_accession} {self.short_name}>"
