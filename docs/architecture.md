# Architecture

## Summary

`agent-rag` is a **local-first, provenance-first corpus builder** for historical RAG systems.

The core abstraction is a **subject pack**:

```text
subjects/<subject-slug>/
```

A subject pack combines:

- subject identity metadata
- alias metadata
- a curated source registry
- optional prompt files describing downstream agent values
- clean text files intended for retrieval/export
- generated outputs derived from those texts

## Design goals

### 1. Provenance before embeddings

Every downstream retrieval artifact should preserve enough metadata to answer:

- who is this text about?
- who authored it?
- what source work did it come from?
- what edition or publication year is represented?
- where can a human verify it?

### 2. Strong separation of content classes

We explicitly distinguish:

- **primary** — texts authored by the historical subject
- **secondary** — scholarship or interpretive works about the subject
- **context** — reference pages, timelines, indexes, or related framing materials

This reduces “voice contamination,” where an agent begins sounding like a biographer instead of the historical writer.

### 3. Local-first curation

The first durable asset is not a vector database. It is a local, inspectable corpus.

This repository therefore prioritizes:

- YAML manifests
- plain text / Markdown source files
- JSONL exports
- simple Python validation and build steps

### 4. Small moving parts

The current bootstrap intentionally avoids heavy framework lock-in.

Outputs are neutral, so they can later feed:

- local embedding workflows
- hosted vector databases
- fine-tuning pipelines
- agent memory stores
- evaluation harnesses

### 5. Canonical corpus first, vendor adapters second

The canonical corpus remains the durable asset.

`agent-rag` therefore distinguishes between:

- **canonical outputs** — the provenance-first `manifest.json`, `corpus.jsonl`, and `chunks.jsonl`
- **prompt artifacts** — recommended system prompts under `exports/prompts/`
- **target packages** — reshaped exports under `exports/targets/<target>/`

Current target priority:

1. **ElevenLabs** for native narration and native RAG workflows
2. **Amazon Bedrock / generic cloud-native retrieval** for broader infrastructure integration
3. **Specialized vector databases** only when the first two paths miss an essential capability

This keeps the repository interoperable without prematurely centering a specific vector database.

## Current pipeline

### Inputs

- `profile.yaml`
- `aliases.yaml`
- `sources.yaml`
- `clean/**/*.md|txt`

### Processing

1. validate required metadata
2. parse clean documents and front matter
3. resolve each document to a registered source
4. normalize text
5. chunk text with overlap
6. emit corpus and chunk JSONL files

### Outputs

Canonical outputs:

- `manifest.json`
- `corpus.jsonl`
- `chunks.jsonl`

Prompt artifacts:

- `prompts/system.md`

Target packages:

- `targets/elevenlabs/manifest.json`
- `targets/elevenlabs/documents.jsonl`
- `targets/bedrock/manifest.json`
- `targets/bedrock/chunks.jsonl`

## Subject-pack contract

A valid subject pack currently requires:

- `profile.yaml`
- `sources.yaml`
- at least one clean text document under `clean/`

Optional but recommended:

- `aliases.yaml`
- `notes.md`
- `prompts/` human-authored prompt files
- `raw/` source captures
- `exports/` generated outputs

## Document handling

Clean documents are Markdown or text files stored under `clean/`.

Markdown files may begin with YAML front matter. The current build pipeline expects front matter fields such as:

- `document_id`
- `source_id`
- `work_title`
- `document_title`
- `author`
- `source_type`
- `composed_year` (optional)

The file body is treated as the retrieval text.

## Prompt handling

Subject packs may include a `prompts/` directory with human-authored prompt files.

Current behavior:

- `prompts/system.md`, if present in the subject pack, is copied into `exports/prompts/system.md`
- if no authored `prompts/system.md` exists, the build generates a default system prompt from subject metadata
- target manifests reference the canonical exported system prompt so downstream integrations can keep data and instructions aligned

The intended prompt values mirror the corpus architecture itself: prefer primary sources, cite provenance, avoid voice contamination, preserve chronology, and surface uncertainty.

## Why generated exports are committed for now

This bootstrap commits generated exports for the Parley pack because:

- the repo is still small
- it provides an immediately inspectable example
- collaborators can see expected output shape without running code first

Later, if corpora become large, generated outputs may move to release assets or selectively committed fixtures.

## Planned evolution

Near-term architectural expansions:

1. raw-source acquisition conventions
2. OCR/transcription workflow tracking
3. explicit edition lineage fields
4. richer document-level provenance
5. retrieval evaluation datasets
6. multiple subject-pack export joins
7. direct upload/integration tooling for target packages once vendor workflows are finalized
