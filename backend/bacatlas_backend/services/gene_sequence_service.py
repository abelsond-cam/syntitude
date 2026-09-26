"""One genome's gene(s) at one locus — DNA, flanks and protein, read from the original GFF.

⭐ **The database holds no bases, and that is the design.** `.nseq` — a custom 8-byte-magic,
2-bit-packed binary with its own schema doc, its own build job and 290 MB of derived files — existed
for exactly one reason: GitHub Pages applies `Range` to the *compressed* stream, so byte offsets
return plausible wrong bytes with a 206 and no error, and the browser therefore had to fetch whole
files and decode DNA itself. **A server has no such constraint.** So the format is retired rather
than ported, and a gene's nucleotides are sliced from the file Bakta actually wrote.

⚠ **Parsed on demand, cached per process.** A gzipped bacterial GFF with its FASTA block is ~1.5–3
MB and parses in tens of milliseconds — against a tab the reader has to click. The cache holds the
contig sequences only, not the CDS features: the features are already in the database, and keeping
them would double the footprint of the one thing here that is measured in megabytes.

⛔ **The GFF is opened by a path built from `bakrep_dataset_id`**, which no parquet carries and which
is captured from the directory at ingest. A genome missing it cannot be read at all, and this says
so rather than constructing a path that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from syntitude_backend.gff.gene_sequence_reader import GeneSequenceView, read_gene_sequence
from syntitude_backend.gff.gff_cds_parser import parse_genome_annotation
from syntitude_backend.models.gene import Gene, GeneLocusMembership
from syntitude_backend.models.genome import Genome, GenomeContig
from syntitude_backend.models.locus import Locus

#: How many genomes' contig sequences to keep parsed. ⚠ A bacterial genome is ~5 MB as a Python
#: string, so this is a memory bound in the tens of MB per worker process — deliberately small,
#: because the tab is a click and not a hot path, and a reader walking a track hits ONE genome.
PARSED_GENOME_CACHE_SIZE = 4

#: Bases either side of the gene. The published page's own window.
FLANK_LENGTH = 100


class SequenceUnavailable(LookupError):
    """The gene exists but its bases cannot be read — and the reason is always named.

    ⛔ Never conflated with "this genome has no gene here", which is an ANSWER. `app.js:4604`: *"a
    sequence panel that fails silently is one a reader will read as 'this genome has nothing here',
    which is a different claim and a false one."*
    """


@dataclass(frozen=True)
class GeneSequenceRow:
    """One gene copy, with everything the tab prints about where it came from."""

    #: ⭐ ρ > 1 puts one genome in a locus twice, so a copy is `n of m` and the page says so.
    copy_ordinal: int
    copy_count: int
    flat_index: int
    #: ⛔ The contig's NAME, never `contig_index + 1` — the index enumerates contigs that HAVE a
    #: CDS, so index 269 is `contig00324` on SAMEA103923484.
    contig_name: str
    seqid: str
    start_position: int
    end_position: int
    strand: str
    strand_is_observed: bool
    gff_phase: int
    is_five_prime_partial: bool
    length_nt: int
    #: What the database stored at ingest, so the page can show it without opening a file — and so a
    #: divergence from the freshly-sliced sequence is visible rather than assumed away.
    stored_protein_length_aa: int | None
    stored_gc_percent: float | None
    bakta_gene_symbol: str | None
    bakta_product: str | None
    locus_tag: str | None
    sequence: GeneSequenceView


@lru_cache(maxsize=PARSED_GENOME_CACHE_SIZE)
def _contig_sequences(path_text: str) -> dict[str, str]:
    """Every contig's bases, by seqid. Cached on the PATH, which is immutable for a build."""
    path = Path(path_text)
    if not path.exists():
        raise SequenceUnavailable(f"the annotation file for this genome is not on this server ({path.name})")
    parsed = parse_genome_annotation(path, want_sequence=True)
    if not parsed.carries_sequence:
        # ⚠ Checked rather than assumed. All 280 probe GFFs carry a `##FASTA` block (measured
        # 2026-09-04), and one that does not must fail with a sentence rather than a KeyError.
        raise SequenceUnavailable(f"{path.name} carries no ##FASTA block, so it holds no bases")
    return parsed.contig_sequences


