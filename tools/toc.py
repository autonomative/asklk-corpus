"""Stage 2 - derive the table of contents.

This document has NO machine-readable outline: its PDF bookmarks are five
entries all titled "Blank Page", and the English block has no printed contents
page. So structure has to be inferred from the body text, which makes the TOC an
inference with a confidence of its own rather than a fact. It is written out for
a human to approve before anything downstream consumes it.

Detection is deliberately conservative:

  * a level-1 heading "N. Title" is accepted only when N is the next number in
    sequence, so numbered list items and table rows cannot masquerade as sections
  * a level-2 heading "N.M Title" is accepted only under its own parent
  * annexures are found by their own "Annexure <roman>" marker, because their
    numbering restarts at 1 and would otherwise collide with the body

    python tools/toc.py budget-2027
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
# A title whose LAST WORD is one of these is mid-phrase and continues on the
# next line. Matched as whole words, never as a suffix: "Education" ends with
# the letters "on", and substring matching silently swallowed the body text of
# every section whose title happened to end that way.
CONT_WORDS = {"and", "of", "the", "to", "for", "through", "with", "in", "on",
              "a", "an", "its", "their", "from", "by"}

# Derived titles would read as inserted text in verification check 3, so the
# front section is named from a line that genuinely appears on its page.
FRONT_TITLE = "81st Budget Speech"

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10}


def slugify(text: str, prefix: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return f"{prefix}-{s[:52]}".strip("-")


def derive(document_id: str, first: int, last: int) -> list[dict]:
    stream = common.line_stream(document_id, first, last)
    lines = [s["text"] for s in stream]
    entries: list[dict] = []
    expect_l1 = 1
    current_l1: dict | None = None
    in_annex = False

    if True:
        i = 0
        while i < len(lines):
            ln = lines[i]
            idx, printed = stream[i]["pdf"], stream[i]["printed"]
            if stream[i]["kind"] == "page":
                i += 1
                continue

            m = ANNEX.match(ln)
            if m:
                in_annex = True
                num = m.group(1).upper()
                title = lines[i + 1].strip() if i + 1 < len(lines) else f"Annexure {num}"
                title_lines = 2 if i + 1 < len(lines) else 1
                entries.append({
                    "id": f"A{ROMAN.get(num, num)}", "number": f"Annexure {num}",
                    "title": title, "level": 1, "parent": None,
                    "pdf_start": idx, "printed_start": printed, "start_line": i,
                    "title_lines": title_lines,
                    "detection": "annexure-marker", "heading_confidence": "high",
                })
                current_l1 = entries[-1]
                i += 1
                continue

            if not in_annex:
                m2 = L2.match(ln)
                if m2 and current_l1 and m2.group(1) == str(current_l1.get("number")):
                    start_i = i
                    title, i = absorb(lines, i, m2.group(3))
                    entries.append({
                        "id": f"{m2.group(1)}.{m2.group(2)}", "number": None,
                        "title": title, "level": 2, "parent": current_l1["id"],
                        "pdf_start": idx, "printed_start": printed,
                        "start_line": start_i, "title_lines": i - start_i + 1,
                        "detection": "numbered-heading-regex", "heading_confidence": "medium",
                    })
                    i += 1
                    continue

                m1 = L1.match(ln)
                if m1 and int(m1.group(1)) == expect_l1:
                    start_i = i
                    title, i = absorb(lines, i, m1.group(2))
                    entries.append({
                        "id": m1.group(1), "number": int(m1.group(1)),
                        "title": title, "level": 1, "parent": None,
                        "pdf_start": idx, "printed_start": printed,
                        "start_line": start_i, "title_lines": i - start_i + 1,
                        "detection": "numbered-heading-regex", "heading_confidence": "medium",
                    })
                    current_l1 = entries[-1]
                    expect_l1 += 1
                    i += 1
                    continue
            i += 1

    return entries


def continues(title: str) -> bool:
    t = title.rstrip()
    if t.endswith((",", "-", "&")):
        return True
    words = re.findall(r"[A-Za-z]+", t)
    return bool(words) and words[-1].lower() in CONT_WORDS


def absorb(lines: list[str], i: int, title: str) -> tuple[str, int]:
    """Headings wrap across lines in the source; pull in the continuation."""
    title = title.strip()
    while (continues(title) and i + 1 < len(lines)
           and not L1.match(lines[i + 1]) and not L2.match(lines[i + 1])):
        i += 1
        title = f"{title} {lines[i].strip()}"
    return re.sub(r"\s+", " ", title).strip(), i


def finish(entries: list[dict], first: int, last: int, stream_len: int) -> list[dict]:
    """Assign page spans, slugs, sibling links and children."""
    front = {
        "id": "front", "number": None, "title": FRONT_TITLE, "level": 1,
        "parent": None, "pdf_start": first, "printed_start": None,
        "start_line": 0, "title_lines": 1,
        "detection": "range-assignment", "heading_confidence": "high",
    }
    if entries and entries[0]["pdf_start"] > first:
        entries = [front] + entries

    # A section runs until the next heading at the same level or shallower.
    for n, e in enumerate(entries):
        nxt = next((x for x in entries[n + 1:] if x["level"] <= e["level"]), None)
        # Line-level boundary: a section ends where the next same-or-shallower
        # heading begins, which is routinely partway down a shared page.
        e["end_line"] = (nxt["start_line"] - 1) if nxt else (stream_len - 1)
        e["pdf_end"] = (nxt["pdf_start"] if nxt else last)
        if e["pdf_end"] < e["pdf_start"]:
            e["pdf_end"] = e["pdf_start"]
        prefix = e["id"].zfill(2) if e["id"].isdigit() else e["id"].lower()
        e["slug"] = slugify(e["title"], prefix)
        e["children"] = [c["id"] for c in entries if c.get("parent") == e["id"]]

    for e in entries:
        if e["level"] == 1:
            kids = [c for c in entries if c.get("parent") == e["id"]]
            if kids:
                e["end_line"] = max(e["end_line"], max(k["end_line"] for k in kids))
                e["pdf_end"] = max(e["pdf_end"], max(k["pdf_end"] for k in kids))

    tops = [e for e in entries if e["level"] == 1]
    for n, e in enumerate(tops):
        e["prev"] = tops[n - 1]["id"] if n else None
        e["next"] = tops[n + 1]["id"] if n + 1 < len(tops) else None
    for e in entries:
        e.setdefault("prev", None)
        e.setdefault("next", None)
    return entries


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    prof = common.read_json(common.doc_dir(doc) / "profile.json")
    first, last = prof["english_runs"][0]
    first -= 1  # the English title page scores below the prose threshold

    stream_len = len(common.line_stream(doc, first, last))
    entries = finish(derive(doc, first, last), first, last, stream_len)
    common.write_json(common.doc_dir(doc) / "toc.json", {
        "document_id": doc,
        "derived_from": "body-text inference (no PDF outline, no printed contents page)",
        "pdf_range": [first, last],
        "approved_by": None,
        "approved_at": None,
        "entries": entries,
    })

    l1 = [e for e in entries if e["level"] == 1]
    print(f"entries {len(entries)}  (level 1: {len(l1)}, level 2: {len(entries) - len(l1)})")
    for e in l1:
        kids = f" +{len(e['children'])}" if e["children"] else ""
        print(f"  {e['id']:>5}  pdf {e['pdf_start']:>3}-{e['pdf_end']:<3} {e['title'][:58]}{kids}")


if __name__ == "__main__":
    main()
