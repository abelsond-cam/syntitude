<script setup lang="ts">
/**
 * **The neighbourhood map — two pictures, not two crops of one.**
 *
 * ⭐ **Why "these loci" is not a UMAP crop.** The map used to be one UMAP over every gene in the
 * catalogue, with three crops of it as three zoom levels. Measured on the shipped fit, a locus's
 * five nearest loci landed a **median 18.5 % of the map apart**, so the "these loci" crop showed six
 * specks scattered over the whole picture. David, 2026-08-19: *"the 'nearest' are spread over the
 * whole catalogue view and it thus indicates the examination of 'these loci' is completely
 * meaningless."* UMAP preserves local neighbourhoods, not global distance, and no caption rescues a
 * crop of one. So "these loci" is classical MDS on the six loci's own pairwise Euclidean distances,
 * fitted per locus — and "whole catalogue" is the UMAP, kept for the one job it can do: orientation.
 *
 * ⭐ **Each ring is that locus's own members' median distance from its centre, at TRUE SCALE** — so
 * a ring that reaches a neighbour is a spread that reaches it, which is the whole question the
 * picture is asked. ⛔ **Rings appear on "these loci" only.** On the UMAP a distance is not a
 * distance, so a ring drawn there would be a true number in a frame that cannot hold it.
 *
 * ⚠ **Both representations, as tabs, because they are different sets of loci.** The five nearest in
 * context space are not the five nearest in sequence space — their separations agree at only
 * ρ ≈ 0.47 — so switching the tab changes the legend as well as the picture.
 *
 * ⛔ **SVG, not canvas.** The published page drew both on a canvas. Six dots and six rings do not
 * need raster, and jsdom computes no canvas — so a canvas version is invisible to every test, the
 * same reason the track's widths are inline styles. The one part that genuinely does need raster is
 * the catalogue dust at 889k points, and that is a PNG rendered on the server and dropped into this
 * same SVG as an `<image>`, so both zooms share one coordinate system.
 */
import { computed, ref, watch } from "vue";

import { catalogueScatterSpriteUrl } from "@/api/client";
import type {
  LocusDetailResponse,
  MapPosition,
  MapProjection,
  NeighbourDisplayRow,
  Representation,
} from "@/api/types";
import { projectOntoSprite, spriteCoverageSentence } from "@/lib/catalogueMapViewport";
import {
  chordDistance,
  chordMatrixFrom,
  classicalMds,
  fitViewport,
  projectOnto,
} from "@/lib/geometry/classicalMultidimensionalScaling";
import { sharePercent } from "@/lib/formatting";
import { similarityFromDistance } from "@/lib/locusStatistics";
import { MAP_ZOOMS, MAP_ZOOM_LABEL, type MapZoom } from "@/stores/neighbourhoodMapStore";

const props = defineProps<{
  detail: LocusDetailResponse;
  representation: Representation;
  /** Which representations the catalogue actually has, so a tab is never offered for a missing one. */
  availableRepresentations: readonly Representation[];
  zoom: MapZoom;
  /** ⚠ Needed to address the sprite, which is a URL rather than a field in a response. */
  speciesKey: string;
  /** This representation's projection, carrying the sprite descriptor. `null` before the catalogue lands. */
  projection: MapProjection | null;
}>();