def clear_parsed_genome_cache() -> None:
    """Drop the parsed genomes. For tests, and for a process that wants its memory back."""
    _contig_sequences.cache_clear()


def load_gene_sequences(
    session: Session,
    *,
    pangenome_id: int,
    node_label: str,
    sample_id: str,
    gff_root: Path,
    flank_length: int = FLANK_LENGTH,
) -> list[GeneSequenceRow]:
    """Every copy this genome has at this locus, in genome order.

    ⛔ Returns an EMPTY LIST where the genome simply has no gene here — an answer, and the caller
    renders it as one. It RAISES `SequenceUnavailable` only where a gene exists and its bases could
    not be read, which is a different thing and must read differently on the page.

    ⚠ **One statement**, then one file. The join reaches `genome_contig` for the seqid rather than
    deriving it, because two GFF seqids can map to one `contig_index` — a short-read assembler emits
    byte-identical duplicate contigs and the extractor keeps only one — so the map is stored as
    measured at ingest and never re-derived per request.
    """
    rows = session.execute(
        select(
            Gene.flat_index,
            Gene.start_position,
            Gene.end_position,
            Gene.strand,
            Gene.strand_is_observed,
            Gene.gff_phase,
            Gene.is_five_prime_partial,
            Gene.length_nt,
            Gene.protein_length_aa,
            Gene.gc_percent,
            Gene.bakta_gene_symbol,
            Gene.bakta_product,
            Gene.locus_tag,
            GenomeContig.seqid,
            GenomeContig.contig_name,
            Genome.bakrep_dataset_id,
            Genome.sample_id,
        )
        .join(GeneLocusMembership, GeneLocusMembership.genome_id == Gene.genome_id)
        .join(Genome, Genome.genome_id == Gene.genome_id)
        .join(
            GenomeContig,
            (GenomeContig.genome_id == Gene.genome_id)
            & (GenomeContig.contig_index == Gene.contig_index),
        )
        .join(Locus, Locus.locus_id == GeneLocusMembership.locus_id)
        .where(
            GeneLocusMembership.pangenome_id == pangenome_id,
            GeneLocusMembership.flat_index == Gene.flat_index,
            Locus.node_label == node_label,
            Locus.pangenome_id == pangenome_id,
            Genome.sample_id == sample_id,
        )
        .order_by(Gene.flat_index)
    ).all()

    if not rows:
        return []

    dataset_id = rows[0].bakrep_dataset_id
    if not dataset_id:
        raise SequenceUnavailable(
            f"{sample_id} has no recorded annotation directory, so its GFF cannot be located"
        )
    path = gff_root / dataset_id / sample_id / f"{sample_id}.bakta.gff3.gz"
    sequences = _contig_sequences(str(path))

    out: list[GeneSequenceRow] = []
    for ordinal, row in enumerate(rows, start=1):
        contig = sequences.get(row.seqid)
        if contig is None:
            # ⚠ Named, not skipped. A silently dropped copy turns "2 of 2" into "1 of 1".
            raise SequenceUnavailable(
                f"contig {row.seqid} is not in {sample_id}'s annotation file, so this gene's bases "
                "cannot be read"
            )
        out.append(
            GeneSequenceRow(
                copy_ordinal=ordinal,
                copy_count=len(rows),
                flat_index=row.flat_index,
                contig_name=row.contig_name,
                seqid=row.seqid,
                start_position=row.start_position,
                end_position=row.end_position,
                strand=row.strand,
                strand_is_observed=row.strand_is_observed,
                gff_phase=row.gff_phase,
                is_five_prime_partial=row.is_five_prime_partial,
                length_nt=row.length_nt,
                stored_protein_length_aa=row.protein_length_aa,
                stored_gc_percent=row.gc_percent,
                bakta_gene_symbol=row.bakta_gene_symbol,
                bakta_product=row.bakta_product,
                locus_tag=row.locus_tag,
                sequence=read_gene_sequence(
                    contig,
                    start_position=row.start_position,
                    end_position=row.end_position,
                    strand=row.strand,
                    phase=row.gff_phase,
                    is_five_prime_partial=row.is_five_prime_partial,
                    flank_length=flank_length,
                ),
            )
        )
    return out
