<script setup lang="ts">
/**
 * The page: header and search, the species strip, the track, four views of one locus, the footer.
 *
 * ⭐ **The URL carries two things and no more.** The species is a query parameter (`?species=kp`),
 * because switching species is a full navigation to a different catalogue — the published site made
 * it a different page. The locus is the published page's own HASH (`#2811`, `#2811r`), so the
 * browser's Back walks the trail and a saved link keeps working. The anchor, the tab, the popover
 * and the map representation are not places, and stay out (`lib/locusHashRoute.ts`).
 *
 * ⚠ **Hash ⇄ route sync goes one way at a time.** A click changes the route, and the route writes
 * the hash (a history entry, as `app.js::go` made one). Back changes the hash, and the hash asks the
 * navigation store — which, finding the route already there, does nothing. Comparing DECODED forms
 * is what stops the two echoing each other forever over a percent-encoded label.
 */
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, watch } from "vue";

import HoverTip from "@/components/layout/HoverTip.vue";
import SiteFooter from "@/components/layout/SiteFooter.vue";
import SiteHeader from "@/components/layout/SiteHeader.vue";
import SpeciesStrip from "@/components/layout/SpeciesStrip.vue";
import TrackPanel from "@/components/layout/TrackPanel.vue";
import ViewTabs from "@/components/layout/ViewTabs.vue";
import FunctionView from "@/components/views/FunctionView.vue";
import LocusEvidenceView from "@/components/views/LocusEvidenceView.vue";
import NavigatingView from "@/components/views/NavigatingView.vue";
import SequenceView from "@/components/views/SequenceView.vue";
import { useLocusNavigationStore } from "@/stores/locusNavigationStore";
import { useSpeciesCatalogueStore } from "@/stores/speciesCatalogueStore";
import { useViewTabStore } from "@/stores/viewTabStore";

const species = useSpeciesCatalogueStore();
const navigation = useLocusNavigationStore();
const tabs = useViewTabStore();
const { speciesList, catalogue, current, publishedSpecies, speciesKey } = storeToRefs(species);
const { drawable, hash } = storeToRefs(navigation);
const { view } = storeToRefs(tabs);

const SPECIES_PARAMETER = "species";

function decoded(text: string): string {
  try {
    return decodeURIComponent(text.replace(/^#/, ""));
  } catch {
    return text.replace(/^#/, "");
  }
}

/** Jump to a locus from search, a crumb, a chip or the footer — no direction of travel, so forward. */
function go(locusLabel: string): void {
  void navigation.navigateTo(locusLabel);
}

/** Open whatever the address bar names, or the catalogue's landing locus if it names nothing. */
async function openFromAddress(): Promise<void> {
  const opened = await navigation.openHash(window.location.hash);
  const landing = current.value?.landing_locus ?? null;
  if (!opened && landing !== null) await navigation.navigateTo(landing);
}

function onHashChange(): void {
  if (current.value === null) return;
  if (decoded(window.location.hash) === decoded(hash.value)) return;
  void openFromAddress();
}

watch(hash, (next) => {
  if (!next || decoded(next) === decoded(window.location.hash)) return;
  window.location.hash = next;
});

/**
 * ⭐ A species switch LEAVES this catalogue: a new address, a fresh page, nothing carried across —
 * exactly as the published picker did. The trail, the cache and the anchor all belong to one
 * catalogue, and a reload is the one reset that cannot forget any of them.
 */
function selectSpecies(nextSpeciesKey: string): void {
  if (nextSpeciesKey === speciesKey.value) return;
  const url = new URL(window.location.href);
  url.searchParams.set(SPECIES_PARAMETER, nextSpeciesKey);
  url.hash = "";
  window.location.assign(url.toString());
}

const pageTitle = computed(() =>
  current.value ? `${current.value.species.scientific_name} · Syntitude` : "Syntitude",
);
watch(pageTitle, (title) => {
  document.title = title;
});

onMounted(async () => {
  window.addEventListener("hashchange", onHashChange);
  await species.loadSpeciesList();
  const requested = new URL(window.location.href).searchParams.get(SPECIES_PARAMETER);
  const chosen =
    publishedSpecies.value.find((entry) => entry.key === requested)?.key ?? publishedSpecies.value[0]?.key;
  if (chosen === undefined) return;
  await species.selectSpecies(chosen);
  if (current.value !== null) await openFromAddress();
});

onBeforeUnmount(() => window.removeEventListener("hashchange", onHashChange));
</script>

<template>
  <HoverTip />
  <SiteHeader
    :species-key="speciesKey"
    :collection-genome-count="current?.pangenome.genome_count ?? null"
    @go="go"
  />
  <SpeciesStrip
    :species="publishedSpecies"
    :species-key="speciesKey"
    :catalogue="current"
    @select-species="selectSpecies"
  />

  <!-- ⛔ Each failure SAYS which thing failed; none of them renders as an empty catalogue. -->
  <section v-if="speciesList.status === 'failed'" class="wrap load-failure">
    <p class="pop-error" role="alert">The list of species did not load — {{ speciesList.failure.detail }}.</p>
  </section>
  <section v-else-if="speciesList.status === 'ready' && publishedSpecies.length === 0" class="wrap load-failure">
    <p class="lede">No species is published on this server yet.</p>
  </section>
  <section v-else-if="catalogue.status === 'failed'" class="wrap load-failure">
    <p class="pop-error" role="alert">This catalogue did not load — {{ catalogue.failure.detail }}.</p>
  </section>

  <template v-if="current !== null">
    <TrackPanel :species-key="speciesKey" :collection-genome-count="current.pangenome.genome_count" />

    <!-- Four views of one locus. They sit OUTSIDE the track panel because the track is common to all
         four — you navigate on it whichever view you are reading. -->
    <main class="views">
      <div class="wrap">
        <ViewTabs :view="view" @show="tabs.showView($event)" />
      </div>
      <section id="view-node" class="view-panel" role="tabpanel" aria-label="Syntolog Loci" :hidden="view !== 'locus'">
        <div class="wrap">
          <LocusEvidenceView v-if="drawable !== null" :detail="drawable" :catalogue="current" />
        </div>
      </section>
      <section
        id="view-navigating"
        class="view-panel"
        role="tabpanel"
        aria-label="Navigating Syntitude"
        :hidden="view !== 'navigating'"
      >
        <div class="wrap">
          <NavigatingView :examples="current.example_locus_rows" @go="go" />
        </div>
      </section>
      <section id="view-sequence" class="view-panel" role="tabpanel" aria-label="Sequence" :hidden="view !== 'sequence'">
        <div class="wrap">
          <SequenceView v-if="drawable !== null" :detail="drawable" :species-key="current.species.key" />
        </div>
      </section>
      <section id="view-eggnog" class="view-panel" role="tabpanel" aria-label="EggNOG" :hidden="view !== 'function'">
        <div class="wrap">
          <FunctionView v-if="drawable !== null" :detail="drawable" />
        </div>
      </section>
    </main>

    <SiteFooter :catalogue="current" @go="go" />
  </template>
</template>
