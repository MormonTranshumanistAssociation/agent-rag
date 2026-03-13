# Export Targets for ElevenLabs-First + Cloud-Native Secondary Backend Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add explicit export-target support so `agent-rag` can keep a canonical provenance-first corpus while generating target-ready packages for ElevenLabs first and a generic cloud-native/Bedrock-style backend second.

**Architecture:** Keep the current top-level canonical build artifacts (`manifest.json`, `corpus.jsonl`, `chunks.jsonl`) as the source of truth. Add a small export-target registry that writes additional provider-specific packages under `exports/targets/<target>/`, with built-in targets for `elevenlabs` and `bedrock` plus manifest metadata describing intended ingestion shape.

**Tech Stack:** Python 3.9+, dataclasses, pathlib, argparse, PyYAML, pytest.

---

### Task 1: Add failing tests for target export generation

**Objective:** Define the desired output shape before implementation.

**Files:**
- Modify: `tests/test_subject_pack.py`

**Steps:**
1. Add a failing test that builds a subject pack and expects:
   - the canonical top-level files to still exist,
   - `targets/elevenlabs/manifest.json` and `targets/elevenlabs/documents.jsonl`,
   - `targets/bedrock/manifest.json` and `targets/bedrock/chunks.jsonl`.
2. Add assertions that ElevenLabs output is document-oriented and Bedrock output is chunk-oriented.
3. Run the focused test and confirm failure.

### Task 2: Add failing CLI test for `--target`

**Objective:** Lock in the CLI surface for selecting export targets.

**Files:**
- Modify: `tests/test_cli.py`

**Steps:**
1. Add a failing test that runs `agent-rag build ... --target elevenlabs --target bedrock`.
2. Assert the build succeeds and creates the expected target directories.
3. Run the focused test and confirm failure.

### Task 3: Implement export target registry and builders

**Objective:** Create the minimal production code needed for the tests to pass.

**Files:**
- Create: `src/agent_rag/export_targets.py`
- Modify: `src/agent_rag/models.py`
- Modify: `src/agent_rag/subject_pack.py`

**Steps:**
1. Add dataclasses for export-target metadata and build outputs.
2. Implement built-in targets:
   - `elevenlabs`: one record per document with citation/provenance metadata,
   - `bedrock`: one record per chunk with flattened metadata suitable for generic cloud retrieval.
3. Update `build_subject_pack()` to accept a `targets` list and emit built-in target packages after canonical files are written.
4. Keep the canonical outputs unchanged.

### Task 4: Implement CLI plumbing and documentation updates

**Objective:** Expose the new behavior cleanly and document the architectural decision.

**Files:**
- Modify: `src/agent_rag/cli.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/ingestion-workflow.md`
- Create: `docs/adr/0001-elevenlabs-first-targeting.md`

**Steps:**
1. Add `--target` (repeatable) to `agent-rag build`.
2. Default builds to canonical + the built-in recommended targets.
3. Update docs to describe:
   - canonical corpus as source of truth,
   - ElevenLabs as the primary integration target,
   - Bedrock/cloud-native as the secondary target,
   - specialized vector DBs as optional later adapters.
4. Add an ADR capturing the decision.

### Task 5: Regenerate fixtures and verify

**Objective:** Make sure the repo reflects the new output structure and remains green.

**Files:**
- Modify: `subjects/parley-p-pratt/exports/**` (generated)

**Steps:**
1. Run the full pytest suite.
2. Rebuild the Parley exports with the new default targets.
3. Inspect the generated target manifests for provenance/citation fields.
4. Confirm `git diff` is limited to the planned files.

---

## Acceptance Criteria

- Canonical exports remain stable and readable.
- `build_subject_pack()` can emit named export targets.
- ElevenLabs and Bedrock target packages are generated automatically by default.
- CLI users can restrict builds with `--target`.
- Documentation clearly states the new target priority order.
- Tests pass locally.
