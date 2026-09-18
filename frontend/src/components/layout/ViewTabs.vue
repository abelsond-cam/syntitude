<script setup lang="ts">
/**
 * The strip that switches the four views of one locus. Its OWN class, `view-tab`, for the reason
 * app.css records beside the map and zoom strips: a selector that can reach more than one strip will
 * eventually be read as naming the wrong one.
 */
import { VIEW_TABS, type ViewId } from "@/stores/viewTabStore";

defineProps<{ view: ViewId }>();
const emit = defineEmits<{ show: [view: ViewId] }>();
</script>

<template>
  <div id="view-tabs" class="view-tabs" role="tablist">
    <button
      v-for="tab in VIEW_TABS"
      :key="tab.id"
      type="button"
      class="view-tab"
      :class="{ on: tab.id === view }"
      role="tab"
      :aria-selected="tab.id === view ? 'true' : 'false'"
      @click="emit('show', tab.id)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
