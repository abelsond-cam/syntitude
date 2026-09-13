<script setup lang="ts">
/**
 * **Sequence diversity and Bakta annotations — ONE card, deliberately.**
 *
 * ⭐ They were two, and the second largely restated the first: UniRef50 is the sequence fact and the
 * Bakta name is *derived from it*, so a locus's families and its names are one table, not two lists
 * in two boxes. That separation is what hid `ybeF` (David, 2026-08-19) — its families split 63/33
 * and its symbols 63/35, in different cards, and the correspondence between them had to be guessed.
 * The join ships, so a row is a statement about its own genes.
 *
 * The Pfam verdict rides here for the same reason: it is a verdict about *these families*, and it
 * had a whole card whose visible content was the accession chips this table already carries.
 *
 * ⛔ **Both verdicts are READ, never re-derived.** `app.js:3208` — the page once re-derived the Pfam
 * class by a different rule and disagreed with the audit on 2 of 22,624 loci. *"A page that quotes
 * the report must not be able to contradict it, ever."*
 */
import { computed } from "vue";

import type { AnnotationEntry, Locus, PfamFamilyReference, UnirefFamily } from "@/api/types";
import { collapseTierVerdict, pfamAccessionsIn, pfamVerdict } from "@/lib/evidenceVocabulary";
import CountTable from "@/components/shared/CountTable.vue";
import PfamChip from "@/components/shared/PfamChip.vue";

const props = defineProps<{
  locus: Locus;
  families: readonly UnirefFamily[];
  /** Every gene symbol in use here, so the card can say how many names there are to reconcile. */
  symbols: readonly AnnotationEntry[];
  pfamReference: Readonly<Record<string, PfamFamilyReference>>;
  /** How many Pfam architectures are LISTED, which may be fewer than the locus has. */
  listedArchitectureCount: number;
}>();

const size = computed(() => props.locus.gene_count);

/**
 * ⛔ Claim with the MAJOR-family count — families holding ≥10 % of the labelled genes, the audit's
 * own bar. The table below lists every family including single-gene stragglers, and claiming with
 * that number would overstate the split at every locus with a long tail.
 */
const majorFamilyCount = computed(
  () => props.locus.uniref50.major_family_count || props.locus.uniref50.family_count,
);

const naming = computed(() => {
  const named = props.locus.named_gene_count;
  const unnamed = size.value - named;
  if (named === 0) {
    return {
      kind: "none" as const,
      text: `None of these ${size.value} genes carries a gene name — a coherent locus with no symbol at all.`,
    };
  }
  if (unnamed > 0) return { kind: "some" as const, unnamed, total: size.value };
  return { kind: "all" as const, text: `Every one of these ${size.value} genes already carries a gene name.` };
});

const tier = computed(() => collapseTierVerdict(props.locus.evidence.collapse_tier));
const verdict = computed(() =>
  pfamVerdict(props.locus.pfam.concordance_class, props.locus.pfam.annotated_gene_count),
);

/** Which optional columns the table earns — an empty column is worse than an absent one. */
const hasSymbols = computed(() => props.families.some((family) => family.modal_symbol));
const hasArchitectures = computed(() => props.families.some(contributesPfamColumn));

const headings = computed(() => {
  const out = ["UniRef50"];
  if (hasSymbols.value) out.push("gene name");
  out.push("modal Bakta product");
  if (hasArchitectures.value) out.push("Pfam");
  return out;
});

const rows = computed(() =>
  props.families.map((family) => ({
    key: family.uniref50_accession,
    count: family.gene_count,
    family,
    accessions: pfamAccessionsIn(family.modal_architecture),
    // ⚠ `null` is NOT MEASURED and shows no marker; `1` is measured agreement and shows none
    // either. Only a measured disagreement earns one, so the two absences collapse here rather
    // than in the template where a `> 1` on a null would read as false by accident.
    extraSymbolCount:
      family.distinct_symbol_count !== null && family.distinct_symbol_count > 1
        ? family.distinct_symbol_count - 1
        : null,
    // ⛔ Tested against null, never truthiness: a family where NO gene is annotated is the loudest
    // case and a `v-if` on the number would hide exactly that one.
    showsOwnCoverage:
      family.pfam_annotated_gene_count !== null &&
      family.pfam_annotated_gene_count < family.gene_count,
  })),
);

function unirefUrl(accession: string): string {
  return `https://www.uniprot.org/uniref/${encodeURIComponent(accession)}`;
}

/**
 * ⚠ `distinct_symbol_count` is a COUNT, not a list. The marker says how many and never invents the
 * others — showing a bare modal would let a family that is itself split across names read as
 * unanimous, which is the same mistake the two-card layout made.
 */
function symbolMarkerTitle(family: UnirefFamily): string {
  return (
    `${family.distinct_symbol_count} different gene names among this family's ` +
    `${family.gene_count} genes; ${family.modal_symbol} is the commonest`
  );
}

