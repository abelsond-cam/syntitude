<script setup lang="ts">
/**
 * **The neighbourhood map — this locus and its five nearest, fitted on their own.**
 *
 * ⭐ **Why this is not a UMAP crop.** The map used to be one UMAP over every gene in the catalogue,
 * with three crops of it as three zoom levels. Measured on the shipped fit, a locus's five nearest
 * loci landed a **median 18.5 % of the map apart**, so the "these loci" crop showed six specks
 * scattered over the whole picture. David, 2026-08-19: *"the 'nearest' are spread over the whole
 * catalogue view and it thus indicates the examination of 'these loci' is completely meaningless."*
 * UMAP preserves local neighbourhoods, not global distance, and no caption rescues a crop of one. So
 * the picture is classical MDS on the six loci's own pairwise Euclidean distances, fitted per locus.
 *
 * ⛔ **One picture, not two (David, 2026-09-22).** The whole-catalogue UMAP survived as a second zoom,
 * kept for orientation, and was removed: *"It isn't helpful. Just display closest 6 neighbours."*
 *
 * ⭐ **Each ring is that locus's own members' median distance from its centre, at TRUE SCALE** — so
 * a ring that reaches a neighbour is a spread that reaches it, which is the whole question the
 * picture is asked.
 *
 * ⚠ **Both representations, as tabs, because they are different sets of loci.** The five nearest in
 * context space are not the five nearest in sequence space — their separations agree at only
 * ρ ≈ 0.47 — so switching the tab changes the legend as well as the picture.
 *
 * ⛔ **SVG, not canvas.** The published page drew on a canvas. Six dots and six rings do not need
 * raster, and jsdom computes no canvas — so a canvas version is invisible to every test, the same
 * reason the track's widths are inline styles.
 */
import { computed } from "vue";

import type { LocusDetailResponse, NeighbourDisplayRow, Representation } from "@/api/types";
import {
  chordDistance,
  chordMatrixFrom,
  classicalMds,
  fitViewport,
  projectOnto,
} from "@/lib/geometry/classicalMultidimensionalScaling";
import { sharePercent } from "@/lib/formatting";
import { similarityFromDistance } from "@/lib/locusStatistics";

const props = defineProps<{
  detail: LocusDetailResponse;
  representation: Representation;
  /** Which representations the catalogue actually has, so a tab is never offered for a missing one. */
  availableRepresentations: readonly Representation[];
}>();

const emit = defineEmits<{
  walk: [locusLabel: string];
  selectRepresentation: [representation: Representation];
}>();

/** The drawn square's side, in user units. The SVG scales itself with `viewBox`. */
const DRAWN_SIZE = 600;
/** How the five neighbours are coloured, in rank order — the page's own five map hues. */
const HUES = ["var(--map-1)", "var(--map-2)", "var(--map-3)", "var(--map-4)", "var(--map-5)"];

const REPRESENTATION_LABEL: Readonly<Record<Representation, string>> = {
  bacformer: "Bacformer",
  esm: "ESM",
};

const geometry = computed(() => props.detail.locus.geometry[props.representation]);

const neighboursByOrdinal = computed(() => {
  const index = new Map<number, NeighbourDisplayRow>();
  for (const row of props.detail.neighbour_display_rows) index.set(row.catalogue_ordinal, row);
  return index;
});

/**
 * The six loci, in slot order: the focal one, then its nearest in this representation.
 *
 * ⛔ **Slots are not ranks.** A `-1` in `nearest_locus_ordinals` drops that locus **and its slot**,
 * and the surviving slot indices are what address the cosine matrix. Reading by rank instead draws
 * one locus's distances on another — and the picture still looks like a picture.
 *
 * ⚠ **The colour is fixed HERE, by position among the resolved neighbours** — not by position among
 * the points the fit ends up drawing, which can drop one whose cosines were not measured. A hue is a
 * RANK: the rendered PNG diagnostics colour by it too, so a figure and the page agree on which colour
 * the nearest neighbour is. `app.js:2765` coloured by resolved order for the same reason.
 */
const members = computed(() => {
  const ordinals = geometry.value.nearest_locus_ordinals;
  const focal = props.detail.locus;
  const out = [
    {
      slot: 0,
      label: focal.label,
      displayName: focal.display_name,
      product: focal.best_product,
      withinDistance: geometry.value.within_medoid_distance,
      isFocal: true,
      colour: "var(--map-focal)",
    },
  ];
  if (ordinals === null) return out;
  for (const [slot, ordinal] of ordinals.entries()) {
    if (ordinal < 0) continue;
    const row = neighboursByOrdinal.value.get(ordinal);
    if (row === undefined) continue;
    out.push({
      // ⚠ `slot + 1` — the cosine matrix's index 0 is the focal locus, so a neighbour's slot is
      // one past its position in `nearest_locus_ordinals`.
      slot: slot + 1,
      label: row.label,
      displayName: row.display_name,
      product: row.best_product,
      withinDistance: row.within_medoid_distance[props.representation],
      isFocal: false,
      colour: HUES[(out.length - 1) % HUES.length] as string,
    });
  }
  return out;
});

