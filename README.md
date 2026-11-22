# asklk-corpus

Official Sri Lankan documents, turned into Markdown a language model can read
and cite — where **the transformation is mechanically verifiable by anyone**.

A corpus you cannot check is a corpus you have to trust. Someone quoting a
budget figure should not have to trust us, so every document here ships with
its source PDF, the code that transformed it, and eight automated checks that
prove no content was invented and none was lost.

> **Read [`DISCLAIMER.md`](DISCLAIMER.md).** No warranty, no liability, not
> advice. Errors are possible. For anything that matters, read the official
> publication — every document records the URL and SHA-256 of its source.

## What's here

| Document | Pages | Sections | Status |
|---|---|---|---|
| [Budget Speech 2027](documents/budget-2027/report.md) | 107 English of 367 | 47 | all checks pass · 38 High / 1 Medium / 8 Low |

## Verify it yourself

```sh
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python tools/verify.py budget-2027
```

Eight checks, non-zero exit on any failure. The two that carry the claim:

- **No insertion** — every token in the output exists in the source lines that
  section was built from. A paraphrase, a summary or an invented figure fails.
- **No omission** — every source token survives, except those matched by a rule
  declared in `extract.config.json`.

Rebuild from the PDF and confirm nothing moved:

```sh
.venv/bin/python tools/extract.py budget-2027
.venv/bin/python tools/chunk.py budget-2027
git diff --exit-code          # determinism: output is byte-identical
```

## What the checks do not prove

- **Reading order.** The same tokens in the wrong sequence pass every automated
  check. Tabular and multi-column sections are marked **Low** confidence for
  exactly this reason, and need human review.
- **Table structure.** Tabular pages are carried through as verbatim blocks, so
  the text is exact, but no check can prove a number is still in its row.
- **Correctness of the original.** We reproduce documents; we do not audit them.

Structured data derived from tables is validated separately and on its own
terms — `data/budget-2027/sectors.json` requires contiguous serial numbers and
a sector, name and amount on every row.

## English only

The sources are trilingual. Sinhala and Tamil are set in legacy non-Unicode
fonts that do not extract as recoverable text, so only the English text is
reproduced. This is a limitation of the sources, not an editorial choice, and
it means the corpus is not a complete rendering of any document.

## Layout

```
manifest.json              sources with SHA-256
sources/                   the PDFs, unmodified
documents/<doc>/
  toc.json                 derived outline (the spine)
  sections/*.md            one file per section, with page anchors
  extract.config.json      every transformation, declared
  report.md                per-section status and confidence
  verification.json        machine-readable results
data/<doc>/                datasets derived from tables
build/<doc>/chunks.jsonl   chunk graph, ready to embed
tools/                     the pipeline
```

## The pipeline

`profile` → `toc` → *human approves the outline* → `extract` → `verify` →
`chunk` → `sectors` → `report`

No model writes corpus text at any stage. Extraction is deterministic Python;
a language model may configure and review, never author. The
[`ingest-document`](.claude/skills/ingest-document/SKILL.md) skill drives the
sequence for a new source.

## The format

[`SPEC.md`](SPEC.md) documents it in full — normalisation, page anchors, front
matter, the TOC, the chunk graph, the eight checks and the confidence rubric.
It is deliberately implementable by anyone; the tooling here is one
implementation, not the definition.

Chunking decisions worth copying: **content-addressed chunk ids**, so citations
survive re-ingestion rather than silently repointing at different text, and
**page anchors captured at authoring time**, because page spans cannot be
reconstructed after chunking.

## Licence

`LICENSE` (MIT) covers the tooling. `LICENSE-CONTENT` (CC0) covers our
transformation — the extraction, structuring and metadata — **and nothing
else**. Rights in the underlying documents remain with the Government of Sri
Lanka. We assert no rights over those works and grant none.

Not affiliated with, endorsed by, or connected to the Government of Sri Lanka.
