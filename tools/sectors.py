"""Derive the per-sector capital expenditure dataset from Annexure VII.

Structured data is derived SEPARATELY from the verbatim text, and validated
differently. Token equality proves the table's text survived intact; it cannot
prove a number is still in the right row. So this parser carries its own checks
- serial numbers must run contiguously, every row needs a sector, a name and an
amount - and any row it cannot parse is reported rather than silently dropped.

    python tools/sectors.py budget-2027
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROW = re.compile(r"^(\d{1,3})\s+(.*?)\s+([\d,]+)$")   # serial, name, amount on one line
SERIAL_ONLY = re.compile(r"^(\d{1,3})$")
AMOUNT_ONLY = re.compile(r"^([\d,]{3,})$")
NOISE = {"serial", "no. project allocations (rs. million)", "annexure vii",
         "note - the numbers are rounded"}


def parse(document_id: str, section_id: str = "A7") -> dict:
    d = common.doc_dir(document_id)
    toc = common.read_json(d / "toc.json")
    entry = next(e for e in toc["entries"] if e["id"] == section_id)
    md = (d / "sections" / f"{entry['slug']}.md").read_text()

    sectors: list[dict] = []
    current: dict | None = None
    unparsed: list[str] = []
    # Rows wrap: a serial can sit alone, its name run over several lines, and
    # the amount land alone below. Without this state machine a name fragment
    # with no digits ("Sebestian Canals") reads as a sector heading and steals
    # every following project into a sector that does not exist.
    pending: dict | None = None

    body = md[md.index("```text"):] if "```text" in md else md
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "```", "<!--")):
            continue
        low = line.lower()
        # The table declares its own end; everything after it is the back cover.
        if low.startswith("note - the numbers are rounded"):
            break
        if low in NOISE or low.startswith("no. project") or low.startswith("summary of key new capital"):
            continue

        if pending is not None:
            if m := AMOUNT_ONLY.match(line):
                pending["amount_rs_mn"] = int(m.group(1).replace(",", ""))
                pending["name"] = " ".join(pending["name_parts"]).strip()
                del pending["name_parts"]
                if current is not None:
                    current["projects"].append(pending)
                else:
                    unparsed.append(str(pending))
                pending = None
                continue
            pending["name_parts"].append(line)
            continue

        if m := ROW.match(line):
            if current is None:
                unparsed.append(line)
                continue
            current["projects"].append({
                "serial": int(m.group(1)),
                "name": m.group(2).strip(),
                "amount_rs_mn": int(m.group(3).replace(",", "")),
            })
            continue

        if m := SERIAL_ONLY.match(line):
            pending = {"serial": int(m.group(1)), "name_parts": []}
            continue

        if re.search(r"\d", line):
            unparsed.append(line)
            continue
        current = {"sector": line, "projects": []}
        sectors.append(current)

    if pending is not None:
        unparsed.append(f"unterminated row {pending['serial']}")

    for s in sectors:
        s["total_rs_mn"] = sum(p["amount_rs_mn"] for p in s["projects"])
        s["project_count"] = len(s["projects"])
    sectors = [s for s in sectors if s["projects"]]

    serials = [p["serial"] for s in sectors for p in s["projects"]]
    issues = []
    if serials != list(range(1, len(serials) + 1)):
        gaps = [n for n in range(1, (max(serials) if serials else 0) + 1) if n not in serials]
        issues.append(f"serials not contiguous; missing {gaps[:12]}")
    if unparsed:
        issues.append(f"{len(unparsed)} unparsed line(s): {unparsed[:3]}")

    return {
        "document_id": document_id,
        "source_section": section_id,
        "source_title": entry["title"],
        "printed_pages": [entry.get("printed_start"), entry.get("printed_end")],
        "unit": "LKR million",
        "grand_total_rs_mn": sum(s["total_rs_mn"] for s in sectors),
        "project_count": len(serials),
        "validation": {"ok": not issues, "issues": issues},
        "sectors": sorted(sectors, key=lambda s: -s["total_rs_mn"]),
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    data = parse(doc)
    out = common.ROOT / "data" / doc / "sectors.json"
    common.write_json(out, data)
    print(f"sectors {len(data['sectors'])}  projects {data['project_count']}  "
          f"total Rs {data['grand_total_rs_mn']:,} mn")
    for s in data["sectors"]:
        print(f"  {s['sector'][:38]:<40} {s['project_count']:>3} proj  "
              f"Rs {s['total_rs_mn']:>9,} mn")
    if not data["validation"]["ok"]:
        print("\nVALIDATION ISSUES:")
        for i in data["validation"]["issues"]:
            print("  -", i)
        sys.exit(1)


if __name__ == "__main__":
    main()
