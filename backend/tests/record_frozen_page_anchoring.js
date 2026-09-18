/* Record the frozen page's ANCHORING answers — the "before" side of parity suite T4.
 *
 * ⭐ **A reference recorder, not a test.** It boots the published `app.js` under `node:vm` exactly as
 * nuna's `tests/js/record_walks.js` does, then asks the page — for every genome it can anchor — which
 * arrangement ranks that genome carries at every locus, whether each locus's membership is complete, and
 * how many loci the anchor dropdown says each genome carries. It asserts nothing: a recorder with an
 * opinion bakes today's behaviour into the oracle by editing rather than by measuring.
 *
 * Usage: node record_frozen_page_anchoring.js <app.js> <dom_shim.js> <payload.json> [drive.json]
 * Prints one JSON object on stdout.
 *
 * ⛔ **HOW THE PAGE'S OWN FUNCTIONS ARE REACHED, and why this is still the page.** `anchorRanks`,
 * `membershipComplete` and `genomeCounts` are closures inside `nunaBoot`, and `anchorRanks` reads the
 * module-level `anchorG`. Driving them through the DOM would mean one render per (genome, locus) — 1.75 M
 * renders over the ecoli grid. So ONE statement is appended inside `nunaBoot`, directly after the page
 * mounts its own anchor controls, that hands those four functions out by reference:
 *
 *     window.__frozenAnchoring = { anchorRanks, membershipComplete, genomeCounts, setAnchor };
 *
 * Nothing in any function body is altered — they close over the same `anchorG`, `ARR`, `GID` and `GIDOFF`
 * the page renders from, and the anchor is SET through the page's own `setAnchor`, which also redraws the
 * track. The injection point must occur exactly once or this exits non-zero, so an edited `app.js`
 * cannot silently receive the hook somewhere it never runs.
 *
 * ⭐ **And the hook is checked against the RENDERED page, not trusted.** Given `drive.json` —
 * `{"pairs": [[locus_index, genome_ordinal], …], "queries": [q, …]}` — each pair is also driven the way a
 * reader would: the anchor is chosen by typing into the anchor box and clicking the matching row (the real
 * `input` → `anchorSearch` → click → `setAnchor` path), the locus is opened by its URL hash, and the
 * recorder reads back the ⚓-marked arrangement buttons and the anchor line's sentence. Each query is typed
 * into the same box and the rows the dropdown renders are read back. The per-genome counts are likewise
 * read off the dropdown's own "N loci" labels. The consuming test requires the DOM and the hook to agree.
 *
 * ⚠ The sandbox is duplicated from `record_walks.js` on purpose, as that file duplicates `boot.js`: the
 * recorders stay independent of the ~130 page tests that boot through `boot.js`.
 */

const fs = require("node:fs");
const vm = require("node:vm");
const crypto = require("node:crypto");

const [appPath, domShimPath, payloadPath, drivePath] = process.argv.slice(2);
if (!appPath || !domShimPath || !payloadPath) {
    process.stderr.write(
        "usage: node record_frozen_page_anchoring.js <app.js> <dom_shim.js> <payload.json> [drive.json]\n",
    );
    process.exit(2);
}
const { makeDom } = require(domShimPath);

/* ⛔ The one injection. Anchored on the page's own mounting of its second anchor box, which runs at boot
   on every payload — a hook placed after an early return would silently never run. */
const INJECTION_POINT =
    'mountAnchor("seq-anchor-wrap", "seq-anchor-genome", "seq-anchor-results");';
const HOOK =
    "\n    window.__frozenAnchoring = { anchorRanks: anchorRanks, membershipComplete: membershipComplete," +
    " genomeCounts: genomeCounts, setAnchor: setAnchor };\n";

const appSource = fs.readFileSync(appPath, "utf8");
const occurrences = appSource.split(INJECTION_POINT).length - 1;
if (occurrences !== 1) {
    process.stderr.write(
        `the injection point occurs ${occurrences} times in ${appPath}, not once — refusing to guess where ` +
            "the page's anchor state lives\n",
    );
    process.exit(3);
}
const hooked = appSource.replace(INJECTION_POINT, INJECTION_POINT + HOOK);

const payloadText = fs.readFileSync(payloadPath, "utf8");
const document = makeDom(payloadText);

const listeners = {};
const location = {
    _hash: "",
    get hash() {
        return this._hash;
    },
    set hash(v) {
        const next = String(v).startsWith("#") ? String(v) : "#" + v;
        if (next === this._hash) return;
        this._hash = next;
        (listeners.hashchange || []).forEach((fn) => fn());
    },
};

const sandbox = {
    // ⛔ No `fetch`: anchoring makes no request on the frozen page, so a stub could only hide one.
    document,
    console,
    JSON,
    Math,
    Object,
    Array,
    String,
    Number,
    Boolean,
    Set,
    Map,
    Int32Array,
    Int16Array,
    Uint8Array,
    Uint16Array,
    DataView,
    atob,
    isNaN,
    parseInt,
    parseFloat,
    encodeURIComponent,
    decodeURIComponent,
    setTimeout: (fn) => fn(),
    location,
    window: {
        addEventListener: (t, fn) => (
            (listeners[t] = listeners[t] || []).push(fn), undefined
        ),
        open: () => {},
        location,
    },
};
sandbox.window.document = document;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(hooked, sandbox, { filename: "app.js" });
const payload = JSON.parse(document.getElementById("payload").textContent);
sandbox.window.nunaBoot(payload);

