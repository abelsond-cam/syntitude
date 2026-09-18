<script setup lang="ts">
/** The EggNOG tab — COG, GO and EC/KEGG across every member gene, fetched when the tab opens. */
import { storeToRefs } from "pinia";

import type { LocusDetailResponse } from "@/api/types";
import FunctionTab from "@/components/function/FunctionTab.vue";
import { useFunctionBlockStore } from "@/stores/functionBlockStore";

defineProps<{ detail: LocusDetailResponse }>();

const functionBlock = useFunctionBlockStore();
const { block, status, lastFailure } = storeToRefs(functionBlock);
</script>

<template>
  <FunctionTab
    :display-name="detail.locus.display_name"
    :locus-label="detail.locus.label"
    :block="block"
    :status="status"
    :failure-detail="lastFailure?.detail ?? null"
    @retry="functionBlock.load()"
  />
</template>
