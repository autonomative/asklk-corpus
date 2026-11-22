# The ask.lk Document Format

A format for turning an official PDF into Markdown that a language model can
read and cite, where **the transformation is mechanically verifiable by anyone**.

The format exists because a corpus that cannot be checked is a corpus that has
to be trusted, and a reader quoting a budget figure or a legal provision should
not have to trust us. Everything below is designed so a third party with the
source PDF can reproduce the output byte-for-byte and prove nothing was
invented or lost.

Anyone may implement this format. See `LICENSE` (MIT, tooling) and
`LICENSE-CONTENT` (CC0, our transformation). Read `DISCLAIMER.md` first.

---

## 1. Principles

1. **No model writes corpus text.** Extraction is deterministic code. A language
   model may configure, propose or review, but never authors, translates,
   summarises or corrects a sentence. Any paraphrase fails verification.
2. **Every transformation is declared.** Anything removed from the source is
   named in `extract.config.json` with a reason. What is not declared must survive.
3. **Verification states its own limits.** The checks prove content fidelity.
   They do not prove reading order or table structure, and the format requires
   that this be published alongside the results, not buried.

## 2. Layout

```
manifest.json                     sources: url, sha256, bytes, retrieved, pages
sources/<doc>/<file>.pdf          the source, committed unmodified
documents/<doc>/
  profile.json                    per-page language, table density, column risk
  toc.json                        the derived outline — the spine
  extract.config.json             page range + every drop rule
  sections/<slug>.md              one file per level-1 entry
  verification.json               machine-readable check results + per-section signals
  report.md                       human-readable transformation report
data/<doc>/*.json                 datasets derived from tables, separately validated
build/<doc>/chunks.jsonl          the chunk graph
```

## 3. Normalisation

Applied identically to both sides of every comparison. Implementations must
match this list exactly or their verification results are not comparable.

1. Unicode NFKC
2. Remove soft hyphens (`U+00AD`)
3. Curly quotes → straight (`’‘` → `'`, `“”` → `"`)
4. En/em dash → spaced hyphen (` - `), so `Budget—Speech` is two tokens
5. Join words broken across a line: `(\w)-\s+(\w)` → `\1\2`
6. Collapse all whitespace runs to a single space; trim

**Tokenisation.** `\d(?:[\d,.]*\d)?%?|[^\W\d_]+(?:['\-][^\W\d_]+)*`, lowercased.
Numbers match first so `1,022` stays one token; each branch starts and ends on a
content character so trailing punctuation never joins a token. Standalone
punctuation produces no token.

## 4. Page anchors

Each page boundary is marked in the Markdown by an HTML comment:

```
<!-- p. 42 -->      printed folio number
<!-- pdf. 259 -->   pages with no printed folio
```

Invisible when rendered; they let a chunker attach a real page locator to every
passage. **Capture these at authoring time.** Reconstructing page spans after
chunking is not possible — this is the single most common unrecoverable loss in
document pipelines.

## 5. Section front matter

```yaml
section_id, title, document_id, document_title
level, parent, prev, next, children[]
pdf_pages: [start, end]
printed_pages: [start, end]
detection: pdf-bookmark | numbered-heading-regex | annexure-marker | range-assignment
heading_confidence: high | medium | low
verbatim_tables: bool
source_url, source_sha256
licence, disclaimer
```

## 6. `toc.json`

Derived outline. Each entry records `id`, `title`, `level`, `parent`,
`children[]`, `prev`, `next`, `slug`, `pdf_start`/`pdf_end`,
`start_line`/`end_line`, `title_lines`, `detection`, `heading_confidence`, plus
document-level `approved_by` and `approved_at`.

**Boundaries are line-level, not page-level.** A heading routinely appears
partway down a page; slicing by page misplaces the previous section's tail and
duplicates the shared page into two files.

Where a source has no usable outline — no PDF bookmarks, no printed contents
page — the TOC is an *inference* and must be approved by a human before anything
downstream consumes it.

## 7. Tables

Tabular and multi-column pages are emitted as fenced verbatim blocks, never
reflowed into Markdown tables. Token equality cannot prove a number is still in
its row, and reflowing is where silent corruption hides.

Structured data is derived **separately**, into `data/<doc>/`, and validated on
its own terms (contiguous keys, required fields, reconciling totals). Text
fidelity and data correctness are different claims and are checked differently.

## 8. Verification

| # | Property |
|---|---|
| 1 | Source integrity — SHA-256 matches `manifest.json` |
| 2 | Determinism — re-running extraction is byte-identical |
| 3 | **No insertion** — every output token exists in its source slice, with at least the same multiplicity |
| 4 | **No omission** — every source token survives, except tokens matched by a declared drop rule |
| 5 | Page anchors — present, unique, ascending |
| 6 | TOC coverage — sections tile the line stream with no gaps or overlaps |
| 7 | Front matter — present and complete |
| 8 | Chunk graph — ids unique, links resolve, no chunk crosses a section |

Checks 3 and 4 carry the integrity claim. A paraphrase, a summary, an invented
figure or a dropped sentence each fail one of them.

### Drop rules

Each rule declares `id`, `scope`, `pattern` and `reason`. `scope` matters:
a rule scoped `page-first-line` is enforced structurally during extraction;
applying it to every line instead would delete genuine content — the pattern
`^\d{1,3}$` removes a printed folio number in the right scope and a table cell
in the wrong one.

## 9. Confidence bands

| Band | Criteria |
|---|---|
| High | Single-column prose, heading on one line, zero insertions, zero omissions |
| Medium | As High, but the heading was inferred across wrapped lines |
| Low | Contains tabular or multi-column pages; text verified, structure not provable |

A band is **machine-verifiable risk only**. Whether a human has read the section
is a separate field. Implementations must not blend the two into one score:
averaging away "this table's structure is unprovable" is false assurance.

## 10. `chunks.jsonl`

One JSON object per line.

```json
{ "chunk_id": "bud-a3f91c2e4d5b6071", "document_id": "budget-2027",
  "section_id": "2.3", "path": "budget-2027 / 2 / 2.3", "depth": 2,
  "parent_id": "2.3", "ancestors": ["budget-2027", "2", "2.3"],
  "prev_id": "…", "next_id": "…", "pages": [8, 9],
  "heading_trail": ["Seven Strategic Objectives…", "Enhancing Productivity…"],
  "kind": "prose", "text": "…verbatim…", "token_count": 214 }
```

Required properties:

- **Content-addressed ids** — `sha256(document_id + section_id + ordinal +
  normalised_text)`, truncated. Re-ingesting unchanged text yields the same id,
  so citations survive re-ingestion. An index-based key (`…/chunk_7`) silently
  repoints at different text the moment a document is re-chunked.
- **Bidirectional traversal** — `parent_id` and `ancestors[]` walk up to the
  TOC; `prev_id`/`next_id` walk along; `toc.json` walks down.
- **No chunk crosses a section**, so every chunk has one true heading trail.
- **Pages travel with the chunk**, so every retrieved passage can cite a page.
- A table is always a whole chunk, never split mid-row.

## 11. Conformance

A document conforms when `tools/verify.py` reports all eight checks passing, its
`report.md` publishes the per-section bands, and `DISCLAIMER.md` ships with it.
