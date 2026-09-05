/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Where the API lives. ⛔ Defaults to the **same origin** at `/api/v1` — never an absolute URL in
   * source. The institutional host comes first, probably under a subpath; the public origin later.
   */
  readonly VITE_API_BASE_URL?: string;
  /** Where the app itself is served from. Consumed by `vite.config.ts`, not by application code. */
  readonly VITE_PUBLIC_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
