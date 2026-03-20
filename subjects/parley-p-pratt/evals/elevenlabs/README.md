# Discord-derived ElevenLabs eval fixtures

This directory holds **curated** eval material derived from Discord conversations about Parley's Ghost.

It is intentionally split into two layers:

1. `discord_feedback.jsonl` — source-of-truth curation records pointing back to Discord messages / attachments
2. `scenarios.json` — evaluation scenarios suitable for `agent_rag.elevenlabs.evaluate_elevenlabs_agent(...)`

## Curation rules

- Raw Discord exports live outside the repo under `~/.hermes/downloads/discord-history/...`
- Raw audio remains primary; transcripts are secondary/derived
- Do **not** auto-promote Discord feedback directly into prompts or clean corpus text
- Convert only selected, reviewed feedback into scenarios here

## Current fixtures

- `discord-primary-source-boundary` — checks that the agent stays in Parley's own voice and distinguishes primary writings from later commentary
- `voice-review-2026-03-18` — metadata-only record for Carl's Discord voice memo; pending transcription/adjudication before scenario promotion

## Running the scenario file now

The CLI does not yet accept a scenario-file flag, but the underlying evaluator already accepts a `scenarios=` argument.

```bash
cd ~/Source/MormonTranshumanistAssociation/agent-rag
source .venv/bin/activate
PYTHONPATH=src python - <<'PY'
import json
from pathlib import Path
from agent_rag.elevenlabs import evaluate_elevenlabs_agent

root = Path('subjects/parley-p-pratt/evals/elevenlabs')
scenarios = json.loads((root / 'scenarios.json').read_text(encoding='utf-8'))
results = evaluate_elevenlabs_agent(
    target_dir=Path('subjects/parley-p-pratt/exports/targets/elevenlabs'),
    scenarios=scenarios,
)
for result in results:
    print(result.scenario_id, result.criteria_results)
PY
```

## Next step

Promote additional reviewed Discord feedback — especially audio notes once transcribed or adjudicated — into new scenarios here.
