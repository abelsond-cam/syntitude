import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { failure, success } from "@/api/result";
import type { GeneSequenceResponse, LocusDetailResponse } from "@/api/types";

import { useAnchorGenomeStore } from "./anchorGenomeStore";
import { useGeneSequenceStore } from "./geneSequenceStore";
import { useLocusNavigationStore } from "./locusNavigationStore";

const fetchLocus = vi.hoisted(() => vi.fn());
const fetchGeneSequence = vi.hoisted(() => vi.fn());
// ⚠ A PARTIAL mock: `anchorQuery` must stay real, because it is the one place the anchor's
// kind becomes a query parameter and a stub would hide a projected genome being fetched as
// `anchor=` — which 404s and reads on the page as "this genome has nothing here".
vi.mock("@/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/client")>()),
  fetchLocus, fetchGeneSequence,
}));

function locusDetail(label: string): LocusDetailResponse {
  return {
    locus: { label, gene_count: 100 } as LocusDetailResponse["locus"],
    annotations: {},
    uniref50_families: [],
    arrangements: {
      listed: [],
      total: 0,
      arrangements_not_listed: 0,
      members_in_arrangements_not_listed: 0,
      members_without_a_neighbourhood: 0,
      membership_is_complete: true,
    },
    anchor: { is_anchored: false, arrangement_ranks: [], kind: null, projected_copies: [] },
    offsets: [],
    intergenic_gaps: [],
    pfam_reference: {},
    neighbour_display_rows: [],
    resolved_neighbour_count: 0,
  };
}

function sequenceResponse(sampleId: string, label: string, count = 1): GeneSequenceResponse {
  return {
    genome: { sample_id: sampleId },
    locus: { label },
    genes: Array.from({ length: count }, (_unused, index) => ({ flat_index: index })) as never,
  };
}

async function drawLocus(label: string) {
  const navigation = useLocusNavigationStore();
  navigation.setSpecies("ecoli");
  fetchLocus.mockResolvedValueOnce(success(locusDetail(label)));
  await navigation.navigateTo(label);
  await nextTick();
}

beforeEach(() => {
  setActivePinia(createPinia());
  fetchLocus.mockReset();
  // ⚠ Anchoring re-asks for the locus on screen (the anchored response differs), so every
  // `setAnchor` below issues a locus fetch too. Answer it with the same locus rather than leaving
  // the mock to return `undefined`, which would fail inside the navigation store instead of here.
  fetchLocus.mockImplementation(async (_species: string, label: string) => success(locusDetail(label)));
  fetchGeneSequence.mockReset();
});

describe("⭐ it needs a genome, and will not pick one", () => {
  it("asks for nothing while no genome is anchored or chosen", async () => {
    await drawLocus("1");
    const store = useGeneSequenceStore();
    store.setOpen(true);
    await nextTick();
    expect(store.sampleId).toBeNull();
    expect(fetchGeneSequence).not.toHaveBeenCalled();
  });

  it("⭐ defaults to the ANCHORED genome — the reader's own choice", async () => {
    // Having picked a genome to anchor the track to, being shown a different genome's DNA would be
    // a quiet substitution.
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA1", "1")));
    store.setOpen(true);
    await nextTick();
    expect(fetchGeneSequence).toHaveBeenCalledWith("ecoli", "SAMEA1", "1", expect.anything());
  });

  it("an explicit choice BEATS the anchor, and clearing it falls back", async () => {
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    store.selectGenome("SAMEA9");
    expect(store.sampleId).toBe("SAMEA9");
    store.selectGenome(null);
    expect(store.sampleId).toBe("SAMEA1");
  });
});

describe("⛔ the key is the PAIR — either half changing invalidates the answer", () => {
  it("re-asks when the locus changes under an open tab", async () => {
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA1", "1")));
    store.setOpen(true);
    await nextTick();
    await nextTick();

    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA1", "2")));
    await drawLocus("2");
    await nextTick();
    expect(fetchGeneSequence).toHaveBeenCalledTimes(2);
    expect(store.response?.locus.label).toBe("2");
  });

  it("⛔ re-asks when the GENOME changes and the locus does not", async () => {
    // The half a locus-keyed store would miss — and it would leave one genome's DNA on screen
    // labelled with another genome's name.
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA1", "1")));
    store.setOpen(true);
    await nextTick();
    await nextTick();

    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA9", "1")));
    store.selectGenome("SAMEA9");
    await nextTick();
    await nextTick();
    expect(fetchGeneSequence).toHaveBeenCalledTimes(2);
    expect(store.response?.genome.sample_id).toBe("SAMEA9");
  });

  it("⚠ discards the previous answer the moment the pair changes", async () => {
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA1", "1")));
    store.setOpen(true);
    await nextTick();
    await nextTick();
    store.setOpen(false);

    await drawLocus("2");
    await nextTick();
    // ⛔ Not left showing under a new locus — one genome's bases under another locus's heading is
    // the worst thing this panel could do.
    expect(store.response).toBeNull();
    expect(fetchGeneSequence).toHaveBeenCalledTimes(1);
  });
});

describe("⛔ an empty gene list is an ANSWER, and a failure is not", () => {
  it("holds an empty list as a ready response", async () => {
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    fetchGeneSequence.mockResolvedValueOnce(success(sequenceResponse("SAMEA1", "1", 0)));
    store.setOpen(true);
    await nextTick();
    await nextTick();
    expect(store.status).toBe("ready");
    expect(store.response?.genes).toEqual([]);
    expect(store.lastFailure).toBeNull();
  });

  it("keeps a failure as a failure, with no response at all", async () => {
    await drawLocus("1");
    useAnchorGenomeStore().setAnchor("SAMEA1");
    const store = useGeneSequenceStore();
    fetchGeneSequence.mockResolvedValueOnce(failure("server", "contig not in the file"));
    store.setOpen(true);
    await nextTick();
    await nextTick();
    expect(store.status).toBe("failed");
    expect(store.response).toBeNull();
    expect(store.lastFailure?.detail).toBe("contig not in the file");
  });
});
