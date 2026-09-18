<script setup lang="ts">
/**
 * The breadcrumb — the last six loci walked, each but the last a button back to it.
 *
 * ⛔ **It retreats rather than grows when the reader goes Back** — `advanceTrail` owns that rule, and
 * this only draws what the navigation store holds. A crumb is a JUMP (`go(i)` with no direction on
 * the published page), so it always faces forward.
 *
 * ⚠ Names come from loci this session DREW. A crumb whose locus has not been drawn — the current one
 * while its response is in flight, or one that failed to load for a reason other than not existing
 * (a locus that does not exist leaves no crumb at all) — shows its label, which is still a true name.
 */
import { computed } from "vue";

const props = defineProps<{
  trail: readonly string[];
  displayNames: ReadonlyMap<string, string>;
}>();

const emit = defineEmits<{ go: [locusLabel: string] }>();

/** How many crumbs are drawn. The trail itself keeps more; the row has room for six. */
const SHOWN = 6;

const crumbs = computed(() =>
  props.trail.length < 2
    ? []
    : props.trail.slice(-SHOWN).map((label) => ({
        label,
        name: props.displayNames.get(label) ?? `·${label}`,
      })),
);
</script>

<template>
  <div id="trail" class="trail">
    <template v-for="(crumb, index) in crumbs" :key="`${index}-${crumb.label}`">
      <span v-if="index" class="sep">›</span>
      <span v-if="index === crumbs.length - 1">{{ crumb.name }}</span>
      <button v-else type="button" @click="emit('go', crumb.label)">{{ crumb.name }}</button>
    </template>
  </div>
</template>
