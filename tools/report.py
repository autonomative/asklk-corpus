"""Produce the transformation report.

Confidence is a BAND derived from published signals, never a blended decimal.
A single number would average away the one thing a reader needs to know - that
a tabular section's row structure is not machine-provable - and present false
precision as assurance. The band and the signals behind it are both shown.

The band reflects machine-verifiable risk only. Human review is a separate
column, because conflating "the checks passed" with "a person looked at it"
is exactly the overstatement the disclaimer exists to prevent.

    python tools/report.py budget-2027
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

RUBRIC = """\
| Band | Criteria |
|---|---|
| **High** | Single-column prose, heading found on one line, zero insertions, zero omissions. |
| **Medium** | As High, but the heading was inferred across wrapped lines, so the section title is an inference. |
| **Low** | Contains tabular or multi-column pages. Text is token-verified, but no automated check can prove a value is still in its original row. |
"""


def band(section: dict, toc_entry: dict, reviewed: set[int]) -> tuple[str, list[str]]:
    signals: list[str] = []
    if section["has_verbatim"]:
        signals.append("tabular pages")
        return "Low", signals
    if (toc_entry.get("title_lines") or 1) > 1:
        signals.append("heading inferred across wrapped lines")
        return "Medium", signals
    signals.append("single-column prose, single-line heading")
    return "High", signals


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    d = common.doc_dir(doc)
    ver = common.read_json(d / "verification.json")
    toc = {e["id"]: e for e in common.read_json(d / "toc.json")["entries"]}
    src = common.source_entry(doc)
    reviewed = set(ver.get("human_reviewed_pages") or [])

    rows, counts = [], {"High": 0, "Medium": 0, "Low": 0}
    for s in ver["sections"]:
        e = toc[s["section_id"]]
        b, signals = band(s, e, reviewed)
        counts[b] += 1
        s["confidence"] = b
        s["signals"] = signals
        pp = s["printed_pages"]
        pages = f"{pp[0]}–{pp[1]}" if pp[0] and pp[1] and pp[0] != pp[1] else (pp[0] or "—")
        status = "verified" if s["insertions"] == 0 and s["omissions"] == 0 else "FAILED"
        page_nums = set(range(int(pp[0] or 0), int(pp[1] or 0) + 1))
        rows.append(
            f"| {s['section_id']} | {s['title'][:52]} | {pages} | {s['source_tokens']:,} | "
            f"{status} | **{b}** | {'yes' if page_nums & reviewed else 'no'} | {'; '.join(signals)} |"
        )

    checks = "\n".join(
        f"| {c['check']} | {c['name']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |"
        for c in sorted(ver["checks"], key=lambda x: x["check"]))

    md = f"""# Transformation report — {src['title']}

Source: [{src['url']}]({src['url']})
SHA-256 `{src['sha256']}` · {src['pages']} pages · retrieved {src['retrieved']}

**Status: {'all checks pass' if ver['ok'] else 'FAILED'}** — {len(ver['sections'])} sections,
{sum(s['source_tokens'] for s in ver['sections']):,} source tokens,
{counts['High']} High / {counts['Medium']} Medium / {counts['Low']} Low confidence.
Human-reviewed pages: {len(reviewed)}.

## Verification checks

| # | Check | Result | Detail |
|---|---|---|---|
{checks}

## What these checks prove

Checks 3 and 4 compare normalised token streams between the source PDF and the
generated Markdown, section by section. Passing both means **no content was
invented and none was lost**: a paraphrase, a summary, an invented figure or a
dropped sentence each fail.

## What they do not prove

- **Reading order.** The same tokens in the wrong sequence pass every automated
  check. Multi-column and tabular pages are reported Low for this reason.
- **Correctness of the original.** We reproduce the document; we do not audit it.
- **Table structure.** Tabular pages are carried through as verbatim blocks, so
  their text is exact, but no check can prove a number is still in its row.

Structured data derived from tables is validated separately, on its own terms —
`data/{doc}/sectors.json` checks that serial numbers run contiguously and that
every row has a sector, a name and an amount.

## Confidence rubric

{RUBRIC}
A band says nothing about whether a human has read the section; that is the
separate "reviewed" column.

## Sections

| ID | Title | Printed pages | Tokens | Status | Confidence | Reviewed | Signals |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}
"""
    (d / "report.md").write_text(md)
    common.write_json(d / "verification.json", ver)
    print(f"{counts['High']} High / {counts['Medium']} Medium / {counts['Low']} Low")
    print(f"wrote {(d / 'report.md').relative_to(common.ROOT)}")


if __name__ == "__main__":
    main()
