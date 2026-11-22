"""Stage 6 - build the chunk graph.

Written now, before any vector work, because the retrieval failures that matter
are baked in at ingest and cannot be repaired later without a full re-ingest:

  * IDs ARE CONTENT-ADDRESSED. sha256(document + section + ordinal + text).
    Re-ingesting unchanged text yields the same id, so citations do not rot.
    An index-based key (…/chunk_7) silently repoints at different text the
    moment a document is re-chunked.
  * PAGES TRAVEL WITH THE CHUNK, so a retrieved passage can cite a real page.
  * CHUNKS NEVER CROSS A SECTION, so every chunk has one true heading trail.
  * LINKS GO BOTH WAYS. parent_id and ancestors[] walk up to the TOC; prev_id
    and next_id walk along; toc.json walks down.

    python tools/chunk.py budget-2027
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import verify  # noqa: E402

TARGET_TOKENS = 250
MAX_TOKENS = 400
FENCE_BLOCK = re.compile(r"```text\n.*?\n```", re.S)
ANCHOR = re.compile(r"<!-- p\. (\d+) -->")
# Pages with no printed folio (the title page) carry a pdf-index anchor instead.
ANY_ANCHOR = re.compile(r"<!--\s*p(?:df)?\.\s*\d+\s*-->")
MIN_TOKENS = 60


def chunk_id(document_id: str, section_id: str, ordinal: int, text: str) -> str:
    h = hashlib.sha256()
    h.update(f"{document_id}\x00{section_id}\x00{ordinal}\x00".encode())
    h.update(common.normalise(text).encode())
    return f"{document_id[:3]}-{h.hexdigest()[:16]}"


def blocks_of(md: str) -> list[tuple[str, str, list[int]]]:
    """(kind, text, pages) in document order. Fenced tables stay whole."""
    md = verify.FRONT_MATTER.sub("", md)
    out: list[tuple[str, str, list[int]]] = []
    page = 0
    sub = ""
    pos = 0
    for m in FENCE_BLOCK.finditer(md):
        out.extend(scan(md[pos:m.start()], lambda: page, sub))
        pages = [int(x) for x in ANCHOR.findall(md[:m.start()])]
        out.append(("table", m.group(0), [pages[-1]] if pages else []))
        pos = m.end()
    out.extend(scan(md[pos:], lambda: page, sub))
    return out


def scan(md: str, _page, _sub) -> list[tuple[str, str, list[int]]]:
    res: list[tuple[str, str, list[int]]] = []
    page: int | None = None
    sub = ""
    for raw in md.split("\n\n"):
        para = raw.strip()
        if not para:
            continue
        if m := ANCHOR.fullmatch(para):
            page = int(m.group(1))
            continue
        if ANY_ANCHOR.fullmatch(para):
            page = None          # title page: no printed folio to cite
            continue
        if para.startswith("## "):
            sub = para[3:].strip()
            continue
        if para.startswith("# "):
            continue
        res.append((f"prose::{sub}", para, [page] if page else []))
    return res


def build(document_id: str) -> list[dict]:
    d = common.doc_dir(document_id)
    toc = common.read_json(d / "toc.json")
    entries = toc["entries"]
    by_id = {e["id"]: e for e in entries}
    rows: list[dict] = []

    for e in entries:
        if e["level"] != 1:
            continue
        md = (d / "sections" / f"{e['slug']}.md").read_text()
        blocks = blocks_of(md)

        # Group consecutive prose of the same sub-section up to the target size;
        # a table is always its own chunk so its rows are never half-retrieved.
        groups: list[dict] = []
        cur: dict | None = None
        for kind, text, pages in blocks:
            if kind == "table":
                cur = None
                groups.append({"sub": "", "texts": [text], "pages": list(pages), "table": True})
                continue
            n = len(common.tokens(text))
            if (cur is None or cur["sub"] != kind or cur["table"]
                    or cur["tokens"] + n > MAX_TOKENS):
                cur = {"sub": kind, "texts": [], "pages": [], "tokens": 0, "table": False}
                groups.append(cur)
            cur["texts"].append(text)
            cur["pages"].extend(pages)
            cur["tokens"] = cur.get("tokens", 0) + n
            if cur["tokens"] >= TARGET_TOKENS:
                cur = None

        groups = [g for g in groups if "".join(g["texts"]).strip(" `\ntext")]

        # A short trailing group is a fragment, not a passage: fold it back into
        # the previous prose group of the same sub-section where it fits.
        merged: list[dict] = []
        for g in groups:
            if (merged and not g["table"] and not merged[-1]["table"]
                    and g["sub"] == merged[-1]["sub"]
                    and len(common.tokens("\n\n".join(g["texts"]))) < MIN_TOKENS
                    and merged[-1].get("tokens", 0) + g.get("tokens", 0) <= MAX_TOKENS):
                merged[-1]["texts"].extend(g["texts"])
                merged[-1]["pages"].extend(g["pages"])
                merged[-1]["tokens"] = merged[-1].get("tokens", 0) + g.get("tokens", 0)
                continue
            merged.append(g)
        groups = merged

        section_rows: list[dict] = []
        for ordinal, g in enumerate(groups):
            text = "\n\n".join(g["texts"])
            sub_title = g["sub"].split("::", 1)[1] if "::" in g["sub"] else ""
            sub_id = sub_title.split(" ", 1)[0] if re.match(r"^\d+\.\d+", sub_title) else None
            holder = by_id.get(sub_id, e) if sub_id else e
            trail = [e["title"]] + ([holder["title"]] if holder is not e else [])
            ancestors = [document_id, e["id"]] + ([holder["id"]] if holder is not e else [])
            section_rows.append({
                "chunk_id": chunk_id(document_id, holder["id"], ordinal, text),
                "document_id": document_id,
                "section_id": holder["id"],
                "path": " / ".join([document_id] + ancestors[1:]),
                "depth": len(ancestors) - 1,
                "parent_id": holder["id"],
                "ancestors": ancestors,
                "prev_id": None,
                "next_id": None,
                "pages": sorted({p for p in g["pages"] if p}),
                "heading_trail": trail,
                "kind": "table" if g["table"] else "prose",
                "text": text,
                "token_count": len(common.tokens(text)),
            })

        for n, r in enumerate(section_rows):
            r["prev_id"] = section_rows[n - 1]["chunk_id"] if n else None
            r["next_id"] = section_rows[n + 1]["chunk_id"] if n + 1 < len(section_rows) else None
        rows.extend(section_rows)

    return rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    rows = build(doc)
    out = common.ROOT / "build" / doc / "chunks.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    toks = [r["token_count"] for r in rows]
    tables = sum(1 for r in rows if r["kind"] == "table")
    print(f"chunks       {len(rows)}  ({tables} tables, {len(rows) - tables} prose)")
    print(f"tokens       min {min(toks)}  median {sorted(toks)[len(toks)//2]}  max {max(toks)}")
    print(f"with pages   {sum(1 for r in rows if r['pages'])}/{len(rows)}")
    print(f"wrote        {out.relative_to(common.ROOT)}")


if __name__ == "__main__":
    main()