/** ⚠ A family earns the Pfam column if it has an architecture OR a measured coverage count. */
function contributesPfamColumn(family: UnirefFamily): boolean {
  return Boolean(family.modal_architecture) || family.pfam_annotated_gene_count !== null;
}

/**
 * ⛔ **Coverage is stated AS COVERAGE.** A gene with no Pfam domain is *missing evidence*, not
 * evidence of a different architecture, and reading the second as the first is the
 * "14 of 99 have different Pfam structures" misreading a bare domain count invites.
 */
const coverage = computed(() => {
  const annotated = props.locus.pfam.annotated_gene_count;
  if (annotated === null) return null;
  if (annotated === 0) {
    return (
      `None of these ${size.value} genes carries a Pfam-A domain — Pfam has no coverage here, ` +
      "so it can neither support nor contradict this locus."
    );
  }
  const architectures = props.locus.pfam.architecture_count;
  const head =
    annotated < size.value
      ? `${annotated} of ${size.value} genes carry a Pfam-A domain; the other ${size.value - annotated} ` +
        "carry none at all — absent annotation, not a competing architecture"
      : `All ${size.value} genes carry a Pfam-A domain`;
  // ⚠ The TRUE architecture count, which the top-N list on screen cannot show — so the card says
  // how many are listed whenever that is fewer.
  const listed =
    architectures > props.listedArchitectureCount ? ` (${props.listedArchitectureCount} listed)` : "";
  const tail =
    architectures > 1
      ? ` · ${architectures} architectures across the locus${listed}`
      : " · one architecture across the locus";
  return `${head}${tail}.`;
});
</script>

<template>
  <div class="card" :class="verdict ? `pf-${verdict.tone}` : null">
    <h2>Sequence diversity and Bakta annotations</h2>

    <p v-if="majorFamilyCount > 1" class="lede">
      UniRef50 files these genes under <b>{{ majorFamilyCount }} families</b> — each holding at least
      a tenth of the labelled genes. Nuna holds them as one locus.
    </p>
    <p v-else-if="families.length >= 1" class="lede">
      One UniRef50 family — this locus and the sequence family agree.
    </p>

    <p class="lede">
      <template v-if="naming.kind === 'some'">
        <b>{{ naming.unnamed }}</b> of {{ naming.total }} genes here carry no gene name. This locus
        names them <b>{{ locus.display_name }}</b>.
      </template>
      <template v-else>{{ naming.text }}</template>
    </p>

    <!-- Both verdicts on one row: how the members hold together by sequence, and what Pfam makes
         of them. -->
    <div v-if="tier || verdict" class="chip-row">
      <span v-if="tier" class="chip" :class="tier.tone">{{ tier.label }}</span>
      <span v-if="verdict" class="chip" :class="verdict.tone">{{ verdict.label }}</span>
    </div>
    <p v-if="tier && tier.note" class="muted">{{ tier.note }}</p>
    <p v-if="verdict" class="muted verdict-note">{{ verdict.note }}</p>

    <CountTable v-if="families.length" :headings="headings" :rows="rows" :total="size">
      <template #cells="{ row }">
        <td class="acc">
          <a
            class="acc-link"
            :href="unirefUrl(row.family.uniref50_accession)"
            :title="`${row.family.uniref50_accession} on UniProt`"
            target="_blank"
            rel="noopener noreferrer"
          >{{ row.family.uniref50_accession }}</a>
        </td>

        <td v-if="hasSymbols" class="fam-sym">
          <span class="fam-sym-in">
            <template v-if="row.family.modal_symbol">
              <span class="acc">{{ row.family.modal_symbol }}</span>
              <span
                v-if="row.extraSymbolCount !== null"
                class="alt-n"
                :title="symbolMarkerTitle(row.family)"
              >+{{ row.extraSymbolCount }}</span>
            </template>
            <span v-else class="none">—</span>
          </span>
        </td>

        <td>{{ row.family.modal_product || "—" }}</td>

        <td v-if="hasArchitectures" class="fam-pf">
          <span class="fam-pf-in">
            <template v-if="row.accessions.length">
              <PfamChip
                v-for="accession in row.accessions"
                :key="accession"
                :accession="accession"
                :family="pfamReference[accession]"
              />
            </template>
            <span v-else class="none">no domain</span>
            <!-- ⛔ `v-if` on a NUMBER would hide a measured zero — see `showsOwnCoverage`. -->
            <span v-if="row.showsOwnCoverage" class="fam-cov"
              >{{ row.family.pfam_annotated_gene_count }}/{{ row.family.gene_count }} annotated</span
            >
          </span>
        </td>
      </template>
    </CountTable>

    <p v-if="families.length" class="muted">
      A UniRef50 accession carries no name of its own, so each family is labelled by the commonest
      Bakta product and gene name among its members here<template v-if="symbols.length > 1"> —
      {{ symbols.length }} different gene names are in use across this one locus, the names to
      reconcile</template>. The clustering never saw UniRef50, Pfam, products or genomic context.
    </p>

    <p v-if="coverage" class="muted">{{ coverage }}</p>
  </div>
</template>
