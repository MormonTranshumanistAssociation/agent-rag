# Evaluation

Historical RAG evaluation should measure more than retrieval hit rate.

## Evaluation goals

A good corpus should help downstream agents:

1. retrieve relevant passages,
2. cite the right source,
3. distinguish the subject's own voice from later commentary,
4. avoid chronology mistakes,
5. surface uncertainty when sources conflict.

## Core evaluation dimensions

### 1. Retrieval relevance

Questions:

- Do the top chunks actually address the query?
- Are key works represented in the chunk set?
- Are chunks too small or too large to be useful?

### 2. Citation fidelity

Questions:

- Can the system identify the correct `source_id`?
- Does it preserve work title and source URL?
- Can a human trace the chunk back to a local clean document?

### 3. Voice contamination

Questions:

- Does a response about Parley quote Parley, or merely summarize him?
- Are secondary/modern interpretations being mistaken for primary text?
- Are generated notes leaking into retrieval?

### 4. Temporal coherence

Questions:

- Does the system collapse early and late periods together?
- Does it attribute later formulations to earlier phases of the subject's life?
- Does it confuse publication year, composition year, and later editions?

### 5. Corpus hygiene

Questions:

- Are there duplicate excerpts from overlapping editions?
- Are OCR errors degrading retrieval?
- Are chunks broken mid-sentence or mid-thought?

## Suggested early benchmark tasks

For each subject pack, create hand-check prompts such as:

- “What themes dominate this author’s early autobiographical writing?”
- “What evidence exists that this passage is in the subject’s own voice?”
- “Which texts discuss theology versus personal history?”
- “What later scholars say about the subject’s murder, and how does that differ from the subject’s own writing?”

## Planned future evaluation assets

- golden retrieval queries per subject
- citation-verification fixtures
- contamination tests mixing primary and secondary corpora
- timeline-sensitive question sets
- duplicate-detection checks across editions

## For the Parley bootstrap

Near-term evaluation priorities:

1. keep primary works dominant in the authored corpus,
2. prevent biography/context sources from masquerading as primary voice,
3. expand to additional Parley texts without losing edition clarity,
4. compare excerpts across different editions of the same work.
