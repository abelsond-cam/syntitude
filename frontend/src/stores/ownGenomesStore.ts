/**
 * "View your own genomes" — the reader's own list, and which step of the dialog is showing.
 *
 * ⭐ **A sketch, and it says so.** Accounts, saving, the BakRep download and the forward pass are not
 * built (David, 2026-09-22): the dialog opens on a page that says accounts and login will be
 * required, and the genomes that can actually be shown were placed in advance. Nothing here is
 * uploaded — the file is read in the browser — and nothing is saved, so it is gone on reload. That
 * keeps the design of record's "no login, no accounts, no user writes" intact.
 *
 * ⛔ **Absolute, never a toggle** — the same rule as the walk direction and every open/closed flag in
 * this app: a toggle called from two places lands back where it started while both call sites
 * believe it moved.
 *
 * ⚠ **A list that failed to load is not an empty list.** The modelled-genome lists decide whether a
 * reader's accession is "already modelled", so when the fetch fails the dialog says the check could
 * not be made rather than implying the genome is new.
 */

import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { fetchGenomes } from "@/api/client";
import type { Failure } from "@/api/result";
import { parseAccessionList, type AccessionLine, type AccessionList } from "@/lib/parseAccessionList";

/** The three steps, in the order a reader meets them. */
export const DIALOG_STEPS = ["account", "add", "yours"] as const;
export type DialogStep = (typeof DIALOG_STEPS)[number];

/** How many modelled genomes one catalogue can hold before this check stops being worth it. */
const MODELLED_LIMIT = 1000;

/**
 * What one line of the reader's file turns out to be. The parser decides the first two; the rest
 * need the catalogue.
 */
export type LineOutcome =
  | { readonly kind: "not-an-accession" }
  | { readonly kind: "repeat" }
  /** One of the 100 genomes this species' model was built from: the anchor box already shows it. */
  | { readonly kind: "modelled-here" }
  /** Modelled, but in the other species' catalogue. */
  | { readonly kind: "modelled-elsewhere"; readonly speciesKey: string; readonly scientificName: string }
  /** A BioSample we cannot place yet — the part of the service that is still to be built. */
  | { readonly kind: "to-be-completed" }
  /** The modelled list did not load, so no claim is made about this accession. */
  | { readonly kind: "unchecked" };

export interface SpeciesRoster {
  readonly key: string;
  readonly scientificName: string;
}

export const useOwnGenomesStore = defineStore("ownGenomes", () => {
  const isOpen = ref(false);
  const step = ref<DialogStep>("account");

  const fileName = ref<string | null>(null);
  const list = ref<AccessionList | null>(null);

  /** The modelled genomes of each species, once loaded. A species missing here was never asked for. */
  const modelledBySpecies = ref<Record<string, readonly string[]>>({});
  const rosterNames = ref<Record<string, string>>({});
  const rosterFailure = ref<Failure | null>(null);
  const isLoadingRosters = ref(false);

  const lines = computed<readonly AccessionLine[]>(() => list.value?.lines ?? []);

  function open(next: DialogStep = "account"): void {
    step.value = next;
    isOpen.value = true;
  }

  function close(): void {
    isOpen.value = false;
  }

  function showStep(next: DialogStep): void {
    step.value = next;
  }

  /** The reader's file, parsed. ⚠ `content` is the text — the file itself never leaves the browser. */
  function setFile(name: string, content: string): void {
    fileName.value = name;
    list.value = parseAccessionList(content);
  }

  function clearFile(): void {
    fileName.value = null;
    list.value = null;
  }

  /**
   * Load every published species' modelled genomes, so an accession can be told apart from one the
   * model already holds — including one that belongs to the OTHER species' page.
   */
  async function loadRosters(species: readonly SpeciesRoster[]): Promise<void> {
    isLoadingRosters.value = true;
    rosterFailure.value = null;
    const answers = await Promise.all(
      species.map(async (entry) => ({
        entry,
        result: await fetchGenomes(entry.key, "", { limit: MODELLED_LIMIT }),
      })),
    );
    const loaded: Record<string, readonly string[]> = {};
    const names: Record<string, string> = {};
    for (const { entry, result } of answers) {
      if (!result.ok) {
        rosterFailure.value = result;
        continue;
      }
      loaded[entry.key] = result.value.genomes.map((genome) => genome.sample_id);
      names[entry.key] = entry.scientificName;
    }
    modelledBySpecies.value = loaded;
    rosterNames.value = names;
    isLoadingRosters.value = false;
  }

  /** What to say about one line, on the page for `speciesKey`. */
  function outcomeFor(line: AccessionLine, speciesKey: string | null): LineOutcome {
    if (line.kind !== "biosample") return { kind: line.kind };
    const here = speciesKey === null ? undefined : modelledBySpecies.value[speciesKey];
    if (here?.includes(line.accession)) return { kind: "modelled-here" };
    for (const [key, roster] of Object.entries(modelledBySpecies.value)) {
      if (key === speciesKey) continue;
      if (roster.includes(line.accession)) {
        return {
          kind: "modelled-elsewhere",
          speciesKey: key,
          scientificName: rosterNames.value[key] ?? key,
        };
      }
    }
    // ⚠ Only once every roster is in can "not modelled" be said at all.
    if (rosterFailure.value !== null || Object.keys(modelledBySpecies.value).length === 0) {
      return { kind: "unchecked" };
    }
    return { kind: "to-be-completed" };
  }

  return {
    isOpen,
    step,
    fileName,
    list,
    lines,
    modelledBySpecies,
    rosterFailure,
    isLoadingRosters,
    open,
    close,
    showStep,
    setFile,
    clearFile,
    loadRosters,
    outcomeFor,
  };
});
