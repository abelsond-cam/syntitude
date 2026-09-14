<script setup lang="ts">
/**
 * One gene copy: where it is, what it reads, and the one sentence that has to be unmissable.
 *
 * ⛔ **The two flanking blocks are NOT part of the gene**, and the card says so above them in its
 * own paragraph rather than relying on the headings. A reader designing a guide across an end needs
 * the flanks; a reader who mistakes one for coding sequence has wasted an experiment.
 *
 * ⛔ **Flanks are in the GENE's reading direction.** On a minus-strand gene the upstream flank sits
 * at HIGHER contig coordinates and is reverse-complemented with it — which is why the card prints
 * the contig span it came from beside each block. The server does that orientation; the card only
 * reports it.
 */
import { computed } from "vue";

import type { GeneSequence } from "@/api/types";

import SequenceBlock from "./SequenceBlock.vue";

const props = defineProps<{ gene: GeneSequence; flankLength: number }>();

const isMinus = computed(() => props.gene.strand === "-");

function spanText(span: readonly [number, number] | null): string {
  if (span === null) return "";
  const reversed = isMinus.value ? ", reverse-complemented" : "";
  return `Contig ${span[0].toLocaleString()}–${span[1].toLocaleString()}${reversed}`;
}

const stats = computed(() => {
  const gene = props.gene;
  const rows: { key: string; value: string }[] = [
    // ⛔ The contig's NAME. `contig_index + 1` is a different contig 28.6 % of the time.
    { key: "Contig", value: gene.contig_name },
    {
      key: "Span",
      value: `${gene.start_position.toLocaleString()}–${gene.end_position.toLocaleString()} (1-based, inclusive)`,
    },
    { key: "Strand", value: isMinus.value ? "− (reverse)" : "+ (forward)" },
    {
      key: "Direction",
      value: isMinus.value
        ? "read as the reverse complement of the contig"
        : "read as the contig is written",
    },
    {
      key: "Length",
      value:
        `${gene.coding_sequence.length.toLocaleString()} bp · ` +
        `${gene.protein_sequence.length.toLocaleString()} aa`,
    },
    { key: "GC content", value: `${gene.gc_percent.toFixed(1)}%` },
  ];
  if (gene.is_five_prime_partial) {
    rows.push({ key: "Note", value: "5′-partial — this CDS does not begin at a start codon" });
  }
  // ⚠ Stated only when it is FALSE. A strand that was observed is the ordinary case and needs no
  // row; a strand that was forced to `+` because no parquet existed must never read as an
  // observation, and silence here would be exactly that.
  if (!gene.strand_is_observed) {
    rows.push({
      key: "Note",
      value: "the strand was not recorded for this genome and has been assumed forward",
    });
  }
  return rows;
});

/** ⚠ Draft assemblies — mean contig 14.4 kb, ~14 genes — so this is common, not exceptional. */
const truncatedEnds = computed(() => {
  const ends: string[] = [];
  if (props.gene.upstream_flank_is_truncated_by_contig_end) ends.push("upstream");
  if (props.gene.downstream_flank_is_truncated_by_contig_end) ends.push("downstream");
  return ends;
});

const edgeSentence = computed(() => {
  const ends = truncatedEnds.value;
  if (ends.length === 0) return null;
  return (
    `This gene sits within ${props.flankLength} bases of the end of ${props.gene.contig_name}, so ` +
    `the ${ends.join(" and ")} flank${ends.length > 1 ? "s are" : " is"} short. These are draft ` +
    "assemblies of a few hundred contigs each, so that is common rather than exceptional — the " +
    "missing bases are not in the assembly at all."
  );
});

const codingProvenance = computed(
  () =>
    `Contig ${props.gene.start_position.toLocaleString()}–${props.gene.end_position.toLocaleString()}` +
    `${isMinus.value ? ", reverse-complemented" : ""}. Includes the stop codon.`,
);
</script>

<template>
  <div class="seq-gene">
    <h3 v-if="gene.copy_count > 1" class="seq-copy-h">
      Copy {{ gene.copy_ordinal }} of {{ gene.copy_count }} at this locus
    </h3>

    <dl class="seq-stats">
      <template v-for="row in stats" :key="`${row.key}-${row.value}`">
        <dt>{{ row.key }}</dt>
        <dd>{{ row.value }}</dd>
      </template>
    </dl>

    <!-- ⛔ The one sentence this panel exists to make unmissable. -->
    <p class="seq-warn">
      The two flanking blocks are NOT part of the gene. They are the {{ flankLength }} bases of
      genomic DNA either side of it, shown so a guide can be designed across either end — only the
      middle block is the coding sequence.
    </p>

    <p v-if="edgeSentence" class="seq-edge">{{ edgeSentence }}</p>

    <SequenceBlock
      kind="up"
      :heading="`${flankLength} bases upstream — not the gene`"
      :provenance="spanText(gene.upstream_flank_span)"
      :sequence="gene.upstream_flank_sequence"
      what="the upstream flank"
    />
    <SequenceBlock
      kind="cds"
      :heading="`The gene — ${gene.coding_sequence.length.toLocaleString()} bases`"
      :provenance="codingProvenance"
      :sequence="gene.coding_sequence"
      what="the coding sequence"
    />
    <SequenceBlock
      kind="down"
      :heading="`${flankLength} bases downstream — not the gene`"
      :provenance="spanText(gene.downstream_flank_span)"
      :sequence="gene.downstream_flank_sequence"
      what="the downstream flank"
    />
    <SequenceBlock
      kind="aa"
      :heading="`Protein — ${gene.protein_sequence.length.toLocaleString()} residues`"
      provenance="Translated with NCBI table 11 from the bases above."
      :sequence="gene.protein_sequence"
      what="the protein sequence"
    />

    <!-- ⚠ The combined copy is offered and LABELLED as not the coding sequence alone, because it is
         the one a guide designer usually wants and the one most easily mistaken for the gene. -->
    <p class="seq-both">
      <SequenceBlock
        kind="cds"
        :heading="`Gene + ${flankLength} bp each side`"
        provenance="The three blocks above, joined in reading order — not the coding sequence alone."
        :sequence="gene.upstream_flank_sequence + gene.coding_sequence + gene.downstream_flank_sequence"
        :what="`the gene with its flanks, which is not the coding sequence alone`"
      />
    </p>
  </div>
</template>
