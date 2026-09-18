<script setup lang="ts">
/**
 * The Sequence tab with its anchor box — mounted a SECOND time, because naming a genome is the
 * precondition for everything below it: without one there is no sequence to show, only a cluster to
 * average. Anchoring here moves the track too; it is the same anchor.
 */
import { storeToRefs } from "pinia";

import type { LocusDetailResponse } from "@/api/types";
import AnchorGenomeBox from "@/components/anchor/AnchorGenomeBox.vue";
import SequenceTab from "@/components/sequence/SequenceTab.vue";
import { useGeneSequenceStore } from "@/stores/geneSequenceStore";

defineProps<{ detail: LocusDetailResponse; speciesKey: string }>();

const sequence = useGeneSequenceStore();
const { response, status, lastFailure, sampleId } = storeToRefs(sequence);
</script>

<template>
  <div>
    <AnchorGenomeBox :species-key="speciesKey" placement="sequence" />
    <div id="seq-body" class="seq-body">
      <SequenceTab
        :display-name="detail.locus.display_name"
        :locus-label="detail.locus.label"
        :sample-id="sampleId"
        :response="response"
        :status="status"
        :failure-detail="lastFailure?.detail ?? null"
        @retry="sequence.load()"
      />
    </div>
  </div>
</template>
