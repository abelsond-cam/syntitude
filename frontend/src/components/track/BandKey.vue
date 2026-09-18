<script setup lang="ts">
/**
 * One key for BOTH of a block's channels — colour first, then transparency, in the order the eye
 * meets them. A block carries two independent quantities, and a reader shown one key reads the other
 * wrong, so they belong together (template.html, David 2026-08-25). Static: nothing here depends on
 * the locus.
 */
</script>

<template>
  <div class="band-note">
    <span class="band-title">Graph nodes</span>
    <span class="band-key">
      <span class="band-ch">
        <i class="band-ramp" aria-hidden="true" />
        <span class="band-ends"><em>divergent</em><em>always this one</em></span>
      </span>
      <span class="band-ch">
        <i class="band-pen" aria-hidden="true" />
        <span class="band-ends"><em>all genomes</em><em>few genomes</em></span>
      </span>
    </span>
  </div>
</template>
