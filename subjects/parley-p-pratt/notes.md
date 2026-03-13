# Parley P. Pratt research notes

## Why Parley is the bootstrap subject

Parley P. Pratt is an excellent first subject for `agent-rag` because he combines:

- a strong and distinctive prose voice
- multiple genres of writing
- a well-documented historical life
- public-domain editions of several major works
- enough secondary scholarship to test provenance boundaries

## Initial biography summary

Parley Parker Pratt (1807-1857) was an early leader in the Latter Day Saint movement. He became one of the original members of the Quorum of the Twelve Apostles in 1835 and was a major missionary, polemicist, theologian, poet, and autobiographical writer. His writings helped define and popularize early Latter-day Saint doctrine, and his life intersects with key early movement events: conversion around the Book of Mormon in 1830, missionary work tied to Sidney Rigdon's circle, Missouri imprisonment, the Nauvoo and pioneer eras, and his murder in Arkansas in 1857.

## Primary-source priorities

Highest-value first-ingest works:

1. *A Voice of Warning* (1837)
2. *Key to the Science of Theology* (1855)
3. *The Autobiography of Parley Parker Pratt* (1888 edition of a posthumous work)
4. *Late Persecutions of the Church of Jesus Christ of Latter-day Saints* (1840)
5. *Mormonism Unveiled* (1838)
6. *The Millennium and Other Poems* (1840)
7. *A Dialogue between Joseph Smith and the Devil* (1844)

## Corpus-design cautions

### 1. Do not blend Parley's voice with later biography

Wikipedia, Joseph Smith Papers, library pages, and journal articles are useful for chronology, bibliography, and context, but they are not the subject's own voice.

### 2. Watch the autobiography carefully

The Project Gutenberg / 1888 text includes editorial framing from Parley P. Pratt Jr. The autobiographical body is still highly valuable, but front matter and later editorial materials should be tracked explicitly.

### 3. Track editions, not just titles

Several texts exist in multiple editions. Later editions may include revisions, editorial changes, or formatting differences that matter for retrieval and voice analysis.

### 4. Keep generated notes out of the retrieval corpus

This `notes.md` file is for researchers and maintainers, not for authorial retrieval.

## Seed excerpts included in this bootstrap

The clean corpus currently includes short public-domain excerpts from:

- *A Voice of Warning*
- *Key to the Science of Theology*
- *The Autobiography of Parley Parker Pratt*

These are not yet a full corpus; they are a working seed set to prove the repository structure and export pipeline.

## Good next steps

- ingest a longer autobiographical section with chapter boundaries
- add *Late Persecutions* as a historical-narrative counterpoint
- add poetry/hymn material to widen stylistic coverage
- introduce explicit edition metadata fields
- add duplicate-detection across overlapping editions
