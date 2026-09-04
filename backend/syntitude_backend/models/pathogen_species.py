"""The species registry, and the pointer that says which pangenome each one currently serves."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base


class PathogenSpecies(Base):
    """One organism the browser publishes. Klebsiella, E. coli, M. tuberculosis, P. aeruginosa …"""

    __tablename__ = "pathogen_species"
    __table_args__ = (UniqueConstraint("species_key"),)

    pathogen_species_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)

    #: The short key the URL and `published.tsv` use: `ecoli`, `kp`, `mtb`.
    species_key: Mapped[str] = mapped_column(String(32), nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ncbi_taxonomy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⭐ The catalogue this species currently serves. Ingest builds a new pangenome alongside the
    #: live one, verifies it, and flips this pointer in a single transaction — which is what makes
    #: republishing atomic, and rollback one UPDATE. The FK is DEFERRABLE so the flip and the
    #: partition attach can share a transaction.
    published_pangenome_id: Mapped[int | None] = mapped_column(
        ForeignKey("pangenome.pangenome_id", deferrable=True, initially="DEFERRED", use_alter=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<PathogenSpecies {self.species_key} ({self.scientific_name})>"
