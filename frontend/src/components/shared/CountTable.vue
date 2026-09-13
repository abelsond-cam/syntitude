<script setup lang="ts" generic="Row extends CountRow">
/**
 * A table of counts over one denominator, with a share bar — `app.js:3306`.
 *
 * ⭐ **The component owns the last two columns.** The caller supplies the descriptive cells through
 * the `cells` slot and a heading for each; the count, the bar and the percentage are appended here,
 * against one `total`. The published page passed `["genes", "share"]` in with the rest, which let a
 * caller supply the headings and the cells in different orders.
 *
 * ⭐ **Generic over the row**, so the caller's own row type reaches the slot. Without it every cell
 * in every caller needs a cast back from `CountRow` — and a cast is exactly where a wrong field
 * stops being a compile error.
 */
import { type CountRow, shareBarWidthPx, shareOf } from "./countTable";
import { sharePercent } from "@/lib/formatting";

defineProps<{
  /** The descriptive headings. `genes` and `share` are appended by this component. */
  headings: readonly string[];
  rows: readonly Row[];
  /**
   * ⛔ The denominator every share is taken over — the locus's member-gene count, not the sum of
   * the rows. Summing the rows would print 100 % on a table that is a top-N cut of something bigger.
   */
  total: number;
}>();

defineSlots<{ cells(props: { row: Row }): unknown }>();
</script>

<template>
  <div class="tw">
    <table>
      <thead>
        <tr>
          <th v-for="heading in headings" :key="heading">{{ heading }}</th>
          <th class="n">genes</th>
          <th class="n">share</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key">
          <slot name="cells" :row="row" />
          <td class="n share">
            {{ row.count }}
            <!-- inline width, deliberately — see `countTable.ts` -->
            <i :style="{ width: `${shareBarWidthPx(row.count, total)}px` }" />
          </td>
          <td class="n">{{ sharePercent(shareOf(row.count, total)) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
