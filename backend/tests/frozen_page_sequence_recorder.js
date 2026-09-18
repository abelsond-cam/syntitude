/* Record the frozen page's Sequence tab — the "before" side of parity suite T6.
 *
 * ⭐ **A reference recorder, not a test.** It runs the published `app.js`'s own sequence code over the
 * committed `.nseq` + `.loci` files and prints what the tab SHOWED, field by field. Nothing here
 * asserts anything: a recorder with an opinion would bake today's behaviour into the oracle by
 * editing rather than by measuring. `test_sequence_parity.py` does the comparing.
 *
 * Usage:  node frozen_page_sequence_recorder.js <render|booted> <request.json | ->
 * Prints one JSON document on stdout.
 *
 * Two modes, because they answer two different questions:
 *
 * - **`render`** — one genome, any number of its loci. The Sequence-tab functions are LIFTED OUT of
 *   `app.js` by name (the precedent is `nuna/tests/js/check_real_nseq.js`) and `seqGene` itself is
 *   called for every copy `genesAtLocus` returns, then read back out of the DOM it built. This is what
 *   makes a sweep over a million genes affordable: booting the whole page per locus redraws the
 *   track, the card and the map every time.
 *   ⛔ **Nothing is re-implemented.** The flank orientation — which end, reverse-complemented or
 *   not — is the exact thing T6 exists to check, so it must come from the page's `seqGene`, never
 *   from a second reading of it here. The only loop written here is `renderSequence`'s own
 *   `hits.forEach(seqGene(ST, j, k + 1, hits.length))`, one line, and `booted` mode proves it.
 *   Also returned: the decoded gene table, contig names and `.loci` for EVERY gene of the genome,
 *   which is what lets the default suite compare every gene's placement even where it renders only
 *   a sample.
 *
 * - **`booted`** — the whole page, exactly as `nuna/tests/js/boot.js` boots it (its `dom_shim.js`, the
 *   real payload, a `fetch` stub serving the real `.nseq`/`.loci`), anchored through the Sequence
 *   tab's own box and walked by URL hash. Slow, so used for a sample — and it is what proves `render`
 *   mode draws exactly what the page draws, including the "has no gene here" answer, which is
 *   `renderSequence`'s and not `seqGene`'s.
 *
 * ⚠ Sequences are reported as `{length, digest, head}` — sha1 truncated to 16 hex characters, and
 * the first 12 bases — rather than in full: a whole species is ~1 GB of DNA text and the comparison
 * needs identity, not the letters. The Python side digests its own strings the same way.
 */
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const [mode, requestPath] = process.argv.slice(2);
// `-` reads the request from stdin, which is how the suite calls it: no request file to clean up.
const request = JSON.parse(fs.readFileSync(requestPath === "-" ? 0 : requestPath, "utf8"));
const APP_SOURCE = fs.readFileSync(request.app_js, "utf8");
const PAYLOAD_TEXT = fs.readFileSync(request.payload, "utf8");
const PAYLOAD = JSON.parse(PAYLOAD_TEXT);
const LABELS = PAYLOAD.nodes.label.map(String);

/* ---- lifting code out of the shipped file, by name ---------------------------------------------- */

/** `    function NAME(` … its matching brace. Four spaces: the body of `window.nunaBoot`. */
function liftFunction(name) {
    const at = APP_SOURCE.indexOf(`\n    function ${name}(`);
    if (at < 0) throw new Error(`function ${name} not found in ${request.app_js}`);
    return APP_SOURCE.slice(at + 1, closingBrace(APP_SOURCE.indexOf("{", at)) + 1);
}

