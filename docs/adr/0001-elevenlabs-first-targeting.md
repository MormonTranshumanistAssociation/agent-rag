# ADR 0001: Prefer ElevenLabs-first targeting, with a cloud-native secondary backend

- **Status:** Accepted
- **Date:** 2026-03-13

## Context

`agent-rag` is intended to support downstream historical-agent experiences, including Parley's Ghost. We already expect to use ElevenLabs for narration because of its superior voice nuance and latency. ElevenLabs now also offers native RAG/knowledge features, making it the most natural first integration target.

At the same time, the repository should not hardcode itself around a specialized vector database unless that database provides an essential missing capability. If a second backend is required, a cloud-native option such as Amazon Bedrock is preferable because it tends to integrate more naturally with surrounding infrastructure.

## Decision

We will structure the export pipeline in two layers:

1. **Canonical provenance-first corpus outputs** remain the source of truth.
2. **Target packages** reshape the canonical corpus for downstream integrations.

Current target priority:

1. **Primary target:** ElevenLabs native narration + native RAG workflows
2. **Secondary target:** Amazon Bedrock or a similar generic cloud-native retrieval service
3. **Optional later targets:** specialized vector databases only if they provide an essential missing capability that the first two paths do not

## Consequences

### Positive

- Keeps the durable asset vendor-neutral
- Lets us optimize first for the stack we already intend to use
- Avoids premature lock-in to Pinecone or another specialized vector store
- Makes it easier to compare downstream integrations without re-curating the corpus

### Negative / tradeoffs

- We still need to maintain some provider-specific packaging logic
- Target packages may lag behind vendor API changes until direct upload tooling is added
- Bedrock is treated as a representative cloud-native backend, not a universal retrieval abstraction

## Implementation notes

- Canonical outputs stay at the top of each `exports/` directory.
- Target packages live under `exports/targets/<target>/`.
- The first built-in targets are `elevenlabs` and `bedrock`.
- Future direct-upload tooling should build on these packages rather than bypassing the canonical corpus.
