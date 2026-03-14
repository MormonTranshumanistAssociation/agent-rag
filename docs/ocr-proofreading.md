# OCR Proofreading Workflow

For scan-derived texts, `agent-rag` should not ingest raw OCR directly into `clean/`.

Instead, use a conservative filter step first.

## Goals

- remove mechanical OCR artifacts without modernizing the text
- keep provenance explicit
- preserve authorial voice
- route uncertain readings into review rather than guessing

## Current CLI support

Prepare a review packet from OCR text:

```bash
PYTHONPATH=src python -m agent_rag.cli prepare-ocr \
  raw.txt \
  --output-dir review/late-persecutions-chapter-01 \
  --document-id late-persecutions-chapter-01 \
  --source-id late-persecutions-1840 \
  --work-title "Late Persecutions of the Church of Jesus Christ of Latter-day Saints" \
  --document-title "Chapter I" \
  --author "Parley P. Pratt"
```

This writes:

- `normalized.txt` — deterministic OCR cleanup
- `candidate.md` — front matter + normalized body, marked `ocr_status: needs_proofread`
- `proofread_prompt.md` — instructions for a proofreader agent or human reviewer

## What the filter currently fixes

- ligatures such as `ﬁ` → `fi`
- soft hyphens
- hyphenated line-break artifacts such as `begin-\nning` → `beginning`
- wrapped prose paragraphs (default mode)
- stray OCR punctuation such as carets and duplicated quote marks
- common honorific spacing glitches such as `Mr.S.` / `Mr, S.` → `Mr. S.`
- simple page-number artifact lines such as `( 4 )`
- punctuation debris inside broken words such as `in«-\nterpretation` → `interpretation`

Use `--preserve-linebreaks` for poetry or line-based material.

## Recommended downstream review

Use a proofreader agent, skill, or human reviewer to:

- correct obvious OCR mistakes conservatively
- confidently infer intended words when the remaining marks are plainly OCR debris
- avoid modernizing diction, spelling, or punctuation beyond removing that debris
- preserve lineation when it matters
- mark uncertain readings with `[[unclear]]`
- keep editorial/non-authorial matter separated from the subject's own text

## Why build our own proofreader workflow?

The existing OCR/document-extraction skill is good for **getting text out of scans**, but historical corpus work needs a second layer specialized for:

- old typography
- conservative correction
- provenance-aware review
- voice contamination avoidance

So the right approach is:

1. use general OCR extraction tools for raw text acquisition,
2. use `agent-rag`'s filter/review packet as the normalization boundary,
3. add a dedicated historical OCR proofreader skill on top of that workflow as it stabilizes.
