/**
 * The entry point. One app, one store instance, one stylesheet.
 *
 * ⚠ The stylesheet is imported HERE and is global, not split into `<style scoped>` per component.
 * It is the published page's `app.css` ported whole, and it styles across what are now component
 * boundaries (`.track .slot.focal`, `.arr-wrap .arr-notes`) — scoping it would silently drop every
 * one of those rules. See `src/styles/README.md`.
 */
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import "./styles/app.css";

createApp(App).use(createPinia()).mount("#app");
