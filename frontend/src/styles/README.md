# `styles/` — the published page's stylesheet, ported whole

`app.css` is nuna's `src/nuna/tl/locus_browser/app.css` — the stylesheet the live static site serves —
copied **byte for byte**, with one section appended at the bottom ("ADDED FOR THE REBUILT PAGE") for the
things the published page could never do: wait for a response, fail to get one, or draw the map in SVG.
A diff against the original therefore shows exactly what the rebuild changed.

## ⛔ Why it is global, not `<style scoped>`

The plan hoped to split it per component, and that is still the direction. But the published sheet
styles **across what are now component boundaries** — `.track .slot.focal .marg i`, `.arr-wrap
.arr-notes`, `.pop .alt` — and `scoped` rewrites every selector to match only its own component's
elements. Scoping it would silently drop every one of those rules, and the page would still render —
just wrong, with nothing to say so. Split it only rule by rule, moving a rule into a component when
every element it matches is rendered by that component.

## ⚠ Keep the inline widths

Neighbour-slot widths and the sprite tint are set **inline** in the components, not here: jsdom loads
no stylesheet and computes no layout, so an inline style is the only version of them any test can see
(`app.js:1198`). Moving either into this file blanks the assertions that check them.