const page = sandbox.window.__frozenAnchoring;
if (!page) {
    process.stderr.write("the hook did not run — nunaBoot returned before mounting its anchor boxes\n");
    process.exit(4);
}

const LABELS = payload.nodes.label;
const GENOMES = payload.meta.genomes;
const NLOCI = LABELS.length;

/* ── the per-genome counts, as the DROPDOWN renders them ──────────────────────────────────────────────
   Focusing the empty box lists every genome with `counts[k].toLocaleString() + " loci"`. Read back as
   digits only, so the locale's grouping separator cannot matter. */
const box = document.getElementById("anchor-genome");
const results = document.getElementById("anchor-results");
function hitsFor(value) {
    box.value = value;
    box.dispatch("input");
    return results.querySelectorAll(".anchor-hit").filter((node) => {
        return !String(node.className).split(" ").includes("clear");
    });
}
const renderedCounts = new Array(GENOMES.length).fill(null);
hitsFor("").forEach((hit) => {
    const spans = hit.children;
    const sample = spans[0].textContent;
    const ordinal = GENOMES.indexOf(sample);
    renderedCounts[ordinal] = Number(String(spans[1].textContent).replace(/[^0-9]/g, ""));
});

/* ── the whole grid, through the page's own functions ─────────────────────────────────────────────────
   For each genome, `setAnchor(k)` and then `anchorRanks(i)` at every locus. Emitted SPARSELY — an empty
   list is the absence of an entry — as one flat array per genome: `[i, n, r_1 … r_n, i, n, …]`. */
const ranksByGenome = [];
let recordedPairs = 0;
let multiRankPairs = 0;
for (let k = 0; k < GENOMES.length; k++) {
    page.setAnchor(k);
    const flat = [];
    for (let i = 0; i < NLOCI; i++) {
        const ranks = page.anchorRanks(i);
        if (!ranks.length) continue;
        flat.push(i, ranks.length);
        for (let r = 0; r < ranks.length; r++) flat.push(ranks[r]);
        recordedPairs++;
        if (ranks.length > 1) multiRankPairs++;
    }
    ranksByGenome.push(flat);
}
page.setAnchor(-1);

let complete = "";
for (let i = 0; i < NLOCI; i++) complete += page.membershipComplete(i) ? "1" : "0";

const functionCounts = Array.from(page.genomeCounts());

/* ── the DOM cross-check, pair by pair ────────────────────────────────────────────────────────────────── */
function anchorThroughTheControl(k) {
    const row = hitsFor(GENOMES[k]).find(
        (hit) => hit.children[0].textContent === GENOMES[k],
    );
    if (!row) return false;
    row.dispatch("click");
    return true;
}

function renderedAnchorState() {
    const options =
        document.getElementById("arrangements")?.querySelectorAll(".arr-opt") ?? [];
    const anchoredRanks = [];
    const shownRanks = [];
    options.forEach((node) => {
        // `#N` is `rank + 1` on the page; recorded as the 0-based rank so both sides compare one space.
        const rank = Number(node.querySelector(".arr-rank").textContent.replace("#", "")) - 1;
        shownRanks.push(rank);
        if (String(node.className).split(" ").includes("anchored")) anchoredRanks.push(rank);
    });
    const line = document.getElementById("arr-notes")?.querySelector(".arr-anchored") ?? null;
    return {
        option_ranks: shownRanks,
        anchored_option_ranks: anchoredRanks,
        anchor_line: line ? line.textContent : null,
        anchor_line_is_muted: line ? String(line.className).split(" ").includes("muted") : null,
    };
}

const drive = drivePath ? JSON.parse(fs.readFileSync(drivePath, "utf8")) : {};

/* What the dropdown LISTS for each query — `anchorSearch` as rendered, in the order it renders. */
const domQueries = (drive.queries || []).map((query) => ({
    query,
    listed: hitsFor(query).map((hit) => hit.children[0].textContent),
}));

const domPairs = [];
if (drive.pairs) {
    const pairs = drive.pairs;
    let anchoredTo = -2;
    for (const [i, k] of pairs) {
        if (k !== anchoredTo) {
            if (!anchorThroughTheControl(k)) {
                domPairs.push({ locus_index: i, genome_ordinal: k, error: "no dropdown row" });
                continue;
            }
            anchoredTo = k;
        }
        // ⚠ Cleared first: the hash setter fires nothing when the value is unchanged, so two pairs at
        // one locus would read the second off a render that never happened.
        location.hash = "";
        location.hash = "#" + LABELS[i];
        domPairs.push({ locus_index: i, genome_ordinal: k, ...renderedAnchorState() });
    }
}

process.stdout.write(
    JSON.stringify({
        recorded_from: "app.js",
        app_js_sha256: crypto.createHash("sha256").update(appSource).digest("hex"),
        payload_schema: payload.schema ?? null,
        payload_run_id: payload.meta?.run_id ?? null,
        // ⛔ Coverage, stated, so a recording of three loci cannot look like one of seventeen thousand.
        locus_count: NLOCI,
        genome_count: GENOMES.length,
        grid_pairs_evaluated: NLOCI * GENOMES.length,
        recorded_pairs: recordedPairs,
        multi_rank_pairs: multiRankPairs,
        genomes: GENOMES,
        anchor_ranks_by_genome: ranksByGenome,
        membership_complete: complete,
        genome_counts_from_function: functionCounts,
        genome_counts_from_dropdown: renderedCounts,
        dom_pairs: domPairs,
        dom_queries: domQueries,
    }) + "\n",
);
