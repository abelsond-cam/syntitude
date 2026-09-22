<script setup lang="ts">
/**
 * "+ View your own genomes" — the second box in the switcher's left gutter, under the anchor box.
 *
 * ⭐ **It is the anchor box's sibling, not its replacement** (David, 2026-09-22): the anchor box keeps
 * its job and its ⚓; this one brings genomes the model was never built from. Both are grey until
 * something is chosen, and only one can be chosen at a time — a state the store will own when
 * placed genomes arrive. Until then this box only opens the dialog.
 *
 * ⚠ The `+` is the mark, in the same place as the anchor's ⚓ and the same grey, so the two boxes read
 * as one pair of controls rather than two unrelated widgets.
 */
import { useOwnGenomesStore } from "@/stores/ownGenomesStore";

const own = useOwnGenomesStore();
// ⚠ Both boxes are in flow inside `.arr-gutter`, so when the anchor box is REMOVED — which is what
// happens where the catalogue cannot answer an anchor — this one simply takes its place.
</script>

<template>
  <div id="own-genomes-wrap" class="own-genomes">
    <button type="button" class="own-genomes-box" @click="own.open('account')">
      <span class="own-genomes-mark" aria-hidden="true">+</span>
      <span class="own-genomes-label">View your own genomes</span>
    </button>
  </div>
</template>
