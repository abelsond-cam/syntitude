import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // ⚠ The Vue plugin is needed HERE as well as in `vite.config.ts`: this config replaces that one
  // rather than extending it, and without the plugin a `.vue` import fails as "invalid JS syntax"
  // — which reads as a broken component rather than a missing build step.
  plugins: [vue()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    globals: true,
    // `lib/`, `api/` and `stores/` are pure and need no DOM. The component suites declare `jsdom`
    // per-file with a docblock, so a pure test never pays for an environment it does not use.
    environment: "node",
    include: ["src/**/*.test.ts", "tests/**/*.test.ts"],
  },
});