/** The per-locus MDS fit, or `null` where there are too few measured points to make one. */
const fit = computed(() => {
  const matrix = geometry.value.cosine_matrix;
  if (matrix === null) return null;
  // Restrict the resolved 6×6 to the slots that actually have a locus behind them.
  const slots = members.value.map((member) => member.slot);
  const restricted = slots.map((a) => slots.map((b) => matrix[a]?.[b] ?? null));
  const built = chordMatrixFrom(restricted);
  if (built === null) return null;
  const kept = built.keptIndices;
  const drawn = kept.map((index) => members.value[index]).filter((member) => member !== undefined);
  if (drawn.length < 2) return null;

  const mds = classicalMds(built.distances, kept.length);
  // ⚠ The ring is in the SAME Euclidean units as the gaps, which is what lets the two be compared.
  const radii = drawn.map((member) => {
    const similarity = similarityFromDistance(member.withinDistance);
    return similarity === null ? 0 : chordDistance(1 - similarity);
  });
  const viewport = fitViewport(mds.positions, radii, DRAWN_SIZE);
  return {
    kept: mds.kept,
    points: drawn.map((member, index) => {
      const [x, y] = projectOnto(mds.positions[index] as [number, number], viewport, DRAWN_SIZE);
      return {
        ...member,
        x,
        y,
        // ⛔ The radius is scaled by the SAME factor as the positions, never separately.
        radius: (radii[index] as number) * viewport.scale,
      };
    }),
  };
});

/**
 * ⛔ **The legend names what is ON the picture.** The fit can drop a locus whose cosines were not
 * measured, and a legend row for a locus the picture does not show is a claim the picture does not
 * support.
 */
const legend = computed(() => {
  const matrix = geometry.value.cosine_matrix;
  return (fit.value?.points ?? []).map((point) => ({
    label: point.label,
    displayName: point.displayName,
    product: point.product,
    colour: point.colour,
    isFocal: point.isFocal,
    // ⛔ Read at the point's own SLOT, not its position in the legend.
    cosine: point.isFocal ? null : (matrix?.[0]?.[point.slot] ?? null),
  }));
});

const nearNote = computed(() => {
  const label = REPRESENTATION_LABEL[props.representation];
  const kept = fit.value === null ? "—" : sharePercent(fit.value.kept);
  return (
    `A fit of these ${fit.value?.points.length ?? 0} alone, not a crop: classical MDS on their ` +
    `pairwise Euclidean distances (√(2−2cos) between L2-normalised ${label} medoids), keeping ` +
    `${kept} of their variance. Each ring is that locus's own members' median distance from its ` +
    "centre, at true scale — a ring reaching a neighbour is a spread that reaches it."
  );
});
</script>

<template>
  <div class="card map-card">
    <h2>Neighbourhood map</h2>

    <div v-if="availableRepresentations.length > 1" class="map-tabs">
      <button
        v-for="option in availableRepresentations"
        :key="option"
        type="button"
        class="map-tab"
        :class="{ on: option === representation }"
        :title="`${REPRESENTATION_LABEL[option]} — the five nearest loci in this representation, which are not the same five as in the other`"
        @click="emit('selectRepresentation', option)"
      >{{ REPRESENTATION_LABEL[option] }}</button>
    </div>

    <svg
      v-if="fit"
      class="map-figure"
      :viewBox="`0 0 ${DRAWN_SIZE} ${DRAWN_SIZE}`"
      role="img"
      :aria-label="`${detail.locus.display_name} and its ${fit.points.length - 1} nearest loci in ${REPRESENTATION_LABEL[representation]} space`"
    >
      <rect class="map-ground" x="0" y="0" :width="DRAWN_SIZE" :height="DRAWN_SIZE" />
      <!-- ⚠ Rings under dots, and the focal locus LAST so it is never hidden behind a neighbour. -->
      <circle
        v-for="point in [...fit.points].reverse()"
        :key="`ring-${point.label}`"
        class="map-ring"
        :cx="point.x"
        :cy="point.y"
        :r="point.radius"
        :stroke="point.colour"
      />
      <circle
        v-for="point in [...fit.points].reverse()"
        :key="`dot-${point.label}`"
        class="map-dot"
        :class="{ 'is-focal': point.isFocal }"
        :cx="point.x"
        :cy="point.y"
        :r="point.isFocal ? 11 : 8.5"
        :fill="point.colour"
      />
    </svg>
    <!-- ⛔ A locus with too few measured pairs gets a SENTENCE, not an empty frame: an empty box
         reads as "these loci are all at the same place", which is a different and false claim. -->
    <p v-else class="muted">
      No map here — this locus has fewer than two measured neighbours in
      {{ REPRESENTATION_LABEL[representation] }} space.
    </p>

    <div class="map-key">
      <button
        v-for="row in legend"
        :key="row.label"
        type="button"
        class="map-row"
        :class="{ 'is-focal': row.isFocal }"
        :disabled="row.isFocal"
        @click="emit('walk', row.label)"
      >
        <i :style="{ background: row.colour }" />
        <span class="nm">{{ row.displayName }}</span>
        <!-- the locus NUMBER is not what tells you whether a neighbour belongs here — the product is -->
        <span v-if="row.product" class="desc">{{ row.product }}</span>
        <span class="cos">{{ row.cosine === null ? "—" : row.cosine.toFixed(3) }}</span>
      </button>
    </div>

    <p v-if="fit" class="muted">{{ nearNote }}</p>
  </div>
</template>