/** `    var NAME = …;` — up to the first `;` outside any bracket or string. */
function liftVar(name) {
    const at = APP_SOURCE.indexOf(`\n    var ${name} =`);
    if (at < 0) throw new Error(`var ${name} not found in ${request.app_js}`);
    let depth = 0,
        quote = null;
    for (let k = at + 1; k < APP_SOURCE.length; k++) {
        const ch = APP_SOURCE[k];
        if (quote) {
            if (ch === "\\") k++;
            else if (ch === quote) quote = null;
        } else if (ch === '"' || ch === "'") quote = ch;
        else if ("([{".includes(ch)) depth++;
        else if (")]}".includes(ch)) depth--;
        else if (ch === ";" && depth === 0) return APP_SOURCE.slice(at + 1, k + 1);
    }
    throw new Error(`var ${name} did not terminate`);
}

function closingBrace(open) {
    let depth = 0,
        quote = null;
    for (let k = open; k < APP_SOURCE.length; k++) {
        const ch = APP_SOURCE[k];
        if (quote) {
            if (ch === "\\") k++;
            else if (ch === quote) quote = null;
        } else if (ch === '"' || ch === "'" || ch === "`") quote = ch;
        else if (ch === "{") depth++;
        else if (ch === "}" && --depth === 0) return k;
    }
    throw new Error("unbalanced braces");
}

/* ---- the smallest DOM `seqGene` can build into ------------------------------------------------- */
// ⚠ Only what `el`, `seqBlock`, `copyBtn`, `seqPre`, `statRow` and `seqGene` touch. Anything else the
// page starts calling must throw here rather than be guessed at — hence no catch-all proxy.
class MiniNode {
    constructor(tag) {
        this.tagName = String(tag).toUpperCase();
        this.children = [];
        this.className = "";
        this._text = "";
        this.attrs = {};
        this.listeners = {};
    }
    appendChild(child) {
        this.children.push(child);
        return child;
    }
    get textContent() {
        return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text;
    }
    set textContent(v) {
        this.children = [];
        this._text = String(v);
    }
    setAttribute(k, v) {
        this.attrs[k] = String(v);
    }
    addEventListener(type, fn) {
        (this.listeners[type] = this.listeners[type] || []).push(fn);
    }
}
class MiniText {
    constructor(text) {
        this._text = String(text);
        this.children = [];
        this.className = "";
        this.tagName = "#text";
    }
    get textContent() {
        return this._text;
    }
}

/* ---- reading a rendered `.seq-gene` back out --------------------------------------------------- */
// Shared by both modes, so `booted` and `render` are read by ONE reader and can only differ in what
// the page drew.
const hasClass = (node, cls) => String(node.className || "").split(/\s+/).includes(cls);
const kids = (node, cls) => (node.children || []).filter((c) => hasClass(c, cls));
const firstDeep = (node, cls) => {
    for (const c of node.children || []) {
        if (hasClass(c, cls)) return c;
        const hit = firstDeep(c, cls);
        if (hit) return hit;
    }
    return null;
};

function digestOf(sequence) {
    if (sequence === null) return null;
    return {
        length: sequence.length,
        digest: crypto.createHash("sha1").update(sequence).digest("hex").slice(0, 16),
        head: sequence.slice(0, 12),
    };
}

/** The bases a `seqPre` block DISPLAYS, with its own position gutter removed. */
function shownBases(pre) {
    return pre.textContent
        .split("\n")
        .map((line) => line.replace(/^\s*\d+ {2}/, ""))
        .join("");
}

