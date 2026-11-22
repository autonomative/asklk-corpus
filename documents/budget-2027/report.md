# Transformation report — Budget Speech 2027

Source: [https://www.treasury.gov.lk/api/file/ea495202-fcb1-4c78-b34e-58389cb20738](https://www.treasury.gov.lk/api/file/ea495202-fcb1-4c78-b34e-58389cb20738)
SHA-256 `d3597453be672b9c2c4ef7e0c5c829a0abab33a64a84bc438b9ec53f084b24ac` · 367 pages · retrieved 2026-11-21

**Status: all checks pass** — 47 sections,
32,129 source tokens,
38 High / 1 Medium / 8 Low confidence.
Human-reviewed pages: 0.

## Verification checks

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | source integrity | PASS | sha256 matches manifest |
| 2 | determinism | PASS | enforced in CI: re-run extract.py and require an empty git diff |
| 3 | no insertion | PASS | every output token present in source |
| 4 | no omission | PASS | every source token present in output |
| 5 | page anchors | PASS | unique and ascending |
| 6 | TOC coverage | PASS | 47 sections tile the stream with no gaps or overlaps |
| 7 | front matter | PASS | all sections conform |
| 8 | chunk graph | PASS | 147 chunks, ids unique, links resolve |

## What these checks prove

Checks 3 and 4 compare normalised token streams between the source PDF and the
generated Markdown, section by section. Passing both means **no content was
invented and none was lost**: a paraphrase, a summary, an invented figure or a
dropped sentence each fail.

## What they do not prove

- **Reading order.** The same tokens in the wrong sequence pass every automated
  check. Multi-column and tabular pages are reported Low for this reason.
- **Correctness of the original.** We reproduce the document; we do not audit it.
- **Table structure.** Tabular pages are carried through as verbatim blocks, so
  their text is exact, but no check can prove a number is still in its row.

Structured data derived from tables is validated separately, on its own terms —
`data/budget-2027/sectors.json` checks that serial numbers run contiguously and that
every row has a sector, a name and an amount.

## Confidence rubric

| Band | Criteria |
|---|---|
| **High** | Single-column prose, heading found on one line, zero insertions, zero omissions. |
| **Medium** | As High, but the heading was inferred across wrapped lines, so the section title is an inference. |
| **Low** | Contains tabular or multi-column pages. Text is token-verified, but no automated check can prove a value is still in its original row. |

A band says nothing about whether a human has read the section; that is the
separate "reviewed" column.

## Sections

| ID | Title | Printed pages | Tokens | Status | Confidence | Reviewed | Signals |
|---|---|---|---|---|---|---|---|
| front | 81st Budget Speech | — | 16 | verified | **High** | no | single-column prose, single-line heading |
| 1 | Preamble | 1–6 | 2,048 | verified | **High** | no | single-column prose, single-line heading |
| 2 | Seven Strategic Objectives of the 2027 Budget | 6–10 | 1,197 | verified | **High** | no | single-column prose, single-line heading |
| 3 | Medium-Term Macroeconomic and Fiscal Path | 10–11 | 525 | verified | **High** | no | single-column prose, single-line heading |
| 4 | Strengthening the Legal Framework | 11–15 | 1,105 | verified | **High** | no | single-column prose, single-line heading |
| 5 | Free Trade Agreements | 15 | 152 | verified | **High** | no | single-column prose, single-line heading |
| 6 | Energy | 15–18 | 1,227 | verified | **High** | no | single-column prose, single-line heading |
| 7 | Digital Transformation and Development towards a Dig | 18–22 | 1,076 | verified | **High** | no | single-column prose, single-line heading |
| 8 | Education | 22–25 | 1,037 | verified | **High** | no | single-column prose, single-line heading |
| 9 | Towards an Economic Transformation through Research, | 25–26 | 337 | verified | **Medium** | no | heading inferred across wrapped lines |
| 10 | Development of Expressways and Highways | 26–28 | 521 | verified | **High** | no | single-column prose, single-line heading |
| 11 | Railway Electrification | 28 | 127 | verified | **High** | no | single-column prose, single-line heading |
| 12 | Micro, Small and Medium Enterprises Sector | 28–31 | 867 | verified | **High** | no | single-column prose, single-line heading |
| 13 | Port Development | 31–32 | 538 | verified | **High** | no | single-column prose, single-line heading |
| 14 | Development of Infrastructure in the Aviation Sector | 32–34 | 478 | verified | **High** | no | single-column prose, single-line heading |
| 15 | Industry, Trade and Investment | 34–36 | 797 | verified | **High** | no | single-column prose, single-line heading |
| 16 | Fisheries Industry | 36–37 | 463 | verified | **High** | no | single-column prose, single-line heading |
| 17 | Agriculture | 37–42 | 1,487 | verified | **High** | no | single-column prose, single-line heading |
| 18 | Plantation Sector | 42–43 | 449 | verified | **High** | no | single-column prose, single-line heading |
| 19 | Sports | 43–45 | 443 | verified | **High** | no | single-column prose, single-line heading |
| 20 | Social Protection and Empowerment | 45–47 | 819 | verified | **High** | no | single-column prose, single-line heading |
| 21 | Disaster Management | 47–48 | 154 | verified | **High** | no | single-column prose, single-line heading |
| 22 | Health Services | 48–50 | 844 | verified | **High** | no | single-column prose, single-line heading |
| 23 | Tourism Sector | 50–52 | 450 | verified | **High** | no | single-column prose, single-line heading |
| 24 | Environmental Management | 52–54 | 891 | verified | **High** | no | single-column prose, single-line heading |
| 25 | Transport | 54–56 | 649 | verified | **High** | no | single-column prose, single-line heading |
| 26 | Drinking Water Supply | 56–57 | 384 | verified | **High** | no | single-column prose, single-line heading |
| 27 | Housing and Urban Development | 57–60 | 1,068 | verified | **High** | no | single-column prose, single-line heading |
| 28 | Public Security | 60–62 | 366 | verified | **High** | no | single-column prose, single-line heading |
| 29 | Judiciary | 62–63 | 389 | verified | **High** | no | single-column prose, single-line heading |
| 30 | National Security | 63 | 226 | verified | **High** | no | single-column prose, single-line heading |
| 31 | Cultural and National Heritage | 63–64 | 392 | verified | **High** | no | single-column prose, single-line heading |
| 32 | Mass Media | 64–65 | 109 | verified | **High** | no | single-column prose, single-line heading |
| 33 | Clean Sri Lanka | 65–66 | 263 | verified | **High** | no | single-column prose, single-line heading |
| 34 | Public Administration and Public Services | 66–68 | 678 | verified | **High** | no | single-column prose, single-line heading |
| 35 | Public Sector Salaries and Pensions | 68–74 | 1,989 | verified | **High** | no | single-column prose, single-line heading |
| 36 | Tax Policy Proposals | 74–79 | 1,550 | verified | **High** | no | single-column prose, single-line heading |
| 37 | Borrowing Limit | 79 | 62 | verified | **High** | no | single-column prose, single-line heading |
| 38 | Supplementary Estimate for Ditwah Reconstruction – 2 | 79 | 125 | verified | **High** | no | single-column prose, single-line heading |
| 39 | Conclusion | 79–83 | 1,091 | verified | **Low** | no | tabular pages |
| A1 | Summary of Revenue Impact – 2027 | 83–84 | 82 | verified | **Low** | no | tabular pages |
| A2 | Summary of New Expenditure Proposals Presented in th | 84–88 | 723 | verified | **Low** | no | tabular pages |
| A3 | Summary of the Budget Estimates – 2027 | 88–90 | 307 | verified | **Low** | no | tabular pages |
| A4 | Gross Borrowings Requirement - 2027 | 90–91 | 94 | verified | **Low** | no | tabular pages |
| A5 | Technical Notes | 91–98 | 1,384 | verified | **Low** | no | tabular pages |
| A6 | Revision of Allowances for Public Officers | 98–103 | 729 | verified | **Low** | no | tabular pages |
| A7 | Summary of Key New Capital Expenditure included in t | 103 | 1,421 | verified | **Low** | no | tabular pages |
