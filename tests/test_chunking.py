from __future__ import annotations

import re

from agent_rag.chunking import chunk_text


def test_chunk_text_preserves_full_token_boundaries_with_overlap() -> None:
    text = " ".join(f"w{i:03d}" for i in range(30))

    chunks = chunk_text(text, chunk_size=28, overlap=8)

    assert len(chunks) > 1
    assert all(re.fullmatch(r"w\d{3}(?: w\d{3})*", chunk) for chunk in chunks)
