from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class ExportTargetDefinition:
    name: str
    provider: str
    priority: str
    description: str
    recommended_ingestion_unit: str
    output_filename: str
    builder: Callable[[Sequence[Dict[str, Any]], Sequence[Dict[str, Any]]], List[Dict[str, Any]]]


DEFAULT_EXPORT_TARGETS = ("elevenlabs", "bedrock")


def _document_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "subject_id": record["subject_id"],
        "subject_name": record["subject_name"],
        "document_id": record["document_id"],
        "document_title": record["document_title"],
        "work_title": record["work_title"],
        "author": record["author"],
        "source_id": record["source_id"],
        "source_title": record["source_title"],
        "source_type": record["source_type"],
        "publication_year": record["publication_year"],
        "source_url": record["source_url"],
        "rights": record["rights"],
        "path": record.get("path"),
    }


def _chunk_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chunk_id": record["chunk_id"],
        "chunk_index": record["chunk_index"],
        "subject_id": record["subject_id"],
        "subject_name": record["subject_name"],
        "document_id": record["document_id"],
        "document_title": record["document_title"],
        "work_title": record["work_title"],
        "author": record["author"],
        "source_id": record["source_id"],
        "source_title": record["source_title"],
        "source_type": record["source_type"],
        "publication_year": record["publication_year"],
        "source_url": record["source_url"],
        "rights": record["rights"],
    }


def _build_elevenlabs_records(
    corpus_records: Sequence[Dict[str, Any]], chunk_records: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    del chunk_records
    return [
        {
            "id": record["document_id"],
            "title": record["document_title"],
            "text": record["text"],
            "metadata": _document_metadata(record),
        }
        for record in corpus_records
    ]


def _build_bedrock_records(
    corpus_records: Sequence[Dict[str, Any]], chunk_records: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    del corpus_records
    return [
        {
            "id": record["chunk_id"],
            "text": record["text"],
            "metadata": _chunk_metadata(record),
        }
        for record in chunk_records
    ]


EXPORT_TARGETS: Dict[str, ExportTargetDefinition] = {
    "elevenlabs": ExportTargetDefinition(
        name="elevenlabs",
        provider="ElevenLabs",
        priority="primary",
        description="Document-oriented package for ElevenLabs native narration and RAG ingestion.",
        recommended_ingestion_unit="document",
        output_filename="documents.jsonl",
        builder=_build_elevenlabs_records,
    ),
    "bedrock": ExportTargetDefinition(
        name="bedrock",
        provider="Amazon Bedrock",
        priority="secondary",
        description="Chunk-oriented package for Bedrock or similar cloud-native retrieval backends.",
        recommended_ingestion_unit="chunk",
        output_filename="chunks.jsonl",
        builder=_build_bedrock_records,
    ),
}


def resolve_export_targets(targets: Iterable[str] | None = None) -> List[str]:
    requested = list(DEFAULT_EXPORT_TARGETS if targets is None else targets)
    resolved: List[str] = []
    for target in requested:
        normalized = str(target).strip().lower()
        if not normalized:
            continue
        if normalized not in EXPORT_TARGETS:
            raise ValueError(
                f"Unknown export target '{target}'. Available targets: {', '.join(sorted(EXPORT_TARGETS))}"
            )
        if normalized not in resolved:
            resolved.append(normalized)
    return resolved


def _write_jsonl(path: Path, records: Sequence[Dict[str, Any]]) -> None:
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_target_exports(
    destination: Path,
    corpus_records: Sequence[Dict[str, Any]],
    chunk_records: Sequence[Dict[str, Any]],
    targets: Iterable[str] | None = None,
) -> List[str]:
    resolved_targets = resolve_export_targets(targets)
    targets_dir = destination / "targets"

    if not resolved_targets:
        if targets_dir.exists():
            shutil.rmtree(targets_dir)
        return []

    targets_dir.mkdir(parents=True, exist_ok=True)
    for path in list(targets_dir.iterdir()):
        if path.name not in resolved_targets:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    for target_name in resolved_targets:
        definition = EXPORT_TARGETS[target_name]
        target_dir = targets_dir / target_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        records = definition.builder(corpus_records, chunk_records)
        manifest = {
            "target": definition.name,
            "provider": definition.provider,
            "priority": definition.priority,
            "description": definition.description,
            "recommended_ingestion_unit": definition.recommended_ingestion_unit,
            "record_count": len(records),
            "source_file": definition.output_filename,
            "canonical_manifest": "../../manifest.json",
            "canonical_corpus": "../../corpus.jsonl",
            "canonical_chunks": "../../chunks.jsonl",
            "recommended_system_prompt": "../../prompts/system.md",
        }

        (target_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _write_jsonl(target_dir / definition.output_filename, records)

    return resolved_targets
