<script setup lang="ts">
/**
 * One labelled block of sequence, with a copy button.
 *
 * ⛔ **The heading says what the block IS, and for the flanks that means saying what it is NOT.**
 * The reader's purpose here is guide design, and a guide designed against flanking DNA in the belief
 * that it is coding is a wasted experiment — so "100 bases upstream" is never shown without
 * "— not the gene" attached to it.
 *
 * ⚠ **A copy that fails must say so.** Clipboard access can be refused (an insecure origin, a
 * permissions policy, a browser that has never implemented it), and a button that silently does
 * nothing sends a reader to the bench with an empty clipboard and no idea.
 */
import { ref } from "vue";

const props = defineProps<{
  kind: "up" | "cds" | "down" | "aa";
  heading: string;
  /** Where it came from — contig coordinates, or how it was produced. */
  provenance: string;
  sequence: string;
  /** Named in the copy button's title, so a reader knows what landed on their clipboard. */
  what: string;
}>();

const copyState = ref<"idle" | "copied" | "failed">("idle");

async function copy(): Promise<void> {
  try {
    // ⚠ Optional-chained: `navigator.clipboard` is undefined on an insecure origin and in jsdom,
    // and a bare property access there throws rather than returning undefined.
    const clipboard = navigator.clipboard;
    if (clipboard === undefined) throw new Error("no clipboard");
    await clipboard.writeText(props.sequence);
    copyState.value = "copied";
  } catch {
    copyState.value = "failed";
  }
}
</script>

<template>
  <div class="seq-block" :class="`seq-${kind}`">
    <div class="seq-head">
      <h4>{{ heading }}</h4>
      <button
        type="button"
        class="seq-copy"
        :title="`copy ${what}`"
        @click="copy"
      >{{ copyState === "copied" ? "copied" : copyState === "failed" ? "copy failed" : "copy" }}</button>
    </div>
    <p v-if="provenance" class="seq-prov">{{ provenance }}</p>
    <!-- ⚠ `<pre>` and not a `<div>`: the sequence is read a base at a time and must not reflow into
         a shape that makes two adjacent bases look like one. -->
    <pre class="seq-bases">{{ sequence }}</pre>
  </div>
</template>
