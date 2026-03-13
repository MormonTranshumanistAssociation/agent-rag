# Parley Remaining Works Ingestion Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add an OCR-assisted filter workflow and use it to ingest the remaining readily-available Parley P. Pratt works and key contextual materials without sacrificing provenance or voice separation.

**Architecture:** Treat the current clean Gutenberg corpus as the baseline. Add a conservative OCR-prep layer that normalizes extraction artifacts and generates proofreader-ready review packets before any scanned document is promoted into `clean/`. Then ingest the remaining primary works in priority order, keeping authorial texts separate from secondary and context materials.

**Tech Stack:** Python 3.9+, argparse, pathlib, PyYAML, pytest, existing `agent-rag` subject-pack build pipeline.

---

## Priority order

1. `late-persecutions-1840` — historical narrative, likely high value for voice + biography + persecution history
2. `mormonism-unveiled-1838` — polemical prose, high value for argumentative voice
3. `dialogue-joseph-smith-devil-1844` — satire, lower volume but useful stylistic coverage
4. `millennium-and-other-poems-1840` — poetry/hymn material, important but needs line-break-sensitive handling
5. high-value secondary/context additions after the primary corpus is stronger

---

### Task 1: Add OCR-prep workflow support

**Objective:** Create a conservative filter step before ingestion of scanned/OCR sources.

**Files:**
- Create: `src/agent_rag/ocr_filter.py`
- Modify: `src/agent_rag/cli.py`
- Create: `tests/test_ocr_filter.py`
- Create: `docs/ocr-proofreading.md`

**Steps:**
1. Write failing tests for OCR normalization and CLI packet generation.
2. Implement deterministic cleanup rules (ligatures, soft hyphens, hyphenated line breaks, wrapped prose paragraphs).
3. Add a CLI command that produces a proofreader-ready package with normalized text and a prompt/checklist.
4. Run focused tests, then the full suite.
5. Commit and push.

### Task 2: Create raw-source workspace conventions for Parley

**Objective:** Make remaining scan-driven ingestion reproducible.

**Files:**
- Create: `subjects/parley-p-pratt/raw/README.md`
- Create: `subjects/parley-p-pratt/raw/ocr/.gitkeep`
- Create: `subjects/parley-p-pratt/raw/scans/.gitkeep`
- Create: `subjects/parley-p-pratt/raw/review/.gitkeep`
- Modify: `subjects/parley-p-pratt/notes.md`

**Steps:**
1. Document where scans, OCR output, and reviewed packets should live.
2. Add notes about prose vs poetry handling.
3. Commit and push.

### Task 3: Ingest *Late Persecutions*

**Objective:** Add the next high-value narrative primary work.

**Files:**
- Modify: `subjects/parley-p-pratt/sources.yaml`
- Create: `subjects/parley-p-pratt/clean/primary/late-persecutions-*.md`
- Modify: `subjects/parley-p-pratt/notes.md`
- Modify: `subjects/parley-p-pratt/exports/**` (generated)

**Steps:**
1. Acquire scan/OCR text and run it through the OCR-prep workflow.
2. Segment by preface/chapter/section as appropriate.
3. Validate and build the subject pack.
4. Commit and push after CI is green.

### Task 4: Ingest *Mormonism Unveiled*

**Objective:** Add a major polemical work for stronger argumentative voice coverage.

**Files:**
- Modify: `subjects/parley-p-pratt/sources.yaml`
- Create: `subjects/parley-p-pratt/clean/primary/mormonism-unveiled-*.md`
- Modify: `subjects/parley-p-pratt/notes.md`
- Modify: `subjects/parley-p-pratt/exports/**` (generated)

**Steps:**
1. Acquire scan/OCR text and run it through the OCR-prep workflow.
2. Segment into retrieval-friendly units.
3. Validate, build, test, commit, and push.

### Task 5: Ingest shorter specialized works

**Objective:** Fill stylistic gaps with satire and poetry.

**Files:**
- Modify: `subjects/parley-p-pratt/sources.yaml`
- Create: `subjects/parley-p-pratt/clean/primary/dialogue-joseph-smith-devil-*.md`
- Create: `subjects/parley-p-pratt/clean/primary/millennium-and-other-poems-*.md`
- Modify: `subjects/parley-p-pratt/notes.md`
- Modify: `subjects/parley-p-pratt/exports/**` (generated)

**Steps:**
1. Ingest *Dialogue* with prose defaults.
2. Ingest *Millennium and Other Poems* with line-break-preserving handling.
3. Validate, build, test, commit, and push.

### Task 6: Add initial about-Parley materials

**Objective:** Start the non-authorial comparison corpus without contaminating the primary voice.

**Files:**
- Modify: `subjects/parley-p-pratt/sources.yaml`
- Create: `subjects/parley-p-pratt/clean/secondary/*.md` and/or `clean/context/*.md`
- Modify: `subjects/parley-p-pratt/notes.md`
- Modify: `subjects/parley-p-pratt/exports/**` (generated)

**Steps:**
1. Add one or two carefully bounded secondary/context sources.
2. Keep source types explicit.
3. Rebuild and verify that prompt/corpus separation assumptions still hold.
4. Commit and push.

---

## Acceptance criteria

- OCR-driven works go through a reproducible filter/review step before entering `clean/`.
- Remaining readily-available Parley primary works are ingested at appropriate section granularity.
- Poetry preserves meaningful line structure.
- Secondary/context materials remain clearly separated from primary voice.
- Each increment is committed and pushed to `main` only after tests pass and CI is green.
