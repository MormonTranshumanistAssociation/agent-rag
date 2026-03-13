from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


VALID_SOURCE_TYPES = {"primary", "secondary", "context"}


@dataclass(frozen=True)
class SubjectProfile:
    id: str
    display_name: str
    canonical_name: str
    birth_year: int | None
    death_year: int | None
    summary: str


@dataclass(frozen=True)
class SourceRecord:
    id: str
    title: str
    author: str
    publication_year: int | None
    source_type: str
    genre: str
    url: str
    rights: str
    extra: Dict[str, Any]


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    source_id: str
    work_title: str
    document_title: str
    author: str
    composed_year: int | None
    source_type: str
    text: str
    path: Path
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class SubjectPack:
    profile: SubjectProfile
    aliases: List[str]
    sources: Dict[str, SourceRecord]
    documents: List[DocumentRecord]


@dataclass(frozen=True)
class BuildResult:
    subject_id: str
    output_dir: Path
    document_count: int
    chunk_count: int
