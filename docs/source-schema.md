# Source Schema

This document describes the human-authored metadata expected in `subjects/<slug>/sources.yaml`.

## Top-level structure

```yaml
sources:
  - id: voice-of-warning-1837
    title: A Voice of Warning
    author: Parley P. Pratt
    publication_year: 1837
    source_type: primary
    genre: theological_treatise
    url: https://www.gutenberg.org/ebooks/35554
    rights: public_domain
```

## Required fields

### `id`
Stable machine-readable identifier for the source.

Guidelines:

- lowercase
- kebab-case
- include year when useful
- keep stable even if notes improve later

### `title`
Human-readable source title.

### `author`
Primary author or responsible editor/organization.

### `publication_year`
Best known publication year for the represented edition or source record.

This field is **recommended but optional** in the current bootstrap, because some
reference pages and rolling web resources do not map cleanly to a single
publication year.

### `source_type`
Allowed values:

- `primary`
- `secondary`
- `context`

### `genre`
Short descriptive label, such as:

- `autobiography`
- `theological_treatise`
- `poetry`
- `polemic`
- `reference_biography`
- `journal_article`

### `url`
Canonical or best-available location for human verification. The current bootstrap validator expects a non-empty URL field.

### `rights`
Current rights status or access note.

Examples:

- `public_domain`
- `unknown`
- `copyrighted_excerpt_only`
- `library_scan`

## Recommended extra fields

The current code ignores these fields, but curators should use them freely.

Recommended examples:

- `edition`
- `publisher`
- `location`
- `priority`
- `ingest_status`
- `notes`
- `digital_source`
- `preferred_source_format`
- `verification_url`
- `scan_url`
- `transcript_url`
- `stance`
- `quality`

For example, when a Project Gutenberg edition exists, curators may want to record both the main verification page and the specific format used for ingestion, such as `preferred_source_format: gutenberg_html` or `preferred_source_format: gutenberg_plaintext`.

## Source-type guidance

### Primary

Use for texts authored by the subject or dictated/issued in a form that should count as the subject's own voice.

For Parley P. Pratt, examples include:

- *A Voice of Warning*
- *Key to the Science of Theology*
- *The Autobiography of Parley Parker Pratt*

### Secondary

Use for interpretive scholarship, biographical studies, or analytical essays.

Examples:

- BYU Studies articles
- academic monographs
- modern biographies

### Context

Use for material that is valuable for factual grounding but should not be treated as the subject's voice.

Examples:

- Wikipedia
- Joseph Smith Papers person page
- library catalog records
- chronology pages

## Clean-document linkage

Every clean document under `clean/` should reference one source record by `source_id` in YAML front matter.

Example:

```markdown
---
document_id: autobiography-childhood-excerpt
source_id: autobiography-1888
work_title: The Autobiography of Parley Parker Pratt
document_title: Childhood and reading excerpt
author: Parley P. Pratt
composed_year: 1888
source_type: primary
---
```

## Versioning philosophy

- treat `sources.yaml` as a curated catalog, not a dump
- preserve stable IDs
- improve metadata incrementally
- add notes rather than silently overwriting ambiguity
