# `frontend/` — the Syntitude browser

Vue 3 + Pinia + Vite + TypeScript, over the read-only `/api/v1` contract. Design of record:
`docs/design/serving_from_a_database.md` in the `nuna` repo. Build order and status:
`PROJECT_STATE.md` §6 there. **Nothing in this directory carries a status block.**

```bash
npm install
npm test          # vitest
npm run typecheck # vue-tsc --noEmit
npm run dev       # vite, proxying /api to localhost:5000
```

## ⛔ No absolute origin, and no hardcoded base path

The service is **institution-only first** — probably served under a subpath — and **public later**,
from a different origin. Both come from build-time config so that neither is a code change:

| variable | meaning | default |
|---|---|---|
| `VITE_API_BASE_URL` | where the API lives | same origin, `/api/v1` |
| `VITE_PUBLIC_BASE` | where the app is served from | `/` |

A literal `https://…` or `/syntitude/…` compiled into a component is exactly what makes the second
deployment a rewrite instead of an environment variable.

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
