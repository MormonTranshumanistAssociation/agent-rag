# agent-rag Bootstrap Implementation Plan

> **For Hermes:** implement this plan with a provenance-first, local-first bias. Prefer small, readable building blocks over premature complexity.

**Goal:** Create a reusable public repository for building citation-aware RAG corpora from the historical writings of specific individuals, starting with Parley P. Pratt.

**Architecture:** Use a subject-pack layout under `subjects/<slug>/` with human-authored YAML manifests, source metadata, curated clean text files, and generated JSONL exports. Provide a small Python package and CLI that can validate a subject pack and build retrieval-ready corpus/chunk exports from local text files.

**Tech Stack:** Python 3.9+, setuptools, PyYAML, pytest, GitHub Actions.

---

## Task 1: Repository scaffold and docs

**Objective:** Establish the repo layout, bootstrap documentation, and development metadata.

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `docs/architecture.md`
- Create: `docs/source-schema.md`
- Create: `docs/ingestion-workflow.md`
- Create: `docs/evaluation.md`

**Steps:**
1. Document the provenance-first design principles.
2. Define the repository layout and setup commands.
3. Explain the source schema and subject-pack conventions.
4. Keep the initial dependency surface intentionally small.

---

## Task 2: Test-first core package

**Objective:** Implement a minimal package that can load, validate, and build subject packs.

**Files:**
- Create: `tests/test_subject_pack.py`
- Create: `tests/test_cli.py`
- Create: `src/agent_rag/__init__.py`
- Create: `src/agent_rag/models.py`
- Create: `src/agent_rag/subject_pack.py`
- Create: `src/agent_rag/chunking.py`
- Create: `src/agent_rag/cli.py`

**Steps:**
1. Write failing tests for subject-pack validation and chunk export generation.
2. Implement only enough code to make the tests pass.
3. Keep the data model simple and explicit.
4. Use JSONL exports so downstream tooling can stay flexible.

---

## Task 3: Parley P. Pratt subject pack

**Objective:** Add the first fully curated subject pack with strong provenance metadata.

**Files:**
- Create: `subjects/parley-p-pratt/profile.yaml`
- Create: `subjects/parley-p-pratt/aliases.yaml`
- Create: `subjects/parley-p-pratt/sources.yaml`
- Create: `subjects/parley-p-pratt/notes.md`
- Create: `subjects/parley-p-pratt/clean/primary/*.md`

**Steps:**
1. Add concise biography/profile metadata.
2. Register high-value primary sources and a few secondary/context sources.
3. Seed the corpus with a few public-domain excerpts so the pipeline can produce a real export immediately.
4. Keep authored corpus texts separate from generated notes and planning docs.

---

## Task 4: Build outputs and CI

**Objective:** Produce generated exports and basic automated validation.

**Files:**
- Create: `subjects/parley-p-pratt/exports/` (generated)
- Create: `.github/workflows/ci.yml`

**Steps:**
1. Run the CLI locally to build corpus and chunks for Parley.
2. Commit generated JSONL outputs so the repo has a working example.
3. Add CI to run tests on push and pull request.
4. Push the bootstrap commit to `main`.

---

## Success Criteria

- The repository is usable immediately by a human collaborator.
- The first subject pack is well-documented and provenance-aware.
- `agent-rag validate subjects/parley-p-pratt` passes.
- `agent-rag build subjects/parley-p-pratt --output-dir subjects/parley-p-pratt/exports --chunk-size 700 --chunk-overlap 120` produces stable JSONL exports.
- Tests pass locally and in CI.
