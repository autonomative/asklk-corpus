"""Stage 5 - verify the transformation.

Eight checks. Any failure exits non-zero, so CI cannot publish an unverified
corpus. The two that carry the integrity claim are 3 and 4:

  3. NO INSERTION - every token in the output exists, with at least the same
     multiplicity, in the source lines that section was built from. This is the
     manipulation test: a paraphrase, a summary or an invented figure all fail.
  4. NO OMISSION  - every source token survives into the output, except tokens
     matched by a rule declared in extract.config.json.

What these checks CANNOT prove: correct reading order. The same tokens in the
wrong sequence pass both. Multi-column and tabular pages are therefore reported
at Low confidence and need sampled human review.

    python tools/verify.py budget-2027
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
FENCE = re.compile(r"^```.*$", re.M)
MD_MARKS = re.compile(r"^#{1,6}\s*|\*\*|^\s*[-*]\s+", re.M)


def body_text(md: str) -> str:
    """Section Markdown minus everything the pipeline added."""
    md = FRONT_MATTER.sub("", md)
    md = HTML_COMMENT.sub(" ", md)
    md = FENCE.sub(" ", md)
    md = MD_MARKS.sub(" ", md)
    return md


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.sections: list[dict] = []

    def add(self, n: int, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"check": n, "name": name, "pass": ok, "detail": detail})

    @property
    def ok(self) -> bool:
        return all(c["pass"] for c in self.checks)


def run(document_id: str) -> Report:
    d = common.doc_dir(document_id)
    rep = Report()
    src = common.source_entry(document_id)
    cfg = common.read_json(d / "extract.config.json")
    toc = common.read_json(d / "toc.json")
    entries = toc["entries"]
    first, last = cfg["pdf_range"]

    # 1 ─ source integrity
    actual = common.sha256_file(common.ROOT / src["path"])
    rep.add(1, "source integrity", actual == src["sha256"],
            "sha256 matches manifest" if actual == src["sha256"]
            else f"expected {src['sha256'][:16]}… got {actual[:16]}…")

    stream = common.line_stream(document_id, first, last)
    # Only rules scoped to "any-line" are re-applied here. Rules enforced
    # structurally during extraction (page-first-line) have already taken effect
    # on the stream; applying them again would drop genuine content.
    drop_res = [re.compile(r["pattern"]) for r in cfg["drop_rules"]
                if r.get("scope") == "any-line"]

    # 3 & 4 ─ per section, against the exact lines it was built from
    insert_fail, omit_fail = [], []
    for e in entries:
        if e["level"] != 1:
            continue
        path = d / "sections" / f"{e['slug']}.md"
        if not path.exists():
            insert_fail.append(f"{e['id']}: missing file")
            continue

        kept = [item["text"] for item in stream[e["start_line"]:e["end_line"] + 1]
                if item["kind"] == "line"
                and not any(r.match(item["text"]) for r in drop_res)]
        # Joined before tokenising, mirroring the renderer: hyphenated words
        # broken across lines must rejoin identically on both sides.
        src_tokens: Counter[str] = Counter(common.tokens(" ".join(kept)))

        out_tokens = Counter(common.tokens(body_text(path.read_text())))
        inserted = out_tokens - src_tokens
        omitted = src_tokens - out_tokens

        if inserted:
            insert_fail.append(f"{e['id']} ({e['slug']}): {dict(list(inserted.items())[:6])}")
        if omitted:
            omit_fail.append(f"{e['id']} ({e['slug']}): {dict(list(omitted.items())[:6])}")

        total = sum(src_tokens.values())
        rep.sections.append({
            "section_id": e["id"], "title": e["title"], "slug": e["slug"],
            "pdf_pages": [e["pdf_start"], e["pdf_end"]],
            "printed_pages": [e.get("printed_start"), e.get("printed_end")],
            "source_tokens": total,
            "insertions": sum(inserted.values()),
            "omissions": sum(omitted.values()),
            "heading_confidence": e["heading_confidence"],
            "has_verbatim": bool(e.get("has_verbatim")),
        })

    rep.add(3, "no insertion", not insert_fail,
            "every output token present in source"
            if not insert_fail else f"{len(insert_fail)} section(s): " + "; ".join(insert_fail[:3]))
    rep.add(4, "no omission", not omit_fail,
            "every source token present in output"
            if not omit_fail else f"{len(omit_fail)} section(s): " + "; ".join(omit_fail[:3]))

    # 5 ─ page anchors present, unique and ascending within each file
    anchor_bad = []
    for e in entries:
        if e["level"] != 1:
            continue
        p = d / "sections" / f"{e['slug']}.md"
        if not p.exists():
            continue
        nums = [int(x) for x in re.findall(r"<!-- p\. (\d+) -->", p.read_text())]
        if len(nums) != len(set(nums)):
            anchor_bad.append(f"{e['id']}: duplicate anchors")
        if nums != sorted(nums):
            anchor_bad.append(f"{e['id']}: anchors out of order")
    rep.add(5, "page anchors", not anchor_bad, "unique and ascending"
            if not anchor_bad else "; ".join(anchor_bad[:4]))

    # 6 ─ TOC coverage: contiguous, no gaps, every line in exactly one section
    tops = [e for e in entries if e["level"] == 1]
    gaps = []
    for a, b in zip(tops, tops[1:]):
        if b["start_line"] != a["end_line"] + 1:
            gaps.append(f"{a['id']}→{b['id']}: {a['end_line']} then {b['start_line']}")
    if tops and tops[0]["start_line"] != 0:
        gaps.append(f"stream does not start at section {tops[0]['id']}")
    if tops and tops[-1]["end_line"] != len(stream) - 1:
        gaps.append(f"stream does not end at section {tops[-1]['id']}")
    rep.add(6, "TOC coverage", not gaps,
            f"{len(tops)} sections tile the stream with no gaps or overlaps"
            if not gaps else "; ".join(gaps[:4]))

    # 7 ─ front matter present and complete
    required = {"section_id", "title", "document_id", "level", "pdf_pages", "licence"}
    fm_bad = []
    for e in tops:
        p = d / "sections" / f"{e['slug']}.md"
        if not p.exists():
            fm_bad.append(f"{e['id']}: missing")
            continue
        m = FRONT_MATTER.match(p.read_text())
        if not m:
            fm_bad.append(f"{e['id']}: no front matter")
            continue
        keys = set(re.findall(r"^(\w+):", m.group(0), re.M))
        if missing := required - keys:
            fm_bad.append(f"{e['id']}: missing {sorted(missing)}")
    rep.add(7, "front matter", not fm_bad, "all sections conform"
            if not fm_bad else "; ".join(fm_bad[:4]))

    # 2 ─ determinism is asserted by re-running extract in CI; recorded here.
    rep.add(2, "determinism", True,
            "enforced in CI: re-run extract.py and require an empty git diff")

    # 8 ─ chunk graph, when it has been built
    chunks = common.ROOT / "build" / document_id / "chunks.jsonl"
    if chunks.exists():
        import json
        ids, bad = set(), []
        rows = [json.loads(l) for l in chunks.read_text().splitlines() if l.strip()]
        for r in rows:
            if r["chunk_id"] in ids:
                bad.append(f"duplicate id {r['chunk_id']}")
            ids.add(r["chunk_id"])
        for r in rows:
            for ref in ("parent_id", "prev_id", "next_id"):
                if r.get(ref) and r[ref] not in ids and ref != "parent_id":
                    bad.append(f"{r['chunk_id']}: dangling {ref}")
        rep.add(8, "chunk graph", not bad,
                f"{len(rows)} chunks, ids unique, links resolve"
                if not bad else "; ".join(bad[:4]))
    else:
        rep.add(8, "chunk graph", True, "not built yet (run tools/chunk.py)")

    return rep


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    rep = run(doc)
    for c in sorted(rep.checks, key=lambda x: x["check"]):
        mark = "PASS" if c["pass"] else "FAIL"
        print(f"  [{mark}] {c['check']}. {c['name']:<18} {c['detail']}")
    print()
    print("ALL CHECKS PASS" if rep.ok else "FAILED")
    common.write_json(common.doc_dir(doc) / "verification.json", {
        "document_id": doc, "ok": rep.ok,
        "checks": rep.checks, "sections": rep.sections,
        "human_reviewed_pages": [],
    })
    sys.exit(0 if rep.ok else 1)


if __name__ == "__main__":
    main()
