# agent-rag

Tools and pipelines for building **provenance-aware RAG corpora** from the historical writings of specific individuals.

This repository starts with **Parley P. Pratt** as the first subject pack, but it is designed to support many future figures without mixing primary texts, secondary scholarship, and generated notes.

## Why this exists

Most historical RAG datasets fail in one of three ways:

1. they lose track of **where text came from**,
2. they mix **authorial voice** with later commentary, or
3. they optimize for embeddings before they establish a trustworthy corpus.

`agent-rag` takes the opposite approach:

- **provenance first**
- **local-first curation**
- **clear separation of primary vs. secondary material**
- **simple JSONL exports for downstream tools**

## Current status

Bootstrap v0.1 includes:

- a documented repository layout
- a minimal Python package + CLI
- validation for subject packs
- chunk export generation for local clean texts
- a first curated subject pack for **Parley P. Pratt**
- public-domain seed excerpts from Parley's writings
- pytest coverage and a GitHub Actions CI workflow

## Repository layout

```text
agent-rag/
  docs/
  src/agent_rag/
  subjects/
    parley-p-pratt/
      profile.yaml
      aliases.yaml
      sources.yaml
      notes.md
      clean/
      exports/
  tests/
```

## Quickstart

Recommended local clone location:

```bash
mkdir -p ~/Source/MormonTranshumanistAssociation
cd ~/Source/MormonTranshumanistAssociation
git clone https://github.com/MormonTranshumanistAssociation/agent-rag.git
cd agent-rag
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

Run tests:

```bash
PYTHONPATH=src python -m pytest -q
```

Validate the Parley subject pack:

```bash
PYTHONPATH=src python -m agent_rag.cli validate subjects/parley-p-pratt
```

Build retrieval exports:

```bash
PYTHONPATH=src python -m agent_rag.cli build \
  subjects/parley-p-pratt \
  --output-dir subjects/parley-p-pratt/exports \
  --chunk-size 700 \
  --chunk-overlap 120
```

## CLI

### Validate a subject pack

```bash
agent-rag validate subjects/parley-p-pratt
```

Checks:

- required manifest files exist
- profile fields are present
- source IDs are unique
- clean documents include required front matter
- document `source_id` values resolve to known sources

### Build a subject pack

```bash
agent-rag build \
  subjects/parley-p-pratt \
  --output-dir subjects/parley-p-pratt/exports \
  --chunk-size 700 \
  --chunk-overlap 120
```

Outputs:

- `manifest.json` — summary counts and build settings
- `corpus.jsonl` — one record per clean document
- `chunks.jsonl` — retrieval-ready text chunks with metadata

## Subject-pack model

Each subject lives in `subjects/<slug>/`.

Core files:

- `profile.yaml` — subject identity and summary
- `aliases.yaml` — known variant names
- `sources.yaml` — curated source registry
- `notes.md` — human research notes, priorities, and caveats
- `clean/` — local clean texts used to build exports
- `exports/` — generated JSON/JSONL output

## Design principles

- **Primary texts stay distinct from secondary analysis.**
- **Generated notes are not treated as corpus text.**
- **Every exported chunk carries source metadata.**
- **Human-editable manifests are preferred over opaque ingestion.**
- **The pipeline should remain easy to inspect and repair.**

## Near-term roadmap

- add raw-source acquisition conventions and OCR workflow
- add stronger corpus normalization utilities
- add more Parley texts and richer source coverage
- add retrieval evaluation fixtures
- add additional historical subjects

## Seed Parley sources currently registered

Primary works already cataloged include:

- *A Voice of Warning* (1837)
- *Mormonism Unveiled* (1838)
- *The Millennium and Other Poems* (1840)
- *Late Persecutions of the Church of Jesus Christ of Latter-day Saints* (1840)
- *A Dialogue between Joseph Smith and the Devil* (1844)
- *Key to the Science of Theology* (1855)
- *The Autobiography of Parley Parker Pratt* (1888 ed.)

See `subjects/parley-p-pratt/notes.md` and `subjects/parley-p-pratt/sources.yaml` for details.
