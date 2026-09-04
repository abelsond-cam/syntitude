"""The vendored GFF + translation logic must agree with `nuna`, on real data.

⛔ These tests are what make the vendoring safe. The serving install cannot depend on `nuna`, so
`gff_text_reader` and `gene_sequence_reader` carry pinned copies of its rules — and a copy is only
safe while something fails when it diverges. That something is this file.

They skip where `nuna` or the pulled probe data is unavailable (a bare serving install), and say
which, rather than passing quietly.
"""

import os
import sys
from pathlib import Path

import pytest

NUNA_SRC = Path(os.environ.get("NUNA_SRC", Path.home() / "developer/nuna/src"))
NUNA_DATA = Path(os.environ.get("NUNA_DATA", Path.home() / "developer/nuna/data"))
GFF_ROOT = NUNA_DATA / "raw/gff"

if NUNA_SRC.is_dir() and str(NUNA_SRC) not in sys.path:
    sys.path.insert(0, str(NUNA_SRC))

nuna_genome_sequence = pytest.importorskip(
    "nuna.tl.locus_browser.genome_sequence",
    reason=f"nuna not importable from {NUNA_SRC} — vendored-copy cross-check cannot run",
)
pytestmark = pytest.mark.skipif(
    not GFF_ROOT.is_dir(), reason=f"probe GFFs not pulled to {GFF_ROOT}"
)

from syntitude_backend.gff.gene_sequence_reader import (  # noqa: E402
    CODON_TABLE,
    INITIATOR_CODONS,
    read_gene_sequence,
    reverse_complement,
)
from syntitude_backend.gff.gff_cds_parser import parse_genome_annotation  # noqa: E402


def _some_gffs(limit):
    return sorted(GFF_ROOT.glob("*/*/*.bakta.gff3.gz"))[:limit]


def test_the_vendored_codon_table_is_byte_identical_to_nunas():
    from nuna.tl.bakta_rna.coords import CODON_TABLE as NUNA_TABLE

    assert CODON_TABLE == NUNA_TABLE
    assert len(CODON_TABLE) == 64, "table 11 has 64 codons; a short table silently yields X"


def test_the_vendored_initiators_and_complement_match():
    assert INITIATOR_CODONS == nuna_genome_sequence._INITIATORS
    assert reverse_complement("ACGTN") == nuna_genome_sequence.revcomp("ACGTN")


def test_translation_agrees_with_nuna_on_every_gene_of_a_real_genome():
    # Not a fixture: a fixture that is not production-shaped tests a branch production never takes.
    path = _some_gffs(1)[0]
    annotation = parse_genome_annotation(path)
    assert annotation.carries_sequence, f"{path.name} has no ##FASTA block"

    compared = 0
    for feature in annotation.coding_features:
        contig = annotation.contig_sequences.get(feature.seqid)
        if contig is None:
            continue
        view = read_gene_sequence(
            contig,
            start_position=feature.start_position,
            end_position=feature.end_position,
            strand=feature.strand,
            phase=feature.phase,
            is_five_prime_partial=feature.is_five_prime_partial,
        )
        expected = nuna_genome_sequence.translate_cds(
            view.coding_sequence, feature.phase, feature.is_five_prime_partial
        )
        assert view.protein_sequence == expected, f"{feature.locus_tag} at {feature.seqid}:{feature.start_position}"
        compared += 1

    # Coverage before the claim: "0 differ" over 0 genes is not a pass.
    assert compared > 1000, f"only {compared} genes compared — too few to mean anything"


def test_gc_agrees_with_nuna():
    path = _some_gffs(1)[0]
    annotation = parse_genome_annotation(path)
    feature = annotation.coding_features[0]
    view = read_gene_sequence(
        annotation.contig_sequences[feature.seqid],
        start_position=feature.start_position,
        end_position=feature.end_position,
        strand=feature.strand,
    )
    assert view.gc_percent == pytest.approx(100.0 * nuna_genome_sequence.gc_fraction(view.coding_sequence))


def test_a_minus_strand_flank_is_taken_from_the_HIGHER_coordinate_end():
    # The bug this exists to catch renders perfectly: slicing `start - flank` unconditionally gives
    # the DOWNSTREAM flank for every minus-strand gene, which is about half of them.
    contig = "".join("ACGT"[i % 4] for i in range(1000))
    plus = read_gene_sequence(contig, start_position=401, end_position=600, strand="+", flank_length=50)
    minus = read_gene_sequence(contig, start_position=401, end_position=600, strand="-", flank_length=50)

    assert plus.upstream_flank_sequence == contig[350:400]
    assert minus.upstream_flank_sequence == reverse_complement(contig[600:650])
    assert minus.downstream_flank_sequence == reverse_complement(contig[350:400])
    assert minus.coding_sequence == reverse_complement(plus.coding_sequence)


def test_a_flank_running_off_a_contig_end_SAYS_it_was_truncated():
    contig = "ACGT" * 25  # 100 bp
    view = read_gene_sequence(contig, start_position=10, end_position=40, strand="+", flank_length=100)
    assert view.upstream_flank_is_truncated_by_contig_end is True
    assert view.downstream_flank_is_truncated_by_contig_end is True
    assert len(view.upstream_flank_sequence) == 9, "clamped to the contig, not padded"


def test_every_probe_gff_parses_and_carries_sequence():
    paths = _some_gffs(8)
    assert paths, "no GFFs found"
    for path in paths:
        annotation = parse_genome_annotation(path)
        assert annotation.carries_sequence, f"{path.name} has no ##FASTA"
        assert annotation.coding_features, f"{path.name} has no CDS lines"
