from __future__ import annotations

import re
from typing import List


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _advance_to_boundary(text: str, index: int) -> int:
    if index <= 0:
        return 0
    if index >= len(text):
        return len(text)

    while index < len(text) and text[index].isspace():
        index += 1

    if index < len(text) and not text[index - 1].isspace():
        while index < len(text) and not text[index].isspace():
            index += 1
        while index < len(text) and text[index].isspace():
            index += 1

    return index


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: List[str] = []
    start = 0
    text_length = len(normalized)

    while start < text_length:
        end = min(text_length, start + chunk_size)
        if end < text_length:
            preferred_breaks = [normalized.rfind("\n", start, end), normalized.rfind(" ", start, end)]
            best_break = max(preferred_breaks)
            if best_break > start + chunk_size // 2:
                end = best_break

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = max(end - overlap, start + 1)
        start = _advance_to_boundary(normalized, next_start)

    return chunks
