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

- `manifest.json`
- `corpus.jsonl`
- `chunks.jsonl`

## Subject-pack contract

A valid subject pack currently requires:

- `profile.yaml`
- `sources.yaml`
- at least one clean text document under `clean/`

Optional but recommended:

- `aliases.yaml`
- `notes.md`
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
