"""Shared primitives for the asklk-corpus pipeline.

Normalisation is defined ONCE, here, because verification compares the output
against the source using these exact rules. If the two sides could normalise
differently the whole assurance argument collapses. SPEC.md publishes this list
verbatim so a third party can reproduce the comparison.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Normalisation ────────────────────────────────────────────────────────────
# Each rule is listed in SPEC.md. Do not add one without updating the spec.
SOFT_HYPHEN = "­"
_WS = re.compile(r"\s+")
_HYPHEN_BREAK = re.compile(r"(\w)-\s+(\w)")      # word broken across a line
# Numbers first so "1,022" stays one token; each branch must start AND end on
# a content character so trailing punctuation never becomes part of a token.
_TOKEN = re.compile(r"\d(?:[\d,.]*\d)?%?|[^\W\d_]+(?:['\-][^\W\d_]+)*", re.UNICODE)


def normalise(text: str) -> str:
    """Canonical form used on BOTH sides of every comparison."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(SOFT_HYPHEN, "")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    # Em/en dashes separate words; a spaced hyphen keeps "Budget—Speech" as two
    # tokens while leaving genuine hyphenates like "co-operation" intact.
    text = text.replace("–", " - ").replace("—", " - ")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _WS.sub(" ", text)
    return text.strip()


def tokens(text: str) -> list[str]:
    """Comparable token stream. Case-folded so capitalisation differences from
    PDF extraction do not read as content changes; punctuation is not a token."""
    return [t.lower() for t in _TOKEN.findall(normalise(text))]


def token_counts(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tokens(text):
        out[t] = out.get(t, 0) + 1
    return out


# ── Manifest & paths ─────────────────────────────────────────────────────────
def manifest() -> dict:
    return json.loads((ROOT / "manifest.json").read_text())


def source_entry(document_id: str) -> dict:
    for s in manifest()["sources"]:
        if s["document_id"] == document_id:
            return s
    raise SystemExit(f"no manifest entry for {document_id!r}")


def doc_dir(document_id: str) -> Path:
    return ROOT / "documents" / document_id


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict | list:
    return json.loads(Path(path).read_text())


def write_json(path: Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ── Page access ──────────────────────────────────────────────────────────────
PAGENO = re.compile(r"^\s*(\d{1,3})\s*$")


def page_texts(document_id: str) -> list[str]:
    """Raw per-page text straight from the PDF. The single read point, so every
    stage sees identical input."""
    from pypdf import PdfReader

    src = source_entry(document_id)
    reader = PdfReader(str(ROOT / src["path"]))
    return [(p.extract_text() or "") for p in reader.pages]


def split_page(raw: str) -> tuple[str | None, list[str]]:
    """Return (printed page number, content lines). The printed number sits
    alone on the first line of every extracted page in this document family."""
    lines = [_WS.sub(" ", ln).strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    printed = None
    if lines and PAGENO.match(lines[0]):
        printed, lines = lines[0].strip(), lines[1:]
    return printed, lines


def line_stream(document_id: str, first: int, last: int) -> list[dict]:
    """Flat, ordered line stream across a page range.

    Section boundaries are line-level, not page-level: a heading routinely
    appears partway down a page, so slicing by page would both misplace the
    trailing content of the previous section and duplicate the shared page into
    two section files. Every line carries its page, so page anchors and the
    verification page map survive the flattening.
    """
    pages = page_texts(document_id)
    stream: list[dict] = []
    for idx in range(first, last + 1):
        printed, lines = split_page(pages[idx])
        stream.append({"kind": "page", "pdf": idx, "printed": printed, "text": ""})
        for ln in lines:
            stream.append({"kind": "line", "pdf": idx, "printed": printed, "text": ln})
    return stream