function readSeqGene(wrap, gcPct) {
    const heading = kids(wrap, "seq-copy-h")[0];
    const stats = [];
    for (const group of kids(kids(wrap, "seq-stats")[0], "seq-stat")) {
        const [dt, dd] = group.children;
        stats.push([dt.textContent, dd.textContent]);
    }
    const edge = kids(wrap, "seq-edge")[0];
    const blocks = {};
    let shownCds = null;
    for (const block of kids(wrap, "seq-block")) {
        const kind = String(block.className).split(/\s+/)[1];
        const pre = firstDeep(block, "seq-pre");
        const note = kids(block, "seq-note")[0];
        const bases = pre ? shownBases(pre) : null;
        if (kind === "cds") shownCds = bases;
        blocks[kind] = {
            heading: firstDeep(block, "seq-bh").children[0].textContent,
            note: note ? note.textContent : null,
            // "None in the assembly." — the page's own words for an empty block, kept verbatim
            none: kids(block, "seq-none").map((n) => n.textContent)[0] ?? null,
            sequence: digestOf(bases),
        };
    }
    return {
        copy_heading: heading ? heading.textContent : null,
        stats,
        edge: edge ? edge.textContent : null,
        blocks,
        // ⭐ The page's OWN `gcPct`, applied to the CDS string the page DISPLAYS. It prints this number
        // to one decimal; carrying it at full precision is what lets "GC computed on the same string the
        // page shows" be an exact comparison rather than a rounding argument.
        gc_of_shown_cds: shownCds === null ? null : gcPct(shownCds),
    };
}

/* ---- render mode: the page's own seqGene, called directly -------------------------------------- */
function liftSequenceCode() {
    const vars = ["SEQ", "FLANK", "COMP", "CODONS", "CODON_IDX", "INITIATORS"].map(liftVar);
    const fns = [
        "el",
        "utf8",
        "decodeNseq",
        "baseAt",
        "contigSpan",
        "rc",
        "translate",
        "gcPct",
        "genesAtLocus",
        "seqPre",
        "copyBtn",
        "seqBlock",
        "statRow",
        "seqGene",
    ].map(liftFunction);
    const context = {
        // `SEQ` reads `P.meta.seq`, so the page's flank width is the payload's and not a constant here.
        P: { meta: PAYLOAD.meta },
        document: {
            createElement: (tag) => new MiniNode(tag),
            createTextNode: (text) => new MiniText(text),
        },
        TextDecoder,
        Uint8Array,
        Uint32Array,
        Int32Array,
        Float64Array,
        DataView,
        JSON,
        Math,
        String,
        Array,
        Error,
    };
    vm.createContext(context);
    vm.runInContext(
        ['"use strict";', ...vars, ...fns, "globalThis.LIFTED = { decodeNseq, genesAtLocus, seqGene, gcPct, FLANK };"].join(
            "\n",
        ),
        context,
        { filename: "app.js (lifted Sequence functions)" },
    );
    return context.LIFTED;
}

