<script setup lang="ts">
/**
 * **Embedding geometry — consistency, never corroboration.**
 *
 * ⛔ Embedding distance is *the clustering's own objective*, so this card is reported as consistency
 * and diagnosis and must never be read as independent support. The independent evidence is above:
 * UniRef50, Pfam and genomic context. The published card says so in its own footer and that
 * sentence is carried here verbatim.
 *
 * ⚠ **Not measurable is a sentence, not a zero.** A singleton is its own medoid and has no
 * separation at all; rendering that as `0.000` puts a made-up number beside real ones.
 */
import { computed } from "vue";

import type { LocusGeometry, MapProjection, Representation } from "@/api/types";
import {
  percentileLabel,
  separationVerdict,
  signedFixed,
  similarityFromDistance,
} from "@/lib/locusStatistics";

import NullStrip from "./NullStrip.vue";

const props = defineProps<{
  geometry: Readonly<Record<Representation, LocusGeometry>>;
  mapProjections: readonly MapProjection[];
  /** The locus's member-gene count — only to say *why* a single gene is not measurable. */
  geneCount: number;
  /** The other half of "p12 of 12,104 loci", per representation where the API has it. */
  separationMeasurableLocusCount: number | null;
}>();

/** ⚠ Bacformer first: it is the context axis the track is built on. */
const ORDER: readonly { readonly representation: Representation; readonly heading: string }[] = [
  { representation: "bacformer", heading: "Bacformer" },
  { representation: "esm", heading: "ESM" },
];

const projectionFor = computed(() => {
  const index = new Map<string, MapProjection>();
  for (const projection of props.mapProjections) index.set(projection.representation, projection);
  return index;
});

const blocks = computed(() =>
  ORDER.map(({ representation, heading }) => {
    const geometry = props.geometry[representation];
    const within = similarityFromDistance(geometry.within_medoid_distance);
    const nearest = similarityFromDistance(geometry.nearest_medoid_distance);
    const projection = projectionFor.value.get(representation) ?? null;
    return {
      representation,
      heading,
      within,
      nearest,
      projection,
      verdict: separationVerdict(within, nearest, geometry.separation_percentile),
      // ⛔ Both ticks are needed to place anything on the strip; one alone would be a mark with
      // nothing to compare it to.
      showsNullStrip: within !== null && nearest !== null && projection !== null,
    };
  }).filter((block) => block.within !== null || block.nearest !== null),
);

const measurableCount = computed(() => props.separationMeasurableLocusCount);

function separationText(block: (typeof blocks.value)[number]): string {
  if (block.verdict !== null) {
    const over =
      measurableCount.value === null
        ? "the measurable loci"
        : `${measurableCount.value.toLocaleString()} loci`;
    return `${percentileLabel(block.verdict.percentile)} of ${over}`;
  }
  // ⚠ The reason, where there is one to give: a single gene IS its own medoid.
  return props.geneCount === 1 ? "not measurable — single gene" : "not measurable";
}

/** A similarity as a rail width, clamped into the axis the strip also uses. */
function railPercent(value: number): string {
  return `${(100 * Math.max(0, Math.min(1, value))).toFixed(1)}%`;
}
</script>

<template>
  <div v-if="blocks.length" class="card">
    <h2>Embedding geometry</h2>

    <template v-for="block in blocks" :key="block.representation">
      <h3 class="sub-head">{{ block.heading }}</h3>

      <div v-if="block.within !== null" class="pair">
        <div class="lab">own members</div>
        <!-- inline width: jsdom computes no layout, so a stylesheet version is untestable -->
        <div class="rail"><i :style="{ width: railPercent(block.within) }" /></div>
        <div class="val">{{ block.within.toFixed(3) }}</div>
      </div>
      <div v-if="block.nearest !== null" class="pair inter">
        <div class="lab">nearest other</div>
        <div class="rail"><i :style="{ width: railPercent(block.nearest) }" /></div>
        <div class="val">{{ block.nearest.toFixed(3) }}</div>
      </div>

      <NullStrip
        v-if="block.showsNullStrip"
        :bin-lower-edge="block.projection!.null_bin_lower_edge"
        :bin-width="block.projection!.null_bin_width"
        :bin-counts="block.projection!.null_bin_counts"
        :mean-cosine="block.projection!.null_mean_cosine"
        :within-similarity="block.within!"
        :nearest-similarity="block.nearest!"
      />

      <div class="pair sep">
        <div class="lab">separation</div>
        <div class="sep-pct">{{ separationText(block) }}</div>
        <div class="val">{{ block.verdict === null ? "—" : signedFixed(block.verdict.separation) }}</div>
      </div>
    </template>

    <p class="muted">
      Cosine similarity of a locus's members to its own medoid (own members) against that medoid to
      the nearest other locus's (nearest other); separation is the difference. Embedding distance is
      the clustering's own objective, so this is reported as consistency and diagnosis — never as
      corroboration. The independent evidence is above: UniRef50, Pfam and genomic context.
    </p>
  </div>
</template>
