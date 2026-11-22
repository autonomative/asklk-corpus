---
name: ingest-document
description: Ingest an official PDF into the asklk-corpus as verified, LLM-readable Markdown with a chunk graph. Use when adding a new source document, re-ingesting an updated one, or when a verification check fails and the pipeline needs diagnosing. Covers fetching and pinning a source, deriving a table of contents, extracting sections, running the eight verification checks, and producing the transformation report.
---

# Ingesting a document

## The rule that governs everything

**You never write corpus text.** Extraction is deterministic Python. You
configure, propose, diagnose and review — you do not author, translate,
summarise, reword or correct a single sentence of a source document.

If the output looks wrong, fix the extractor or declare a drop rule. **Never
hand-edit a file under `documents/*/sections/`.** A hand edit cannot be
reproduced from the source, so it breaks determinism, and if it adds text it
fails the insertion check. Those checks are the product; do not route around them.

This matters more than it sounds. The corpus exists so a reader can quote a
figure without trusting us. One paraphrased sentence, anywhere, makes that claim
false for the whole corpus.

## Sequence

Run from the repo root with `.venv/bin/python`.

### 1 · Fetch and pin
Download the PDF to `sources/<doc>/`, compute its SHA-256, and add a
`manifest.json` entry with url, bytes, page count and retrieval date. The hash
is checked before every build, so a source that changes underneath us fails
loudly rather than silently.

### 2 · Profile
```
.venv/bin/python tools/profile.py <doc>
```
Reports per-page language, table density and column risk, and proposes the
English page range. These documents are trilingual and the non-English text is
set in legacy fonts that extract as Latin noise — the English-function-word
ratio separates real English from that noise reliably; font inspection does not.

### 3 · Derive the TOC, then **get it approved**
```
.venv/bin/python tools/toc.py <doc>
```
Check PDF bookmarks first — if real, they beat inference. (For Budget Speech
2027 they were five entries all titled "Blank Page", so structure had to come
from the body text.)

Present the derived outline to the user and ask them to confirm it before going
further. Everything downstream is sliced from it; a wrong boundary silently
misfiles content. Record `approved_by` and `approved_at` in `toc.json`.

Look specifically for: sections missed because the title contains an unusual
character (an en-dash cost us section 38 once); titles that swallowed body text;
numbering that restarts inside annexures.

### 4 · Configure
Write `extract.config.json`: the page range, the list of tabular pages from the
profile, and every drop rule. **Give each rule an explicit `scope`.** A rule
scoped wrongly is silent data loss — `^\d{1,3}$` removes a printed folio number
at `page-first-line` and destroys table cells at `any-line`.

### 5 · Extract
```
.venv/bin/python tools/extract.py <doc>
```

### 6 · Verify — and treat failures as information
```
.venv/bin/python tools/verify.py <doc>
```
Eight checks. When one fails, the usual causes, in order of likelihood:

| Symptom | Usual cause |
|---|---|
| Insertions of title words | Heading emitted as H1 *and* left in the body — check `title_lines` |
| Insertions of bare numbers | A drop rule is scoped too broadly and is deleting table cells from the comparison |
| Omissions of joined words (`highproductivity`) | Verifier tokenising line-by-line while the renderer joins lines |
| Omission of a section number | H1 dropped the number the source heading carried |

A failing check has caught something real. Diagnose it; do not relax the check.

### 7 · Chunk, derive, report
```
.venv/bin/python tools/chunk.py <doc>
.venv/bin/python tools/sectors.py <doc>    # if the document has a table worth structuring
.venv/bin/python tools/report.py <doc>
```
Table parsers need their own validation — contiguous keys, required fields,
reconciling totals — because token checks cannot see row structure. A wrapped
table row once turned a project-name fragment into a phantom sector; the
contiguity check caught it.

### 8 · Human review gate
Sample ~10 pages, weighted toward Low-confidence sections, and read them against
the PDF **for reading order** — the one failure mode no automated check sees.
Record the page numbers in `verification.json` under `human_reviewed_pages`.

### 9 · Commit
Only when all eight checks pass. Commit the source PDF, the generated files and
the config together, so the whole chain of evidence lands in one diff.

## Adding a new document type

`tools/` is generic; the document-specific parts are `extract.config.json` and
the heading patterns in `tools/toc.py`. Prefer extending the config. If a new
source needs different heading detection, add a detection method and record it
per entry so `heading_confidence` stays meaningful — do not quietly broaden an
existing regex, because that changes how every other document is parsed.

Update `SPEC.md` whenever the format changes. The spec is the published
contract, not documentation written afterwards.
