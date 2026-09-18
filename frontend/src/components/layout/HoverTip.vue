<script setup lang="ts">
/**
 * The page's own hover tooltip — one element, one delegated listener, `data-tip` on whatever wants one.
 *
 * ⭐ **Why not the browser's `title`** (`app.js`, "the hover tooltip", David 2026-08-21): a native
 * tooltip fires at the browser's discretion and was unreliable in exactly the way a reader notices.
 * The occupancy bars nest a described segment inside a described button, so sweeping a bar of eight
 * thin segments cancels the timer at every boundary and never lets it fire; and the track is rebuilt
 * on every arrangement change, so the element under a still cursor is replaced with no fresh pointer
 * event. This one switches AT ONCE between neighbouring tips once open, which is what makes a
 * segmented bar hoverable at all.
 *
 * ⚠ A tip that outlives what it points at is worse than none — the same rule as the popover — so it
 * hides on any pointerdown, on window blur and on any scroll.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";

/** Delay before the FIRST tip opens; switching between tips once one is open is immediate. */
const OPEN_DELAY_MS = 90;

const element = ref<HTMLDivElement | null>(null);
const lines = ref<string[]>([]);
const isHidden = ref(true);
const position = ref({ left: 0, top: 0 });

let owner: Element | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
let pointerX = 0;
let pointerY = 0;

function hide(): void {
  owner = null;
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
  isHidden.value = true;
}

function place(): void {
  const node = element.value;
  const width = node?.offsetWidth ?? 0;
  const height = node?.offsetHeight ?? 0;
  let left = pointerX + 14;
  let top = pointerY + 18;
  // Flip to the other side of the cursor rather than letting the tip run off the viewport.
  if (left + width > window.innerWidth - 8) left = Math.max(8, pointerX - 14 - width);
  if (top + height > window.innerHeight - 8) top = Math.max(8, pointerY - 12 - height);
  position.value = { left, top };
}

function show(target: Element): void {
  const text = target.getAttribute("data-tip");
  if (!text) return;
  lines.value = text.split("\n");
  isHidden.value = false;
  requestAnimationFrame(place);
}

function onPointerMove(event: PointerEvent): void {
  pointerX = event.clientX;
  pointerY = event.clientY;
  const target = event.target instanceof Element ? event.target.closest("[data-tip]") : null;
  if (target === null) {
    if (owner !== null) hide();
    return;
  }
  if (target === owner) {
    if (!isHidden.value) place();
    return;
  }
  const alreadyOpen = !isHidden.value;
  owner = target;
  if (timer !== null) clearTimeout(timer);
  if (alreadyOpen) {
    show(target);
    return;
  }
  timer = setTimeout(() => {
    timer = null;
    if (owner === target) show(target);
  }, OPEN_DELAY_MS);
}

onMounted(() => {
  document.addEventListener("pointermove", onPointerMove);
  document.addEventListener("pointerdown", hide);
  window.addEventListener("blur", hide);
  window.addEventListener("scroll", hide, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointermove", onPointerMove);
  document.removeEventListener("pointerdown", hide);
  window.removeEventListener("blur", hide);
  window.removeEventListener("scroll", hide, true);
});
</script>

<template>
  <div
    id="tip"
    ref="element"
    class="tip"
    role="tooltip"
    :hidden="isHidden"
    :style="{ left: `${position.left}px`, top: `${position.top}px` }"
  >
    <div v-for="(line, index) in lines" :key="index">{{ line }}</div>
  </div>
</template>
