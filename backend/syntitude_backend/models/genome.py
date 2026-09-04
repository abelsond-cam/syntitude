"""Genome, its assemblies and its contigs — **model-independent** facts that outlive every run.

⛔ This is the half of the gene layer that a re-ingest must never rewrite. Coordinates are a
property of the genome; a locus is a property of the model. The split is the same one that keeps
`.nseq` and `.loci` as two files, one level up.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from syntitude_backend.database import Base
from syntitude_backend.models.enumerations import SampleIdentifierKind


class Genome(Base):
    """One assembled genome, ever. Not scoped to a collection or a model."""

    __tablename__ = "genome"
    __table_args__ = (
        UniqueConstraint("sample_id"),
        Index("ix_genome__bare_accession", "bare_accession"),
    )

    genome_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pathogen_species_id: Mapped[int] = mapped_column(
        ForeignKey("pathogen_species.pathogen_species_id"), nullable=False
    )

    #: ⭐ **The store key.** Every parquet, `.npy`, GFF and assignment file is named by this.
    #: ⚠ The parquets' own `species` column is NOT the species key: it reads `ecoli | kpneumoniae`
    #: (the only two values over all 280 genomes), while `pathogen_species.species_key` is
    #: `ecoli | kp` (`published.tsv`). A direct string join drops every Klebsiella genome silently.
    sample_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sample_id_kind: Mapped[SampleIdentifierKind] = mapped_column(nullable=False)

    #: The second key form, and ONLY for RefSeq/GenBank stems. ⚠ `GCF_000512165.1` against
    #: `GCF_000512165.1_ASM51216v1_genomic`. The tail is **not always** `_ASM…_genomic` — NCBI
    #: writes the submitter's strain name there, so `_INF156_genomic` and `_KSB2_2B_genomic` (two
    #: underscores) occur. Populated by `build_genome_set.bare_accession`, which anchors on the
    #: ACCESSION and not on the tail; an `_ASM`-only rule silently lost 27 genomes.
    #: NULL for BioSample-keyed short-read assemblies, which have one form.
    bare_accession: Mapped[str | None] = mapped_column(String(128), nullable=True)

    #: The BakRep dataset directory (`gff/<datasetID>/<BS>/`). No parquet carries it, so it is
    #: captured from the path at ingest or it is lost.
    bakrep_dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    sublineage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lincode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phylogroup: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: ⚠ NULL means "not a Klebsiella genome / flag not applicable", NOT false.
    is_kpsc_final_list: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_complete_assembly: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_hybrid_assembly: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    contig_count_with_coding_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_base_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    coding_gene_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: ⚠ Whether a `{BS}_strand.parquet` existed, or every gene was forced to `+`. Present for all
    #: 280 probe genomes (verified); absent for the entire 13,573-genome Klebsiella cohort. A forced
    #: `+` must never read as an observation, which is what this column is for.
    strand_is_observed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Genome {self.sample_id}>"


class GenomeAssembly(Base):
    """Where a genome's assembly came from — accession, source and the file we hold."""

    __tablename__ = "genome_assembly"
    __table_args__ = (UniqueConstraint("genome_id", "assembly_accession"),)

    genome_assembly_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    genome_id: Mapped[int] = mapped_column(ForeignKey("genome.genome_id", ondelete="CASCADE"), nullable=False)

    #: ⚠ Every probe assembly is an **AllTheBacteria** assembly, not an NCBI one: all 281 manifest
    #: rows read `source = atb` and `ncbi_accession` is blank on all of them. So this is nullable
    #: and its absence is a fact about the cohort, not a gap in the load.
    assembly_accession: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assembly_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assembly_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotation_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)


class GenomeContig(Base):
    """`contig_index` ↔ seqid ↔ contig name and length — the map, stored because it is measured.

    ⛔ **`contig_index` is not the contig number.** It is a position over contigs that have a CDS.
    Index 269 on SAMEA103923484 is `contig00324`. `contig_index + 1` is right for the low indices
    and silently wrong in the tail.

    ⛔ **Two GFF seqids can map to one `contig_index`, and it is not a broken join.** A short-read
    assembler emits byte-identical duplicate contigs and the extractor keeps only one, so the
    coordinate map assigns both seqids to it. That is why the map is stored as measured at ingest
    rather than re-derived per request — and why the unique constraint is on (genome, seqid) and
    NOT on (genome, contig_index).
    """

    __tablename__ = "genome_contig"
    __table_args__ = (
        UniqueConstraint("genome_id", "seqid"),
        Index("ix_genome_contig__genome_id__contig_index", "genome_id", "contig_index"),
    )

    genome_contig_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    genome_id: Mapped[int] = mapped_column(ForeignKey("genome.genome_id", ondelete="CASCADE"), nullable=False)

    #: The GFF's own column-1 identifier, e.g. `SAMEA103923484.contig00001`.
    seqid: Mapped[str] = mapped_column(String(128), nullable=False)
    contig_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    contig_name: Mapped[str] = mapped_column(String(128), nullable=False)
    length_bases: Mapped[int] = mapped_column(Integer, nullable=False)
