# `frontend/` — the BacAtlas browser

Vue 3 + Pinia + Vite + TypeScript, over the read-only `/api/v1` contract. Design of record:
`docs/design/serving_from_a_database.md` in the `nuna` repo. Build order and status:
`PROJECT_STATE.md` §6 there. **Nothing in this directory carries a status block.**

```bash
npm install
npm test          # vitest
npm run typecheck # vue-tsc --noEmit
npm run dev       # vite, proxying /api to localhost:5001 (SYNTITUDE_DEV_API_TARGET overrides)
```

## ⛔ No absolute origin, and no hardcoded base path

The service is **institution-only first** — probably served under a subpath — and **public later**,
from a different origin. Both come from build-time config so that neither is a code change:

| variable | meaning | default |
|---|---|---|
| `VITE_API_BASE_URL` | where the API lives | same origin, `/api/v1` |
| `VITE_PUBLIC_BASE` | where the app is served from | `/` |

A literal `https://…` or `/bacatlas/…` compiled into a component is exactly what makes the second
deployment a rewrite instead of an environment variable.

⚠ **Under a subpath, set BOTH.** `VITE_API_BASE_URL` defaults to the origin-absolute `/api/v1`, so a
build with `VITE_PUBLIC_BASE=/bacatlas/` and no API base would ask the origin root for its data. The
Compose web image does this for you (`frontend/Dockerfile`: an empty `VITE_API_BASE_URL` becomes
`${VITE_PUBLIC_BASE}api/v1`, and nginx proxies that prefix). An empty value falls back to the default
(`request.ts` uses `||`), so leaving it blank is safe — but that default is the ORIGIN root, not the
subpath.

## `lib/` is built first, and it is where the bugs of record live

Pure functions, no DOM, no API, no store. Three modules, each one a rewrite risk named in the plan:

| module | the risk it exists against |
|---|---|
| `walkDirection.ts` | `go(i, sameStrand)` is **absolute, not a toggle**. `walkFlip = !walkFlip` mirrors twice: the first antiparallel step is right, the second inverted, and the track walks backwards *while rendering perfectly*. The module exports no toggle, and a test asserts the export list so one cannot be added quietly. |
| `slotSpaces.ts` | The **three slot spaces** are all integers 0..9 and all valid indices into the same array. An arrangement flip moves the gene but keeps the label; a walk flip moves both. Branded types make the substitution fail to compile — `vue-tsc` refuses `ObservedSlot === LabelSlot` outright. |
| `locusHashRoute.ts` | The hash is the **published page's hash**, so saved links keep working. A trailing `r` is the direction marker *only if what remains is itself a label*; the breadcrumb **retreats** rather than growing when Back fires `hashchange`. |

⚠ **`shadowedReverseRoutes` is a measurement, not a formality.** `#abcr` is ambiguous — locus
`abcr` forward, or locus `abc` reversed — and the encoding resolves it toward `abcr`, which leaves
`abc` reversed with no URL. Neither published catalogue can hit this, because labels are decimal
integers; that is a fact about today's naming and stops being true the moment a model labels loci by
gene symbol. Check it, do not assume it.

## Two rules that will otherwise be "cleaned up"

1. **Keep the inline `style.width` on the neighbour slot component.** jsdom computes no layout and
   the test harness loads no stylesheet, so an inline width is the only version of a block's size
   that any test can see. Roughly 40 DOM assertions depend on it. (`app.js:1198`.)
2. **Never `v-if` on a number.** `v-if="varianceScore"` is false for a *measured zero*, and a
   measured zero is the majority case — white on the track has to mean "identical in every genome",
   never "small". Test `!== null` explicitly.

## Looking at the page — `scripts/capture_page.mjs`

⭐ **Render it and look.** jsdom computes no layout and loads no stylesheet, so a whole class of defect
is invisible to every test here — and rendering the rebuilt page beside the frozen one found several:
gaps missing from the track, a switcher stacked down the page gutter, an enum printed where a product
belongs, and a fan the published page has never drawn. `scripts/capture_page.mjs` drives a headless
Chrome over the DevTools protocol (Node ≥ 22, no dependencies), runs a list of steps — navigate, run
JavaScript, emulate dark mode, screenshot a region — and prints the page's console errors and failed
requests at the end.

```bash
# the API on :5001 and `npm run dev` on :5173, then:
cat > /tmp/steps.json <<'JSON'
[
  { "url": "http://localhost:5173/?species=kp#1098", "settle": 3500 },
  { "eval": "document.querySelectorAll('.slot.gap').length + ' intergenic regions drawn'" },
  { "shot": "/tmp/kp-light.png", "h": 1300 },
  { "media": "dark" },
  { "shot": "/tmp/kp-dark.png", "h": 1300 },
  { "shot": "/tmp/kp-phone.png", "w": 390, "h": 1800 }
]
JSON
node scripts/capture_page.mjs /tmp/steps.json
```

The frozen page is the comparison: serve the repository root (`python3 -m http.server 8765` from it)
and point the same steps at `http://localhost:8765/kp.html#1098`.

