<script setup lang="ts">
/**
 * One labelled block of sequence, with a copy button.
 *
 * ⛔ **The heading says what the block IS, and for the flanks that means saying what it is NOT.**
 * The reader's purpose here is guide design, and a guide designed against flanking DNA in the belief
 * that it is coding is a wasted experiment — so "100 bases upstream" is never shown without
 * "— not the gene" attached to it.
 *
 * ⭐ **Numbered from 1 WITHIN the block, sixty to a line** (`app.js::seqPre`), with the true contig
 * span in the note above it. One signed ruler running across all three blocks would put a "−100"
 * gutter on the upstream flank, which invites exactly the reading — that the flank is part of the
 * gene — this panel exists to prevent. The copy button copies the bases alone, never the numbers.
 */
import { computed } from "vue";

import CopySequenceButton from "./CopySequenceButton.vue";

const props = defineProps<{
  kind: "up" | "cds" | "down" | "aa";
  heading: string;
  /** Where it came from — contig coordinates, or how it was produced. */
  provenance: string;
  sequence: string;
  /** Named in the copy button, so a reader knows what landed on their clipboard. */
  what: string;
}>();

/** Bases per line. */
const LINE = 60;

/**
 * ⚠ Computed here rather than with a CSS counter: a `<pre>` is what a reader selects and pastes, and
 * the numbers have to be in the text they select or the columns stop lining up in their editor.
 */
const numbered = computed(() => {
  const sequence = props.sequence;
  const width = String(sequence.length).length;
  const lines: string[] = [];
  for (let start = 0; start < sequence.length; start += LINE) {
    lines.push(`${String(start + 1).padStart(width, " ")}  ${sequence.slice(start, start + LINE)}`);
  }
  return lines.join("\n");
});
</script>

<template>
  <div class="seq-block" :class="kind">
    <div class="seq-bh">
      <h4>{{ heading }}</h4>
      <CopySequenceButton v-if="sequence" label="copy" :what="what" :text="sequence" />
    </div>
    <p v-if="provenance" class="seq-note">{{ provenance }}</p>
    <!-- ⚠ `<pre>` and not a `<div>`: the sequence is read a base at a time and must not reflow into
         a shape that makes two adjacent bases look like one. -->
    <pre v-if="sequence" class="seq-pre">{{ numbered }}</pre>
    <!-- An empty flank is a FACT about the assembly — the contig ends there — not a missing value. -->
    <p v-else class="seq-none">None in the assembly.</p>
  </div>
</template>
