"""One pass over a Bakta GFF → its CDS features and its contig sequences.

⛔ **One pass, not two.** The CDS lines and the ``##FASTA`` block are in the same file, and a
1.9 MB gzipped GFF costs more to decompress twice than to hold once. The reader therefore returns
both halves together and the caller decides what to keep.

⛔ **No pandas.** ``extract_strand.parse_gff_cds`` returns a DataFrame, which is right for an
ingest job and wrong here: pandas is in the backend's ``ingest`` extra, not its serving
dependencies, and the sequence endpoint runs on a machine that has neither pandas nor ``nuna``.

Coordinates are the GFF's own: **1-based inclusive**, and ``end`` includes the stop codon.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from syntitude_backend.gff.gff_text_reader import open_gff_text

FASTA_DIRECTIVE = "##FASTA"


@dataclass(frozen=True)
class CodingFeature:
    """One CDS line. ``phase`` and ``is_five_prime_partial`` are what make translation reproducible."""

    seqid: str
    start_position: int          # 1-based inclusive
    end_position: int            # inclusive, INCLUDES the stop codon
    strand: str                  # '+' or '-'
    phase: int                   # 0/1/2; non-zero means the CDS does not begin at a start codon
    locus_tag: str | None
    is_five_prime_partial: bool


@dataclass(frozen=True)
class ParsedGenomeAnnotation:
    """A whole GFF: its CDS features in file order, and its contig sequences by seqid."""

    coding_features: tuple[CodingFeature, ...]
    contig_sequences: dict[str, str]

    @property
    def carries_sequence(self) -> bool:
        """Whether the file had a ``##FASTA`` block at all.

        ⚠ Checked rather than assumed. Measured 2026-09-04: all 280 probe GFFs carry one, but the
        endpoint must fail with a named reason on one that does not, never with a KeyError.
        """
        return bool(self.contig_sequences)


def _attributes(field: str) -> dict[str, str]:
    """GFF3 column 9 → a dict. Malformed pairs are skipped, not guessed at."""
    out: dict[str, str] = {}
    for item in field.rstrip(";").split(";"):
        key, separator, value = item.partition("=")
        if separator:
            out[key.strip()] = value.strip()
    return out


def parse_genome_annotation(path: Path, *, want_sequence: bool = True) -> ParsedGenomeAnnotation:
    """Read one GFF. Set ``want_sequence=False`` to stop at ``##FASTA`` and skip the bases."""
    features: list[CodingFeature] = []
    sequences: dict[str, str] = {}

    with open_gff_text(path) as handle:
        for line in handle:
            if line.startswith("#"):
                if line.startswith(FASTA_DIRECTIVE):
                    break
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 9 or columns[2] != "CDS":
                continue
            attributes = _attributes(columns[8])
            features.append(
                CodingFeature(
                    seqid=columns[0],
                    start_position=int(columns[3]),
                    end_position=int(columns[4]),
                    strand=columns[6],
                    # A '.' phase is 0 by GFF3 convention; Bakta writes an integer, but a
                    # reader that assumes so raises on a file it should have handled.
                    phase=int(columns[7]) if columns[7].isdigit() else 0,
                    locus_tag=attributes.get("locus_tag"),
                    # Bakta records partiality in `partial`/`start_type`; a non-zero phase is the
                    # portable signal and the one translate_cds keys on.
                    is_five_prime_partial=columns[7].isdigit() and int(columns[7]) != 0,
                )
            )
        else:
            # Loop finished without hitting ##FASTA: the file carries no sequence.
            return ParsedGenomeAnnotation(tuple(features), {})

        if want_sequence:
            sequences = _read_fasta_block(handle)

    return ParsedGenomeAnnotation(tuple(features), sequences)


def _read_fasta_block(handle) -> dict[str, str]:
    """Read the ``##FASTA`` block the caller has already positioned past.

    Sequences are uppercased once, here, so no downstream comparison has to think about case.
    """
    sequences: dict[str, str] = {}
    seqid: str | None = None
    chunks: list[str] = []
    for line in handle:
        if line.startswith(">"):
            if seqid is not None:
                sequences[seqid] = "".join(chunks)
            # The seqid is the first whitespace-delimited token, as in every FASTA.
            seqid = line[1:].split()[0]
            chunks = []
        elif seqid is not None:
            chunks.append(line.strip().upper())
    if seqid is not None:
        sequences[seqid] = "".join(chunks)
    return sequences
