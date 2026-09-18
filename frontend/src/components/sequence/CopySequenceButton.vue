<script setup lang="ts">
/**
 * Copy a sequence to the clipboard — and say so when that fails.
 *
 * ⚠ **A copy that fails must say so.** Clipboard access can be refused (an insecure origin, a
 * permissions policy, a browser that has never implemented it), and a button that silently does
 * nothing sends a reader to the bench with an empty clipboard and no idea.
 */
import { ref } from "vue";

const props = defineProps<{
  label: string;
  /** Named in the button's accessible label, so a reader knows what landed on their clipboard. */
  what: string;
  text: string;
}>();

const copyState = ref<"idle" | "copied" | "failed">("idle");

async function copy(): Promise<void> {
  try {
    // ⚠ Optional-chained: `navigator.clipboard` is undefined on an insecure origin and in jsdom,
    // and a bare property access there throws rather than returning undefined.
    const clipboard = navigator.clipboard;
    if (clipboard === undefined) throw new Error("no clipboard");
    await clipboard.writeText(props.text);
    copyState.value = "copied";
  } catch {
    copyState.value = "failed";
  }
}
</script>

<template>
  <button type="button" class="seq-copy" :aria-label="`Copy ${what}`" :title="`copy ${what}`" @click="copy">
    {{ copyState === "copied" ? "copied" : copyState === "failed" ? "copy failed" : label }}
  </button>
</template>
