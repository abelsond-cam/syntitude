"""Turn a pytest JUnit report into a GitHub job summary that says what did NOT run, and why.

⛔ Most of the backend suite SKIPS in CI, by design: the parity, API and ingest suites need the fully
loaded database (`BACATLAS_DATABASE_URL`), the cluster-artifact mirror, or `nuna` — a private repo —
and CI has none of the three. A bare green tick over that reads as "the parity suites passed in CI".
They did not, and cannot, run there. This summary puts the skip count first and names every skipped
module with its reason, so the tick can only be read as what it is.

Usage: ``python summarise_pytest_junit.py REPORT.xml >> "$GITHUB_STEP_SUMMARY"``. Stdlib only, so it
runs on the runner's own interpreter with nothing installed.
"""

from __future__ import annotations

import ast
import sys
from collections import Counter, defaultdict
from xml.etree import ElementTree


def _collection_skip_reason(text: str | None) -> str:
    """A module skipped at collection records ``('path', line, 'Skipped: reason')`` as its text."""
    try:
        _path, _line, reason = ast.literal_eval(text or "")
    except (ValueError, SyntaxError):
        return (text or "no reason recorded").strip()
    return str(reason).removeprefix("Skipped: ")


def summarise(report_path: str) -> str:
    """Render the markdown summary for one JUnit report."""
    root = ElementTree.parse(report_path).getroot()
    outcomes: dict[str, Counter] = defaultdict(Counter)
    reasons: dict[str, Counter] = defaultdict(Counter)
    collection_skipped: dict[str, str] = {}

    for case in root.iter("testcase"):
        module = case.get("classname") or ""
        skipped = case.find("skipped")
        if not module:
            # ⚠ A module skipped at COLLECTION appears once, under its own name, however many tests
            # it holds — they were never collected, so they are not in any count below.
            if skipped is not None:
                collection_skipped[case.get("name", "?")] = _collection_skip_reason(skipped.text)
            continue
        if case.find("failure") is not None:
            outcomes[module]["failed"] += 1
        elif case.find("error") is not None:
            outcomes[module]["error"] += 1
        elif skipped is not None:
            outcomes[module]["skipped"] += 1
            reasons[module][skipped.get("message", "no reason recorded")] += 1
        else:
            outcomes[module]["passed"] += 1

    total = Counter()
    for counts in outcomes.values():
        total.update(counts)
    ran = total["passed"] + total["failed"] + total["error"]
    collected = ran + total["skipped"]

    # pytest's own "N skipped" counts each whole-module skip as one; both parts are shown so the
    # header can be checked against the log line.
    skipped_all = total["skipped"] + len(collection_skipped)
    lines = [
        (
            f"## Backend tests — {total['passed']} passed · {skipped_all} skipped "
            f"({total['skipped']} tests + {len(collection_skipped)} whole modules) · "
            f"{total['failed']} failed · {total['error']} errors"
        ),
        "",
        (
            f"> ⚠ **{total['skipped']} of {collected} collected tests did not run here, and "
            f"{len(collection_skipped)} whole modules were never collected.** CI has no loaded database, "
            "no cluster-artifact mirror and no `nuna`, so the parity, API-endpoint and ingest suites "
            f"skip. **A green tick means the {ran} tests that can run without them passed — not that "
            "parity holds.** The parity suites run only where the loaded database is: the full suite on "
            "the Mac (`backend/README.md`, Tests)."
        ),
        "",
    ]

    skipped_modules = sorted(module for module, counts in outcomes.items() if counts["skipped"])
    if skipped_modules or collection_skipped:
        lines += ["### Skipped, and why", "", "| module | ran | skipped | reason |", "|---|---:|---:|---|"]
        for module, reason in sorted(collection_skipped.items()):
            lines.append(f"| `{module}` | 0 | whole module | {reason} |")
        for module in skipped_modules:
            counts = outcomes[module]
            ran_here = counts["passed"] + counts["failed"] + counts["error"]
            for index, (reason, count) in enumerate(reasons[module].most_common()):
                shown = f"`{module}`" if index == 0 else "″"
                lines.append(f"| {shown} | {ran_here if index == 0 else ''} | {count} | {reason} |")
        lines.append("")

    fully_run = sorted(m for m, c in outcomes.items() if not c["skipped"])
    if fully_run:
        lines += [
            "### Ran in full",
            "",
            ", ".join(f"`{m}` ({outcomes[m]['passed']})" for m in fully_run),
            "",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(summarise(sys.argv[1]))
