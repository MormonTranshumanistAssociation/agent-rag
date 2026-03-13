# Prompting

`agent-rag` is not only a corpus builder; it is also a place to preserve the behavioral values that downstream agents should follow.

## Why prompt artifacts belong here

A historical agent can fail even with a good corpus if its prompt encourages style over fidelity. The prompt should therefore reinforce the same values that the data pipeline enforces:

- provenance before performance
- primary sources before secondary interpretation
- explicit source-class distinctions
- citation fidelity
- chronology and edition awareness
- uncertainty when evidence is thin or conflicting

## Subject-pack convention

A subject pack may include:

```text
subjects/<slug>/prompts/
  system.md
```

If `prompts/system.md` exists, `agent-rag build` copies it into:

```text
subjects/<slug>/exports/prompts/system.md
```

If it does not exist, the build generates a default system prompt from subject metadata.

## Recommended prompt content

A good historical-agent system prompt should state:

1. **Identity** — who the subject is and what the assistant is trying to represent
2. **Source hierarchy** — primary over secondary over context for claims about the subject's own thought and voice
3. **Citation expectations** — include work title, source id, and source URL when possible
4. **Voice contamination rules** — do not let later biography or generated notes masquerade as the subject
5. **Chronology rules** — preserve time, edition, and attribution boundaries
6. **Uncertainty rules** — admit ambiguity and conflicting evidence directly

## Current target packaging

Target manifests under `exports/targets/<target>/manifest.json` reference the recommended canonical system prompt at:

```text
../../prompts/system.md
```

This keeps prompt values and retrieval artifacts aligned across ElevenLabs-first and Bedrock/cloud-native downstream integrations.
