# `styles/` — the published page's stylesheet, ported whole

`app.css` is nuna's `src/nuna/tl/locus_browser/app.css` — the stylesheet the live static site serves —
copied **byte for byte**, with one section appended at the bottom ("ADDED FOR THE REBUILT PAGE") for the
things the published page could never do — wait for a response, or fail to get one — and for the design
changes David has made since the port, each dated (the mark in the instrument bar and the shorter search
box, 2026-09-22). **Change the page by adding to that section, never by editing above it:** a diff against
the original then shows exactly what the rebuild changed.

⚠ **The exception is a section the published sheet itself rewrote**, and the rule is then to RE-PORT it
rather than to patch around it. On 2026-09-24 the neighbourhood map and the medoid geometry card went
upstream and the similarity card replaced them, so `.map-tabs` / `.zooms` / `.map-key` / `.map-figure` and
the null strip's density bars were deleted here and `.sim-views` / `.sim-key` / `.fbox` taken in their
place — **including two measured fixes a patch would have missed**: `.pair` widened to `116px 1fr 54px`
because "nearest other cluster" did not fit at 88px, and `.tile` became a flex column because "within
cluster · Bacformer" wraps where "synteny A5" did not. What remains divergent in the ported region is
only what this app has that the published page does not: the `--projected` tokens and `.sym-vote`.

## ⛔ Why it is global, not `<style scoped>`

The plan hoped to split it per component, and that is still the direction. But the published sheet
styles **across what are now component boundaries** — `.track .slot.focal .marg i`, `.arr-wrap
.arr-notes`, `.pop .alt` — and `scoped` rewrites every selector to match only its own component's
elements. Scoping it would silently drop every one of those rules, and the page would still render —
just wrong, with nothing to say so. Split it only rule by rule, moving a rule into a component when
every element it matches is rendered by that component.

## ⚠ Keep the inline widths

Neighbour-slot widths are set **inline** in the component, not here: jsdom loads no stylesheet and
computes no layout, so an inline style is the only version of them any test can see (`app.js:1198`).
Moving them into this file blanks the assertions that check them.
