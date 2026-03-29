# ElevenLabs ingestion and agent workflow

This workflow turns the `agent-rag` ElevenLabs target package into a live ElevenLabs knowledge base + conversational agent deployment.

## What the workflow does

`agent-rag elevenlabs-sync` now:

1. reads `exports/targets/elevenlabs/documents.jsonl`
2. converts each exported document into a single ElevenLabs text document with a provenance header baked into the retrieval text
3. syncs those documents into the ElevenLabs knowledge base
4. computes RAG indexes for all synced documents
5. creates or updates a conversational agent named **Parley's Ghost**
6. configures a local `widget.html` page for quick voice-chat testing
7. writes `sync-state.json` so reruns can reuse unchanged documents and recreate changed ones

## Why the ingestion text is reformatted

ElevenLabs text knowledge-base documents do not preserve arbitrary structured metadata fields the way our local JSONL exports do.

To keep provenance available at retrieval time, the sync step prepends a **citation/provenance header** to each uploaded document. This makes work title, source id, source URL, publication year, and rights information available to the agent when relevant chunks are retrieved.

## Voice selection

The default deployed voice is:

- **Eric — Smooth, Trustworthy** (`cjVigY5qzO86Huf0OWal`)

Reasoning:

- American male voice
- middle-aged rather than youthful
- conversational enough for live voice chat
- trustworthy/classy rather than overly theatrical

This felt like the best premade compromise for a historically grounded Parley persona.

## Commands

Build exports if needed:

```bash
source .venv/bin/activate
PYTHONPATH=src python -m agent_rag.cli build \
  subjects/parley-p-pratt \
  --output-dir subjects/parley-p-pratt/exports
```

## Secrets

Keep live credentials in a repo-local ignored `.env`, not in tracked files:

```bash
cp .env.example .env
# then fill in ELEVENLABS_API_KEY locally
```

The CLI now loads `.env` / `.env.local` from the repo root automatically before command parsing.

Sync into ElevenLabs and create/update the agent:

```bash
source .venv/bin/activate
export ELEVENLABS_API_KEY=...your key...
PYTHONPATH=src python -m agent_rag.cli elevenlabs-sync \
  subjects/parley-p-pratt \
  --output-dir subjects/parley-p-pratt/exports \
  --rebuild
```

Run the simple simulated-conversation eval pack:

```bash
source .venv/bin/activate
export ELEVENLABS_API_KEY=...your key...
PYTHONPATH=src python -m agent_rag.cli elevenlabs-eval \
  subjects/parley-p-pratt \
  --output-dir subjects/parley-p-pratt/exports
```

## Generated files

Under `subjects/parley-p-pratt/exports/targets/elevenlabs/` the workflow writes:

- `sync-state.json` — remote ElevenLabs document IDs + current agent ID
- `widget.html` — local embed page for quick browser testing
- `eval-results.json` — raw results from the canned eval scenarios

## Default eval themes

The built-in eval pack checks for:

1. grounded doctrine recall with provenance
2. explicit uncertainty on out-of-scope modern questions
3. preference for primary sources over later commentary

These are intentionally simple first-pass evals, meant to smoke-test the deployment rather than exhaustively benchmark it.
