"""Stage 3+4 - split by TOC and extract section Markdown.

Deterministic. No model is involved at any point: given the same PDF and the
same config this produces byte-identical output, which verification check 2
enforces.

One file per LEVEL-1 TOC entry, with level-2 entries as "##" headings inside
their parent. The plan called for a file per TOC entry; sub-sections share pages
with their parent, so giving each its own file would make page accounting
ambiguous for no retrieval benefit. The two-level hierarchy is preserved where
it is actually consumed - toc.json and the chunk graph.

Pages flagged tabular in the config are emitted as fenced verbatim blocks,
never reflowed into Markdown tables.

    python tools/extract.py budget-2027
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

L1 = re.compile(r"^(\d{1,2})\.\s+(\S.*)$")
L2 = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+(\S.*)$")
ANNEX = re.compile(r"^Annexure\s+([IVXL]+)\s*$", re.I)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10}
SALUTATION = re.compile(r"^(Honourable Speaker|Hon\. Speaker)\s*[,:]?\s*$", re.I)
ENDS_BLOCK = re.compile(r"[.:;?!]\s*$")


def yaml_escape(v: str) -> str:
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def front_matter(entry: dict, doc_meta: dict) -> str:
    rows = [
        ("section_id", yaml_escape(entry["id"])),
        ("title", yaml_escape(entry["title"])),
        ("document_id", yaml_escape(doc_meta["document_id"])),
        ("document_title", yaml_escape(doc_meta["title"])),
        ("level", str(entry["level"])),
        ("parent", yaml_escape(entry["parent"]) if entry["parent"] else "null"),
        ("prev", yaml_escape(entry["prev"]) if entry.get("prev") else "null"),
        ("next", yaml_escape(entry["next"]) if entry.get("next") else "null"),
        ("pdf_pages", f"[{entry['pdf_start']}, {entry['pdf_end']}]"),
        ("printed_pages", f"[{entry.get('printed_start') or 'null'}, "
                          f"{entry.get('printed_end') or 'null'}]"),
        ("detection", yaml_escape(entry["detection"])),
        ("heading_confidence", yaml_escape(entry["heading_confidence"])),
        ("verbatim_tables", "true" if entry.get("has_verbatim") else "false"),
        ("source_url", yaml_escape(doc_meta["url"])),
        ("source_sha256", yaml_escape(doc_meta["sha256"])),
        ("licence", '"CC0-1.0 (this transformation only)"'),
        ("disclaimer", '"Provided as-is with no warranty. Not legal, tax or '
                       'financial advice. Verify against the official publication."'),
    ]
    body = "\n".join(f"{k}: {v}" for k, v in rows)
    children = entry.get("children") or []
    if children:
        body += "\nchildren:\n" + "\n".join(f"  - {yaml_escape(c)}" for c in children)
    return f"---\n{body}\n---\n"


def render_section(entry: dict, stream: list[dict], cfg: dict, subs: list[dict]) -> str:
    """Render one section from its slice of the line stream."""
    verbatim = set(cfg["verbatim_pages"])
    heading = entry["title"]
    if entry.get("number"):
        heading = f"{entry['number']}. {heading}"
    elif entry["id"].startswith("A") and entry["id"] != "front":
        # Annexures are introduced by their own marker line in the source;
        # carry it into the heading so no token goes missing.
        roman = {v: k for k, v in ROMAN.items()}.get(int(entry["id"][1:]), entry["id"][1:])
        heading = f"Annexure {roman} - {heading}"
    out: list[str] = [f"# {heading}\n"]
    buf: list[str] = []
    seen_sub: set[str] = set()
    last_page: int | None = None
    skip_heading = entry.get("title_lines", 0)

    def flush():
        if buf:
            text = " ".join(buf).strip()
            if text:
                out.append(text + "\n")
            buf.clear()

    i = entry["start_line"]
    end = entry["end_line"]
    remaining = skip_heading
    while remaining > 0 and i <= end:
        if stream[i]["kind"] == "line":
            remaining -= 1
        i += 1
    while i <= end:
        item = stream[i]

        if item["pdf"] != last_page:
            flush()
            anchor = f"<!-- p. {item['printed']} -->" if item["printed"] else f"<!-- pdf. {item['pdf']} -->"
            out.append(anchor + "\n")
            last_page = item["pdf"]
            if item["pdf"] in verbatim:
                # Tabular page: carried through exactly, never reflowed.
                block = []
                while i <= end and stream[i]["pdf"] == item["pdf"]:
                    if stream[i]["kind"] == "line":
                        block.append(stream[i]["text"])
                    i += 1
                out.append("```text\n" + "\n".join(block) + "\n```\n")
                continue

        if item["kind"] == "page":
            i += 1
            continue

        ln = item["text"]

        m2 = L2.match(ln)
        if m2:
            sid = f"{m2.group(1)}.{m2.group(2)}"
            sub = next((x for x in subs if x["id"] == sid), None)
            if sub and sid not in seen_sub:
                flush()
                seen_sub.add(sid)
                out.append(f"## {sid} {sub['title']}\n")
                # Skip exactly the heading lines this sub-section occupied.
                remaining = sub.get("title_lines", 1)
                while remaining > 0 and i <= end:
                    if stream[i]["kind"] == "line":
                        remaining -= 1
                    i += 1
                continue
        if SALUTATION.match(ln):
            flush()
            out.append("**Honourable Speaker,**\n")
            i += 1
            continue

        buf.append(ln)
        if ENDS_BLOCK.search(ln) and len(" ".join(buf)) > 260:
            flush()
        i += 1

    flush()
    return "\n".join(out)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    d = common.doc_dir(doc)
    toc = common.read_json(d / "toc.json")
    cfg = common.read_json(d / "extract.config.json")
    src = common.source_entry(doc)
    first, last = cfg["pdf_range"]
    stream = common.line_stream(doc, first, last)

    entries = toc["entries"]
    verbatim = set(cfg["verbatim_pages"])
    sec_dir = d / "sections"
    for old in sec_dir.glob("*.md"):
        old.unlink()
    sec_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for e in entries:
        if e["level"] != 1:
            continue
        subs = [s for s in entries if s.get("parent") == e["id"]]
        span = range(e["pdf_start"], e["pdf_end"] + 1)
        e["has_verbatim"] = any(p in verbatim for p in span)
        e["printed_end"] = stream[e["end_line"]]["printed"]
        body = render_section(e, stream, cfg, subs)
        (sec_dir / f"{e['slug']}.md").write_text(front_matter(e, {**src, "document_id": doc}) + "\n" + body)
        written += 1

    common.write_json(d / "toc.json", toc)
    print(f"wrote {written} section files to {sec_dir.relative_to(common.ROOT)}")


if __name__ == "__main__":
    main()