const emit = defineEmits<{
  walk: [locusLabel: string];
  selectRepresentation: [representation: Representation];
  selectZoom: [zoom: MapZoom];
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
const sprite = computed(() => props.projection?.scatter_sprite ?? null);

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
 * ⚠ **The colour is fixed HERE, by position among the resolved six** — not by position in whatever
 * subset a given picture ends up drawing. The two zooms drop different members (one needs a measured
 * cosine, the other a medoid position), so a colour taken from the drawn subset would repaint a
 * locus as the reader switched zoom, and the legend beside it would agree — quietly, and with both
 * pictures internally consistent. `app.js:2765` coloured by resolved order for the same reason.
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
      mapPosition: geometry.value.map_position,
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
      mapPosition: row.map_position[props.representation],
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
 * The same six on the whole-catalogue sprite.
 *
 * ⛔ **Projected with the viewport the SERVER published, never one derived here.** See
 * `lib/catalogueMapViewport.ts`: a re-derived transform puts the focal dot beside its own speck
 * rather than on it, and the result is still a scatter plot with a highlighted point.
 */
const globalPoints = computed(() => {
  const drawn = sprite.value;
  if (drawn === null) return [];
  return members.value
    .filter((member) => member.mapPosition !== null)
    .map((member) => {
      const [x, y] = projectOntoSprite(member.mapPosition as MapPosition, drawn, DRAWN_SIZE);
      return { ...member, x, y };
    });
});

const spriteUrl = computed(() =>
  sprite.value === null
    ? null
    : catalogueScatterSpriteUrl(props.speciesKey, props.representation, sprite.value.content_digest),
);

const isGlobal = computed(() => props.zoom === "global");

/**
 * ⛔ **A sprite that fails to load must not render as a catalogue with six loci in it.**
 *
 * This is the same rule as `app.js:4604` — *"a sequence panel that fails silently is one a reader
 * will read as 'this genome has nothing here', which is a different claim and a false one"* — and it
 * is sharper here, because the dots draw perfectly well over blank ground. A reader looking at six
 * specks on an empty square has been told, wordlessly, that the catalogue contains six loci.
 *
 * ⚠ Three states, never two: `pending` is not `failed`, and on a warm cache it lasts no frames at
 * all — which is why the whole picture is not withheld behind a spinner.
 */
const spriteStatus = ref<"pending" | "ready" | "failed">("pending");
watch(spriteUrl, () => {
  spriteStatus.value = "pending";
});

/**
 * ⛔ **The legend names what is ON the picture, and the two zooms draw different subsets** — "these
 * loci" needs a measured cosine, "whole catalogue" needs a medoid position, and a locus can have one
 * without the other. A legend row for a locus the picture does not show is a claim the picture does
 * not support.
 */
const legend = computed(() => {
  const matrix = geometry.value.cosine_matrix;
  const drawn = isGlobal.value ? globalPoints.value : (fit.value?.points ?? []);
  return drawn.map((point) => ({
    label: point.label,
    displayName: point.displayName,
    product: point.product,
    colour: point.colour,
    isFocal: point.isFocal,
    // ⛔ Read at the point's own SLOT, not its position in the legend.
    cosine: point.isFocal ? null : (matrix?.[0]?.[point.slot] ?? null),
  }));
});

/** ⚠ Whether the reader's own locus is on the catalogue picture at all. */
const focalIsPlotted = computed(() =>
  globalPoints.value.some((point) => point.isFocal),
);

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

const globalNote = computed(() => {
  const drawn = sprite.value;
  if (drawn === null) return "";
  const label = REPRESENTATION_LABEL[props.representation];
  const method = props.projection?.method ?? "UMAP";
  return (
    `One ${method} over every locus's ${label} medoid, drawn as ${spriteCoverageSentence(drawn)}. ` +
    "Orientation only — it says where this locus sits among them, not how close these six are. " +
    "UMAP preserves local neighbourhoods, not global distance, so a gap on this picture is not a " +
    "distance, and there are no rings here for the same reason."
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

    <!-- ⚠ Its own wrapper class, because the representation strip sits right above it and a
         selector that could not tell them apart would read one for the other (`app.js:2735`). -->
    <div class="zooms">
      <button
        v-for="option in MAP_ZOOMS"
        :key="option"
        type="button"
        class="zoom map-zoom"
        :class="{ on: option === zoom }"
        :disabled="option === 'global' && sprite === null"
        :title="
          option === 'global' && sprite === null
            ? `no whole-catalogue picture was rendered for ${REPRESENTATION_LABEL[representation]}`
            : undefined
        "
        @click="emit('selectZoom', option)"
      >{{ MAP_ZOOM_LABEL[option] }}</button>
    </div>

    <!-- ── whole catalogue ─────────────────────────────────────────────────────────────────── -->
    <svg
      v-if="isGlobal && sprite && spriteUrl && spriteStatus !== 'failed'"
      class="map-figure map-figure-global"
      :viewBox="`0 0 ${DRAWN_SIZE} ${DRAWN_SIZE}`"
      role="img"
      :aria-label="`${detail.locus.display_name} among ${sprite.plotted_locus_count.toLocaleString()} loci in ${REPRESENTATION_LABEL[representation]} space`"
    >
      <rect class="map-ground" x="0" y="0" :width="DRAWN_SIZE" :height="DRAWN_SIZE" />
      <!-- ⛔ The sprite is a COVERAGE mask — flat black with a varying alpha — because the server
           does not know the viewer's theme and two baked sprites are two artifacts that can
           disagree. `--map-sprite-invert: 1` under a dark theme turns the dust light and leaves the
           alpha alone. ⚠ Inline, not in a stylesheet: the default must be right with no CSS loaded
           at all, and jsdom can read an inline style where it can read no computed one — the same
           rule as the track's block widths (`app.js:1198`). -->
      <image
        class="map-sprite"
        :href="spriteUrl"
        x="0"
        y="0"
        :width="DRAWN_SIZE"
        :height="DRAWN_SIZE"
        style="filter: invert(var(--map-sprite-invert, 0))"
        @load="spriteStatus = 'ready'"
        @error="spriteStatus = 'failed'"
      />
      <!-- ⚠ The dots are drawn while the dust is still LOADING, deliberately. Withholding them
           until `load` fires would be the more literal reading of "never show six specks on an empty
           square" — but `load` on an `<image>` is an event we do not control, and a browser that
           does not fire it would then draw no dots at all, permanently. The caption below covers
           the pending frame; a browser quirk must cost a sentence, not the picture. Only an explicit
           `error` suppresses, and it suppresses the whole figure. -->
      <circle
        v-for="point in [...globalPoints].reverse()"
        :key="`global-${point.label}`"
        class="map-dot"
        :class="{ 'is-focal': point.isFocal }"
        :cx="point.x"
        :cy="point.y"
        :r="point.isFocal ? 11 : 8.5"
        :fill="point.colour"
      />
    </svg>
    <!-- ⛔ A sentence, never an empty frame: an empty frame reads as "there is nothing out there".
         ⚠ And the two sentences are two: *never rendered* is a fact about the catalogue, *did not
         load* is a fact about this request, and a reader can act on only one of them. -->
    <p v-else-if="isGlobal && sprite" class="muted" role="alert">
      The catalogue picture did not load, so this locus's place among
      {{ sprite.plotted_locus_count.toLocaleString() }} is not being shown.
    </p>
    <p v-else-if="isGlobal" class="muted">
      No whole-catalogue picture for {{ REPRESENTATION_LABEL[representation] }} — its projection was
      never rendered.
    </p>

    <!-- ── these loci ──────────────────────────────────────────────────────────────────────── -->
    <svg
      v-else-if="fit"
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

    <!-- ⚠ Said out loud rather than left as an absent dot: on a picture whose whole job is "where
         am I", a missing focal dot is the one thing a reader cannot infer from what is drawn. -->
    <!-- ⚠ The pending frame, said out loud rather than left as six dots on empty ground. On a warm
         cache this never renders; on a cold one it is the difference between "still arriving" and
         "this is the whole catalogue". -->
    <p v-if="isGlobal && sprite && spriteStatus === 'pending'" class="muted">
      Loading the catalogue picture…
    </p>

    <p v-if="isGlobal && sprite && !focalIsPlotted" class="muted">
      This locus has no {{ REPRESENTATION_LABEL[representation] }} medoid, so it is not on this
      picture — only its neighbours are.
    </p>

    <!-- ⚠ The caption goes with the figure. Left up after an error it describes a picture that is
         not there — "drawn as all 17,531 loci" beside a blank space. -->
    <p
      v-if="isGlobal ? sprite && spriteStatus !== 'failed' : fit"
      class="muted"
    >{{ isGlobal ? globalNote : nearNote }}</p>
  </div>
</template>
