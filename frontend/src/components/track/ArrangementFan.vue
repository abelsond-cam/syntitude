<script setup lang="ts">
/**
 * The fan joining the focal gene to the arrangements offered under it (`app.js::drawArrFan`).
 *
 * The neighbourhoods are choices for THAT ONE LOCUS, and the full-width row the page used to have did
 * not say so — it read as a property of the track (David, 2026-08-23). The curves say it.
 *
 * ⚠ Measured from live positions, because the track scrolls sideways under a panel that does not: the
 * parent calls `redraw()` on every track scroll, resize and redraw. The arithmetic is in
 * `lib/arrangementFan`, where a test can reach it.
 */
import { ref } from "vue";

import { NO_FAN, type Fan, arrangementFan } from "@/lib/arrangementFan";

const fan = ref<Fan>(NO_FAN);

/**
 * Recompute from the DOM as it is now. `host` is the `.arr-wrap` the fan is drawn in; `frame` holds
 * the track, where the focal block lives.
 */
function redraw(host: HTMLElement | null, frame: HTMLElement | null): void {
  const block = frame?.querySelector(".slot.focal .block");
  const scroller = frame?.querySelector(".track-scroll") ?? null;
  const options = host ? [...host.querySelectorAll<HTMLElement>(".arr-opt")] : [];
  if (!host || !block) {
    fan.value = NO_FAN;
    return;
  }
  fan.value = arrangementFan(
    block.getBoundingClientRect(),
    host.getBoundingClientRect(),
    options.map((option) => ({ rect: option.getBoundingClientRect(), isOn: option.classList.contains("on") })),
    scroller ? scroller.getBoundingClientRect() : null,
  );
}

defineExpose({ redraw });
</script>

<template>
  <svg
    id="arr-fan"
    class="arr-fan"
    aria-hidden="true"
    focusable="false"
    :width="fan.width"
    :height="fan.height"
  >
    <!-- ⛔ The published fan NEVER RENDERED. Its rule pins `.arr-fan` at `height: 0` and the script set
         only the height ATTRIBUTE, which CSS overrides — and an <svg> whose height is 0 is not drawn at
         all, `overflow: visible` notwithstanding (measured on the live page: four paths, a 0 px box,
         nothing on screen). The rebuilt page gives the fan a FIXED row (app.css, appended section):
         fixed, because a height measured from the options would push the options down, and the next
         redraw would measure the row it had just moved and grow again, on every scroll. -->
    <path v-for="(curve, index) in fan.curves" :key="index" class="fan-line" :class="{ on: curve.isOn }" :d="curve.d" />
  </svg>
</template>
