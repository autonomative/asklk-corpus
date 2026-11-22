"""Stage 1 - profile the source PDF.

Classifies every page by language, table density and column risk. Two of those
feed the confidence rubric directly, and the language classification is how the
English block gets located: this document family interleaves Sinhala, Tamil and
English, and the first two are set in legacy non-Unicode fonts that extract as
Latin noise. Counting English function words separates real English from that
noise far more reliably than any font check.

    python tools/profile.py budget-2027
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import common  # noqa: E402

# Function words are the signal: they are frequent in real English prose and
# essentially absent from font-mangled Sinhala/Tamil rendered as Latin.
EN_FUNCTION = re.compile(
    r"\b(the|and|of|to|in|for|will|that|this|has|have|been|are|is|with|from|"
    r"by|as|be|which|our|we|it|on|at|an|their)\b", re.I)
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
WIDE_GAP = re.compile(r"\S {4,}\S")

EN_RATIO_MIN = 0.06
MIN_WORDS = 40


def profile_document(document_id: str) -> dict:
    from pypdf import PdfReader

    src = common.source_entry(document_id)
    reader = PdfReader(str(common.ROOT / src["path"]))

    pages = []
    for i, page in enumerate(reader.pages):
        flat = page.extract_text() or ""
        try:
            laid = page.extract_text(extraction_mode="layout") or ""
        except Exception:
            laid = flat

        words = LATIN_WORD.findall(flat)
        hits = len(EN_FUNCTION.findall(flat))
        ratio = hits / max(len(words), 1)

        lines = [ln for ln in laid.splitlines() if ln.strip()]
        gapped = sum(1 for ln in lines if WIDE_GAP.search(ln))
        table_density = round(gapped / max(len(lines), 1), 3)

        numbers = len(re.findall(r"\b[\d,]{3,}\b", flat))
        printed, _ = common.split_page(flat)

        pages.append({
            "index": i,
            "printed": printed,
            "chars": len(flat),
            "latin_words": len(words),
            "en_ratio": round(ratio, 3),
            "language": "en" if ratio > EN_RATIO_MIN and len(words) > MIN_WORDS else "non-en",
            "table_density": table_density,
            # A page that is mostly wide-gapped lines is either tabular or
            # multi-column; either way its reading order is not machine-provable.
            "column_risk": "high" if table_density > 0.40 else "low",
            "numeric_tokens": numbers,
        })

    english = [p["index"] for p in pages if p["language"] == "en"]
    runs, start = [], None
    for i in range(len(pages)):
        is_en = i in set(english)
        if is_en and start is None:
            start = i
        if not is_en and start is not None:
            runs.append([start, i - 1])
            start = None
    if start is not None:
        runs.append([start, len(pages) - 1])
    runs = [r for r in runs if r[1] - r[0] >= 1]

    return {
        "document_id": document_id,
        "sha256": common.sha256_file(common.ROOT / src["path"]),
        "page_count": len(pages),
        "english_runs": runs,
        "english_page_count": len(english),
        "pages": pages,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    doc = sys.argv[1]
    prof = profile_document(doc)
    out = common.doc_dir(doc) / "profile.json"
    common.write_json(out, prof)
    print(f"pages           {prof['page_count']}")
    print(f"english pages   {prof['english_page_count']}")
    print(f"english runs    {prof['english_runs']}")
    # Scoped to the English runs: out-of-scope pages are legacy-font noise whose
    # gappy layout inflates the count without meaning anything.
    in_scope = {i for a, b in prof["english_runs"] for i in range(a, b + 1)}
    heavy = [p["index"] for p in prof["pages"]
             if p["column_risk"] == "high" and p["index"] in in_scope]
    print(f"table/column risk (in scope): {len(heavy)} of {len(in_scope)} -> {heavy}")
    print(f"wrote           {out.relative_to(common.ROOT)}")


if __name__ == "__main__":
    main()