function readBinary(file) {
    const b = fs.readFileSync(file);
    return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

function render() {
    const page = liftSequenceCode();
    const sample = request.sample;
    const ST = page.decodeNseq(readBinary(path.join(request.seq_dir, `${sample}.nseq`)));
    // Exactly as `withSeq` does it: the `.loci` file IS an Int32Array, one entry per `.nseq` gene.
    ST.loci = new Int32Array(readBinary(path.join(request.seq_dir, `${sample}.loci`)));

    const labelToIndex = new Map(LABELS.map((label, i) => [label, i]));
    let loci;
    if (request.labels === null) {
        loci = [...new Set(Array.from(ST.loci).filter((i) => i >= 0))].sort((a, b) => a - b);
    } else {
        loci = request.labels.map((label) => {
            if (!labelToIndex.has(label)) throw new Error(`label ${label} is not in the payload`);
            return labelToIndex.get(label);
        });
    }

    const rendered = [];
    for (const i of loci) {
        const hits = page.genesAtLocus(ST, i);
        hits.forEach((j, k) => {
            const record = readSeqGene(page.seqGene(ST, j, k + 1, hits.length), page.gcPct);
            record.label = LABELS[i];
            record.locus_index = i;
            // The `.nseq` row IS `flat_index` (its schema's contract). Never displayed, but it is the
            // gene's identity, and ρ > 1 needs one.
            record.flat_index = j;
            rendered.push(record);
        });
        if (!hits.length) rendered.push({ label: LABELS[i], locus_index: i, absent: true });
    }

    const n = ST.head.n_genes;
    return {
        recorded_from: request.app_js,
        payload_schema: PAYLOAD.schema ?? null,
        flank: page.FLANK,
        genome: {
            sample: ST.head.sample,
            n_genes: n,
            contig_names: ST.head.cname,
            contig_lengths: ST.head.clen,
            ambiguous_runs: ST.head.ambiguous.length,
            // Every gene, not only the rendered ones: word 0..3 of the gene table and its locus index.
            start: Array.from({ length: n }, (_, j) => ST.genes[4 * j]),
            end: Array.from({ length: n }, (_, j) => ST.genes[4 * j + 1]),
            contig_index: Array.from({ length: n }, (_, j) => ST.genes[4 * j + 2]),
            flags: Array.from({ length: n }, (_, j) => ST.genes[4 * j + 3]),
            locus_index: Array.from(ST.loci),
        },
        rendered,
    };
}

/* ---- booted mode: the whole page, driven as a reader drives it --------------------------------- */
async function booted() {
    const { makeDom } = require(request.dom_shim);
    const document = makeDom(PAYLOAD_TEXT);
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
    // The page's only network call, answered from the committed files — 404 for anything absent, as
    // `boot.js` does, so "no file" and "no gene" can never render alike.
    const fetchStub = (url) => {
        const file = path.join(request.seq_dir, path.basename(String(url)));
        if (!fs.existsSync(file)) return Promise.resolve({ ok: false, status: 404 });
        const buffer = readBinary(file);
        return Promise.resolve({ ok: true, status: 200, arrayBuffer: () => Promise.resolve(buffer) });
    };
    const sandbox = {
        fetch: fetchStub,
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
        Uint32Array,
        Float64Array,
        DataView,
        TextDecoder,
        Promise,
        Error,
        atob,
        isNaN,
        parseInt,
        parseFloat,
        encodeURIComponent,
        decodeURIComponent,
        setTimeout: (fn) => fn(),
        location,
        window: {
            addEventListener: (t, fn) => ((listeners[t] = listeners[t] || []).push(fn), undefined),
            open: () => {},
            location,
        },
    };
    sandbox.window.document = document;
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(APP_SOURCE, sandbox, { filename: "app.js" });
    sandbox.window.nunaBoot(JSON.parse(document.getElementById("payload").textContent));

    const $ = (id) => document.getElementById(id);
    // The fetch stub resolves at once, so one macrotask drains `withSeq`'s promise chain.
    const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
    const { gcPct } = liftSequenceCode();

    const tab = document.querySelectorAll(".view-tabs > .view-tab").filter((b) => b.textContent === "Sequence")[0];
    if (!tab) throw new Error("the page drew no Sequence tab");
    tab.dispatch("click");
    await flush();

    const box = $("seq-anchor-genome");
    let anchored = null;
    const visits = [];
    for (const [sample, label] of request.visits) {
        location.hash = "#" + label;
        await flush();
        if (anchored !== sample) {
            box.value = sample;
            box.dispatch("input");
            const hit = $("seq-anchor-results")
                .querySelectorAll(".anchor-hit")
                .filter((h) => h.children[0] && h.children[0].textContent === sample)[0];
            if (!hit) throw new Error(`the anchor box offered no ${sample}`);
            hit.dispatch("click");
            await flush();
            anchored = sample;
        }
        const body = $("seq-body");
        const head = body.querySelector(".seq-head");
        const err = body.querySelector(".seq-err");
        visits.push({
            sample,
            label,
            hash: location.hash,
            head: head ? head.textContent : null,
            error: err ? err.textContent : null,
            genes: body.querySelectorAll(".seq-gene").map((wrap) => readSeqGene(wrap, gcPct)),
        });
    }
    return { recorded_from: request.app_js, payload_schema: PAYLOAD.schema ?? null, visits };
}

(async () => {
    const out = mode === "render" ? render() : mode === "booted" ? await booted() : null;
    if (out === null) throw new Error(`unknown mode ${mode} — expected render or booted`);
    process.stdout.write(JSON.stringify(out));
})();
