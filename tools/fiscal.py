"""Derive the fiscal datasets from Annexures I, III and IV.

Structured data is derived separately from the verbatim text and validated on
its own terms, because token equality proves the table's text survived but says
nothing about whether a value is still in its row.

Two things here will silently invert the meaning of the budget if done wrong:

  * PARENTHESES ARE NEGATIVE. "(745)" is -745. Read as positive, a deficit
    becomes a surplus.
  * ROW LABELS WRAP. "Revenue Surplus (+)/Deficit" and "(-) 217 103 216 206"
    are one row across two lines. The same wrapping once turned a project-name
    fragment into a phantom sector in Annexure VII.

So the parser accumulates label text until it finds a line ending in a full run
of value columns, and then reconciles: components must sum to their totals and
financing must equal the deficit, within a rounding tolerance.

    python tools/fiscal.py budget-2027
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

FENCE = re.compile(r"```text\n(.*?)\n```", re.S)
# Column headers arrive as their own lines and would otherwise be glued onto the
# first data row's label.
HEADER_LINE = re.compile(
    r"^(rs\.?\s*billion|\d{4}|\(provisional\)|revised|estimates|budget"
    r"|budget\s*\(with|supplementary\)|gdp\s*\(%\))$", re.I)
MAX_LABEL_LINES = 2
# A value is a number, a parenthesised negative, or "-" for nil.
VALUE = re.compile(r"\(\s*[\d,]+(?:\.\d+)?\s*\)|[\d,]+(?:\.\d+)?|^-$|(?<=\s)-(?=\s|$)")
ROUNDING_TOLERANCE = 2.0          # Rs billion; the source is rounded

SCENARIOS = ["2025_provisional", "2026_revised", "2027_budget", "2027_budget_with_supplementary"]

# Our annotation, not the source's: which rows are components of which total.
# Used only to reconcile, and recorded in the output so it can be audited.
COMPONENTS = {
    "Total Revenue and Grants": ["Total Revenue", "Grants"],
    "Total Revenue": ["Tax Revenue", "Non-Tax Revenue"],
    "Tax Revenue": ["Income Tax", "Taxes on Goods and Services", "Taxes on External Trade"],
    "Total Expenditure": ["Recurrent", "Public Investment", "Other"],
    "Recurrent": ["Salaries and Wages", "Other Goods and Services", "Interest",
                  "Subsidies and Transfers"],
}


def to_number(tok: str) -> float | None:
    tok = tok.strip()
    if tok in {"-", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "").strip()
    if not tok:
        return None
    try:
        v = float(tok)
    except ValueError:
        return None
    return -v if neg else v


def parse_grid(block: str, n_cols: int) -> list[dict]:
    """Rows of (label, values[n_cols]) from a fenced table block."""
    rows: list[dict] = []
    label_buf: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if HEADER_LINE.match(line):
            label_buf.clear()
            continue
        toks = VALUE.findall(line)
        # A data row ends with a full run of value columns.
        if len(toks) >= n_cols:
            tail = toks[-n_cols:]
            cut = len(line)
            for t in reversed(tail):
                pos = line.rfind(t, 0, cut)
                if pos != -1:
                    cut = pos
            head = line[:cut].strip()
            label = " ".join(label_buf + ([head] if head else [])).strip()
            values = [to_number(t) for t in tail]
            if label and all(v is not None for v in values):
                rows.append({"label": re.sub(r"\s+", " ", label), "values": values})
                label_buf = []
                continue
        label_buf.append(line)
        # Labels in this table wrap over at most two lines; anything longer is
        # stray header text, not part of the next row's name.
        del label_buf[:-MAX_LABEL_LINES]
    return rows


def clean_label(label: str) -> str:
    label = re.sub(r"Surplus\s*\(\+\)\s*/\s*Deficit\s*\(-\)", "Surplus/Deficit", label)
    label = re.sub(r"\s*\(-\)\s*", " ", label)
    label = re.sub(r"\s*\(\+\)\s*", " ", label)
    label = re.sub(r"\s*/\s*GDP\s*(\(%\))?\s*$", "", label, flags=re.I)
    label = re.sub(r"\s*GDP\s*\(%\)\s*$", "", label, flags=re.I)
    label = re.sub(r"\s*\(%\)\s*$", "", label)
    return re.sub(r"\s+", " ", label).strip(" -/")


def blocks(document_id: str, section_id: str) -> list[str]:
    d = common.doc_dir(document_id)
    toc = common.read_json(d / "toc.json")
    e = next(x for x in toc["entries"] if x["id"] == section_id)
    md = (d / "sections" / f"{e['slug']}.md").read_text()
    return [b for b in FENCE.findall(md) if b.strip()]


def parse_estimates(document_id: str) -> dict:
    """Annexure III - the budget itself, in Rs billion and as a share of GDP."""
    bl = blocks(document_id, "A3")
    tables = []
    for b in bl:
        rows = [r for r in parse_grid(b, 4) if not r["label"].lower().startswith(
            ("rs. billion", "2025", "2026", "2027", "compiled by"))]
        if not rows:
            continue
        unit = "percent_of_gdp" if "GDP (%)" in b or "/GDP" in b else "lkr_billion"
        tables.append({
            "unit": unit,
            "scenarios": SCENARIOS,
            "rows": [{"label": clean_label(r["label"]),
                      "values": dict(zip(SCENARIOS, r["values"]))} for r in rows],
        })

    issues: list[str] = []
    for t in tables:
        if t["unit"] != "lkr_billion":
            continue
        by_label = {r["label"]: r for r in t["rows"]}
        for total, parts in COMPONENTS.items():
            if total not in by_label or not all(p in by_label for p in parts):
                continue
            for sc in SCENARIOS:
                got = by_label[total]["values"][sc]
                want = sum(by_label[p]["values"][sc] for p in parts)
                if abs(got - want) > ROUNDING_TOLERANCE:
                    issues.append(f"{total} [{sc}]: stated {got}, components sum to {want}")
        # Financing must close the deficit exactly.
        if "Budget Surplus/Deficit" in by_label and "Total Financing" in by_label:
            for sc in SCENARIOS:
                d_ = by_label["Budget Surplus/Deficit"]["values"][sc]
                f_ = by_label["Total Financing"]["values"][sc]
                if abs(abs(d_) - f_) > ROUNDING_TOLERANCE:
                    issues.append(f"financing [{sc}]: deficit {d_}, financing {f_}")

    return {
        "document_id": document_id, "source_section": "A3",
        "source_title": "Summary of the Budget Estimates - 2027",
        "scenario_labels": {
            "2025_provisional": "2025 (Provisional)",
            "2026_revised": "2026 Revised Estimates",
            "2027_budget": "2027 Budget",
            "2027_budget_with_supplementary": "2027 Budget (With Supplementary)",
        },
        "reconciliation_map": COMPONENTS,
        "validation": {"ok": not issues, "issues": issues},
        "tables": tables,
    }


def parse_revenue_measures(document_id: str) -> dict:
    """Annexure I - revenue measures. Impacts are mostly negative."""
    rows: list[dict] = []
    issues: list[str] = []
    total_stated = None
    year_impact = None
    for b in blocks(document_id, "A1"):
        buf: list[str] = []
        for raw in b.splitlines():
            line = raw.strip()
            if not line or line.lower().startswith("revenue measure"):
                continue
            m = re.match(r"^(.*?)\s*(\(?[\d,]+\)?)\s*((?:January|February|March|April|May|June|"
                         r"July|August|September|October|November|December)\s+\d{4})$", line)
            if m:
                label = " ".join(buf + [m.group(1).strip()]).strip()
                rows.append({"measure": re.sub(r"\s+", " ", label),
                             "annual_impact_rs_mn": to_number(m.group(2)),
                             "effective": m.group(3)})
                buf = []
                continue
            if line.lower().startswith("total revenue increase"):
                total_stated = to_number(VALUE.findall(line)[-1])
                buf = []
                continue
            if line.lower().startswith("revenue impact for the year"):
                year_impact = to_number(VALUE.findall(line)[-1])
                buf = []
                continue
            buf.append(line)

    computed = sum(r["annual_impact_rs_mn"] for r in rows)
    if total_stated is not None and abs(computed - total_stated) > 1:
        issues.append(f"measures sum to {computed}, table states {total_stated}")
    if not rows:
        issues.append("no measures parsed")

    return {
        "document_id": document_id, "source_section": "A1",
        "source_title": "Summary of Revenue Impact - 2027",
        "unit": "LKR million",
        "note": "Negative values are revenue forgone. Parentheses in the source denote negatives.",
        "measures": rows,
        "total_annual_impact_rs_mn": total_stated,
        "impact_for_2027_rs_mn": year_impact,
        "validation": {"ok": not issues, "issues": issues},
    }


def parse_borrowing(document_id: str) -> dict:
    """Annexure IV - gross borrowing requirement."""
    rows, issues = [], []
    for b in blocks(document_id, "A4"):
        buf: list[str] = []
        for raw in b.splitlines():
            line = raw.strip()
            if not line or line.lower().startswith(("item ", "compiled by", "note:")):
                continue
            # A parenthesised sub-caption on its own line is table furniture,
            # not part of the next row's label.
            if re.fullmatch(r"\(.*\)", line):
                continue
            m = re.match(r"^(.*?)\s+(\(?[\d,]+\)?)$", line)
            if m and re.search(r"[A-Za-z]", m.group(1)):
                label = " ".join(buf + [m.group(1).strip()]).strip()
                rows.append({"item": re.sub(r"\s+", " ", label),
                             "amount_rs_bn": to_number(m.group(2))})
                buf = []
                continue
            buf.append(line)
    if not rows:
        issues.append("no items parsed")

    # These totals are stated AND decomposed in the same table, so they can be
    # reconciled rather than merely parsed.
    by = {r["item"]: r["amount_rs_bn"] for r in rows}
    for total, parts in (("Total Primary Expenditure", ["Recurrent", "Capital"]),
                         ("Debt Service Payments", ["Interest Payments", "Debt Repayments"])):
        if total in by and all(p in by for p in parts):
            want = sum(by[p] for p in parts)
            if abs(by[total] - want) > 1:
                issues.append(f"{total}: stated {by[total]}, components sum to {want}")
        else:
            issues.append(f"{total}: could not reconcile, rows missing")

    return {
        "document_id": document_id, "source_section": "A4",
        "source_title": "Gross Borrowings Requirement - 2027",
        "unit": "LKR billion",
        "items": rows,
        "validation": {"ok": not issues, "issues": issues},
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    outputs = {
        "fiscal.json": parse_estimates(doc),
        "revenue-measures.json": parse_revenue_measures(doc),
        "borrowing.json": parse_borrowing(doc),
    }
    failed = False
    for name, data in outputs.items():
        common.write_json(common.ROOT / "data" / doc / name, data)
        v = data["validation"]
        mark = "ok " if v["ok"] else "FAIL"
        count = (len(data.get("tables", [])) and sum(len(t["rows"]) for t in data["tables"])) \
            or len(data.get("measures", data.get("items", [])))
        print(f"  [{mark}] {name:<24} {count} rows")
        for i in v["issues"]:
            print(f"         - {i}")
        failed |= not v["ok"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
