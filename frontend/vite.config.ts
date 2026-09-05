import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// ⛔ NO absolute origin and NO hardcoded base path anywhere in the app. The service is
// institution-only first — probably served under a subpath — and public later, from a different
// origin. Both come from build-time config so that neither is a code change:
//   VITE_API_BASE_URL   where the API lives   (default: same origin, `/api/v1`)
//   VITE_PUBLIC_BASE    where the app is served from (default: `/`)
// A literal `https://…` or `/syntitude/…` compiled into a component is exactly the thing that
// makes the second deployment a rewrite instead of an environment variable.
export default defineConfig(({ mode }) => ({
  base: process.env.VITE_PUBLIC_BASE ?? "/",
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // Dev only. In every deployed configuration the API is reached at `VITE_API_BASE_URL`, and this
  // proxy does not exist. Spread rather than `proxy: undefined`, which `exactOptionalPropertyTypes`
  // rightly refuses: an absent key and a key holding `undefined` are different things.
  ...(mode === "development"
    ? { server: { proxy: { "/api": { target: "http://localhost:5000", changeOrigin: true } } } }
    : {}),
}));
