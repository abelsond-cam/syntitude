<script setup lang="ts">
/**
 * One Pfam family, as a chip that links to the record a reader following a domain actually wants.
 *
 * ⭐ **InterPro over Pfam**: the integrated entry is preferred, and a family with no integrated
 * entry falls back to the Pfam one. `""` is the absence to test for — never a URL fragment.
 *
 * ⚠ **An unresolved accession still renders.** The reference resolves every accession the response
 * mentions, so a miss means the join failed — and a chip that vanished would say the locus has no
 * such domain, which is a different and false claim. It shows the bare accession instead.
 */
import { computed } from "vue";

import type { PfamFamilyReference } from "@/api/types";
import { pfamEntryUrl } from "@/lib/evidenceVocabulary";

const props = defineProps<{
  accession: string;
  /** The resolved family, or `undefined` where the reference had no row for it. */
  family?: PfamFamilyReference | undefined;
}>();

const label = computed(() => {
  const short = props.family?.short_name ?? "";
  return short === "" ? props.accession : short;
});

const href = computed(() => pfamEntryUrl(props.accession, props.family?.interpro_accession ?? ""));

/** Accession, what it is, and its InterPro id — the hover, assembled from what is actually there. */
const title = computed(() => {
  const family = props.family;
  if (family === undefined) return props.accession;
  const what = family.interpro_name !== "" ? family.interpro_name : family.description;
  const parts = [props.accession];
  if (what !== "") parts.push(what);
  const suffix = parts.join(" — ");
  return family.interpro_accession === "" ? suffix : `${suffix} · ${family.interpro_accession}`;
});
</script>

<template>
  <a
    class="chip pfam"
    :href="href"
    :title="title"
    target="_blank"
    rel="noopener noreferrer"
  >{{ label }}</a>
</template>
