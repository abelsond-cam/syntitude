"""A gene's DNA, its flanks and its protein — sliced from a GFF's ``##FASTA`` block.

⛔ **The translation rule here is a PINNED COPY of `nuna.tl.locus_browser.genome_sequence`, not a
second opinion.** The serving install must not depend on `nuna` (a private repo the med school
server has no access to), and the API has to translate. So the rule is vendored, and
``tests/test_translation_matches_nuna.py`` imports the original and asserts byte-equality on real
genes — the copy is safe *because the test fails when they diverge*, not because it was careful.
Vendoring reference logic under a cross-check is the same pattern `vendor_reference.py` already
uses in `nuna` for external tables.

The order of the four translation steps is the part that is easy to get subtly wrong: drop
``phase`` bases **first**, then trim to a codon boundary, then translate, then promote the
initiator — and **never** promote when 5'-partial.
"""

from __future__ import annotations

from dataclasses import dataclass

#: NCBI table 11 in ``TCAG`` order, byte-identical to `nuna.tl.bakta_rna.coords.CODON_TABLE`.
_BASES = "TCAG"
_AMINO_ACIDS = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODON_TABLE = {
    a + b + c: _AMINO_ACIDS[i]
    for i, (a, b, c) in enumerate((a, b, c) for a in _BASES for b in _BASES for c in _BASES)
}

#: Table 11 initiators. A CDS starting with any of these is translated as `M` by prodigal/pyrodigal
#: even when it is GTG or TTG, so a naive codon table disagrees on exactly the first residue.
INITIATOR_CODONS = frozenset({"ATG", "GTG", "TTG", "CTG", "ATT", "ATC", "ATA"})

_COMPLEMENT = str.maketrans("ACGTN", "TGCAN")


def reverse_complement(sequence: str) -> str:
    """Reverse complement, with `N` preserved."""
    return sequence.translate(_COMPLEMENT)[::-1]


def translate_coding_sequence(nucleotides: str, phase: int, is_five_prime_partial: bool) -> str:
    """Table-11 translation of a CDS already in the gene's reading direction."""
    if phase:
        nucleotides = nucleotides[phase:]
    nucleotides = nucleotides[: len(nucleotides) - len(nucleotides) % 3]
    if len(nucleotides) < 3:
        return ""
    protein = "".join(CODON_TABLE.get(nucleotides[i : i + 3], "X") for i in range(0, len(nucleotides), 3))
    if protein.endswith("*"):
        protein = protein[:-1]
    if not is_five_prime_partial and protein and protein[0] != "M" and nucleotides[:3] in INITIATOR_CODONS:
        protein = "M" + protein[1:]
    return protein


def gc_percent(sequence: str) -> float:
    """G+C over the bases that are ``ACGT``; 0.0 for an empty or wholly ambiguous span."""
    countable = sum(sequence.count(base) for base in "ACGT")
    return 100.0 * (sequence.count("G") + sequence.count("C")) / countable if countable else 0.0


@dataclass(frozen=True)
class GeneSequenceView:
    """Everything the Sequence tab shows for one gene copy."""

    coding_sequence: str
    upstream_flank_sequence: str
    downstream_flank_sequence: str
    protein_sequence: str
    gc_percent: float
    upstream_flank_is_truncated_by_contig_end: bool
    downstream_flank_is_truncated_by_contig_end: bool


def read_gene_sequence(
    contig_sequence: str,
    *,
    start_position: int,
    end_position: int,
    strand: str,
    phase: int = 0,
    is_five_prime_partial: bool = False,
    flank_length: int = 100,
) -> GeneSequenceView:
    """Slice one gene and its flanks out of a contig. Coordinates are **1-based inclusive**.

    ⛔ **Flanks are in the GENE's reading direction, not the contig's.** On a minus-strand gene the
    upstream flank sits at HIGHER contig coordinates and is reverse-complemented with the gene. This
    is the repo's own convention (`load_meta_flanks` orients on strand, `app.js:4376-4386`) and the
    only one a guide can be designed against. Slicing ``start - flank`` unconditionally returns the
    **downstream** flank for roughly half of all genes and looks entirely plausible on screen.

    ⚠ Truncation is reported, not hidden. These are draft assemblies — mean contig 14.4 kb, ~14
    genes — so a gene within 100 bp of a contig end is common, and a short flank that does not say
    it is short reads as a complete one.
    """
    contig_length = len(contig_sequence)
    is_minus = strand == "-"

    body = contig_sequence[start_position - 1 : end_position]

    # Contig-coordinate spans of the two flanks, before any orientation is applied.
    low_from, low_to = max(1, start_position - flank_length), start_position - 1
    high_from, high_to = end_position + 1, min(contig_length, end_position + flank_length)
    low_span = contig_sequence[low_from - 1 : low_to] if low_to >= low_from else ""
    high_span = contig_sequence[high_from - 1 : high_to] if high_to >= high_from else ""

    low_is_truncated = (start_position - flank_length) < 1
    high_is_truncated = (end_position + flank_length) > contig_length

    if is_minus:
        coding = reverse_complement(body)
        upstream, downstream = reverse_complement(high_span), reverse_complement(low_span)
        upstream_truncated, downstream_truncated = high_is_truncated, low_is_truncated
    else:
        coding = body
        upstream, downstream = low_span, high_span
        upstream_truncated, downstream_truncated = low_is_truncated, high_is_truncated

    return GeneSequenceView(
        coding_sequence=coding,
        upstream_flank_sequence=upstream,
        downstream_flank_sequence=downstream,
        protein_sequence=translate_coding_sequence(coding, phase, is_five_prime_partial),
        gc_percent=gc_percent(coding),
        upstream_flank_is_truncated_by_contig_end=upstream_truncated,
        downstream_flank_is_truncated_by_contig_end=downstream_truncated,
    )
