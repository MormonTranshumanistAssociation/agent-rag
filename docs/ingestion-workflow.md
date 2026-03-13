# Ingestion Workflow

This repository is optimized for **careful historical corpus building**, not one-click scraping.

## Guiding rule

Do not treat “downloaded text” as “clean corpus text.”

A source only becomes part of the retrieval corpus after it has:

1. been identified,
2. been classified,
3. been documented in `sources.yaml`,
4. been reviewed by a human, and
5. been written into `clean/` with traceable metadata.

## Workflow for a new subject

### 1. Create a subject folder

```text
subjects/<slug>/
```

Add:

- `profile.yaml`
- `aliases.yaml`
- `sources.yaml`
- `notes.md`
- optional `prompts/` files if you already know the downstream agent values you want to preserve

### 2. Build the initial source registry

Start with a small list of high-value sources:

- core primary works
- one or two trusted secondary sources
- one or two context/reference pages

### 3. Capture raw material

Keep raw scans, OCR output, or downloaded text outside the final clean corpus until reviewed.

Suggested future layout:

```text
raw/
  scans/
  ocr/
  transcripts/
```

### 4. Run OCR text through a proofreading filter when needed

If a source comes from scans or OCR, do not move the raw text directly into `clean/`.

Instead, prepare a review packet first:

```bash
PYTHONPATH=src python -m agent_rag.cli prepare-ocr \
  raw.txt \
  --output-dir review/<document-id> \
  --document-id <document-id> \
  --source-id <source-id> \
  --work-title "<work title>" \
  --document-title "<document title>" \
  --author "<author>"
```

This creates a normalized OCR text, a candidate Markdown document, and a proofread prompt for an agent or human reviewer.

### 5. Produce clean text documents

Write or copy reviewed corpus text into `clean/`.

Suggested subfolders:

```text
clean/
  primary/
  secondary/
  context/
```

Each clean Markdown file should include YAML front matter linking it back to a `source_id`.

### 6. Author or review agent prompts

If the downstream experience depends on stable behavioral values, encode them in `prompts/system.md`.

Recommended values to state explicitly:

- prefer primary sources for the subject's own voice
- distinguish primary, secondary, and context materials
- cite provenance and avoid invented quotations
- preserve chronology and edition boundaries
- surface uncertainty when sources conflict

If no authored prompt is present, `agent-rag build` will generate a default `exports/prompts/system.md` from subject metadata.

### 7. Validate the pack

```bash
PYTHONPATH=src python -m agent_rag.cli validate subjects/<slug>
```

### 8. Build exports

```bash
PYTHONPATH=src python -m agent_rag.cli build \
  subjects/<slug> \
  --output-dir subjects/<slug>/exports \
  --chunk-size 700 \
  --chunk-overlap 120
```

By default this now produces:

- the canonical provenance-first corpus outputs,
- an ElevenLabs-oriented document package, and
- a Bedrock/cloud-native chunk package.

If you only want one downstream package, specify `--target` explicitly:

```bash
PYTHONPATH=src python -m agent_rag.cli build \
  subjects/<slug> \
  --output-dir subjects/<slug>/exports \
  --target elevenlabs
```

### 9. Inspect outputs manually

Check:

- canonical metadata looks correct
- ElevenLabs target records preserve document-level provenance and citation URLs
- Bedrock/cloud target records preserve chunk-level metadata
- chunk text is readable
- source IDs are preserved
- generated chunks do not blend unrelated texts

## What belongs in `notes.md`

Use `notes.md` for:

- research priorities
- unresolved source questions
- ambiguity around editions or attribution
- warnings about OCR quality
- ideas for future ingestion

Do **not** treat `notes.md` as corpus text.

## Current limitations

The current bootstrap does not yet automate:

- web ingestion
- OCR
- citation extraction from scans
- edition reconciliation
- de-duplication across overlapping editions

That is intentional. The goal is to establish trustworthy ground truth before automating more aggressively.
