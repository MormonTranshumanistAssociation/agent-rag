from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

from .chunking import chunk_text, normalize_text
from .models import BuildResult, DocumentRecord, SourceRecord, SubjectPack, SubjectProfile, VALID_SOURCE_TYPES


REQUIRED_PROFILE_FIELDS = {"id", "display_name", "canonical_name", "summary"}
REQUIRED_SOURCE_FIELDS = {"id", "title", "author", "source_type", "genre", "url", "rights"}
REQUIRED_DOCUMENT_FIELDS = {"document_id", "source_id", "work_title", "document_title", "author", "source_type"}


def _read_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text

    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        raise ValueError("Invalid YAML front matter")

    metadata = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    return metadata, body


def _coerce_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _validate_year(value: Any, field_name: str, context: str, errors: List[str]) -> None:
    if value in (None, ""):
        return
    try:
        int(value)
    except (TypeError, ValueError):
        errors.append(f"{context} has invalid {field_name}: {value}")


def _load_profile(subject_dir: Path) -> SubjectProfile:
    data = _read_yaml(subject_dir / "profile.yaml")
    return SubjectProfile(
        id=str(data.get("id", "")).strip(),
        display_name=str(data.get("display_name", "")).strip(),
        canonical_name=str(data.get("canonical_name", "")).strip(),
        birth_year=_coerce_year(data.get("birth_year")),
        death_year=_coerce_year(data.get("death_year")),
        summary=str(data.get("summary", "")).strip(),
    )


def _load_aliases(subject_dir: Path) -> List[str]:
    aliases_path = subject_dir / "aliases.yaml"
    if not aliases_path.exists():
        return []
    data = _read_yaml(aliases_path)
    aliases = data.get("aliases", [])
    return [str(alias).strip() for alias in aliases if str(alias).strip()]


def _load_sources(subject_dir: Path) -> Dict[str, SourceRecord]:
    data = _read_yaml(subject_dir / "sources.yaml")
    result: Dict[str, SourceRecord] = {}
    for item in data.get("sources", []):
        source = SourceRecord(
            id=str(item.get("id", "")).strip(),
            title=str(item.get("title", "")).strip(),
            author=str(item.get("author", "")).strip(),
            publication_year=_coerce_year(item.get("publication_year")),
            source_type=str(item.get("source_type", "")).strip(),
            genre=str(item.get("genre", "")).strip(),
            url=str(item.get("url", "")).strip(),
            rights=str(item.get("rights", "")).strip(),
            extra={k: v for k, v in item.items() if k not in REQUIRED_SOURCE_FIELDS | {"publication_year"}},
        )
        result[source.id] = source
    return result


def _iter_clean_document_paths(subject_dir: Path) -> Iterable[Path]:
    clean_dir = subject_dir / "clean"
    if not clean_dir.exists():
        return []
    return sorted(path for path in clean_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".txt"})


def _load_documents(subject_dir: Path) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    for path in _iter_clean_document_paths(subject_dir):
        raw_text = path.read_text(encoding="utf-8")
        metadata, body = _parse_front_matter(raw_text)
        documents.append(
            DocumentRecord(
                document_id=str(metadata.get("document_id", "")).strip(),
                source_id=str(metadata.get("source_id", "")).strip(),
                work_title=str(metadata.get("work_title", "")).strip(),
                document_title=str(metadata.get("document_title", "")).strip(),
                author=str(metadata.get("author", "")).strip(),
                composed_year=_coerce_year(metadata.get("composed_year")),
                source_type=str(metadata.get("source_type", "")).strip(),
                text=normalize_text(body),
                path=path,
                metadata={k: v for k, v in metadata.items() if k not in REQUIRED_DOCUMENT_FIELDS | {"composed_year"}},
            )
        )
    return documents


def load_subject_pack(subject_dir: Path | str) -> SubjectPack:
    subject_path = Path(subject_dir)
    return SubjectPack(
        profile=_load_profile(subject_path),
        aliases=_load_aliases(subject_path),
        sources=_load_sources(subject_path),
        documents=_load_documents(subject_path),
    )


def validate_subject_pack(subject_dir: Path | str) -> List[str]:
    subject_path = Path(subject_dir)
    errors: List[str] = []

    for required_file in ["profile.yaml", "sources.yaml"]:
        if not (subject_path / required_file).exists():
            errors.append(f"Missing required file: {required_file}")

    if errors:
        return errors

    try:
        profile_data = _read_yaml(subject_path / "profile.yaml")
    except Exception as exc:  # pragma: no cover - defensive
        return [f"Could not parse profile.yaml: {exc}"]

    if not isinstance(profile_data, dict):
        errors.append("profile.yaml must contain a mapping/object")
        profile_data = {}

    missing_profile_fields = sorted(field for field in REQUIRED_PROFILE_FIELDS if not profile_data.get(field))
    if missing_profile_fields:
        errors.append(f"profile.yaml is missing required fields: {', '.join(missing_profile_fields)}")
    _validate_year(profile_data.get("birth_year"), "birth_year", "profile.yaml", errors)
    _validate_year(profile_data.get("death_year"), "death_year", "profile.yaml", errors)

    aliases_path = subject_path / "aliases.yaml"
    if aliases_path.exists():
        try:
            aliases_data = _read_yaml(aliases_path)
        except Exception as exc:
            errors.append(f"Could not parse aliases.yaml: {exc}")
        else:
            if not isinstance(aliases_data, dict):
                errors.append("aliases.yaml must contain a mapping/object")
            else:
                aliases = aliases_data.get("aliases")
                if aliases is None or not isinstance(aliases, list) or any(not str(alias).strip() for alias in aliases):
                    errors.append("aliases.yaml must contain a non-empty 'aliases' list of strings")

    try:
        sources_data = _read_yaml(subject_path / "sources.yaml")
    except Exception as exc:  # pragma: no cover - defensive
        return [f"Could not parse sources.yaml: {exc}"]

    if not isinstance(sources_data, dict):
        return ["sources.yaml must contain a mapping/object"]

    source_items = sources_data.get("sources")
    if not isinstance(source_items, list) or not source_items:
        errors.append("sources.yaml must contain a non-empty 'sources' list")
        return errors

    seen_source_ids: set[str] = set()
    source_metadata: Dict[str, Dict[str, str]] = {}
    for index, item in enumerate(source_items, start=1):
        missing_fields = sorted(field for field in REQUIRED_SOURCE_FIELDS if item.get(field) in (None, ""))
        if missing_fields:
            errors.append(f"source #{index} is missing required fields: {', '.join(missing_fields)}")
        source_id = str(item.get("id", "")).strip()
        if source_id in seen_source_ids:
            errors.append(f"Duplicate source id: {source_id}")
        if source_id:
            seen_source_ids.add(source_id)
            source_metadata[source_id] = {
                "author": str(item.get("author", "")).strip(),
                "source_type": str(item.get("source_type", "")).strip(),
            }
        source_type = str(item.get("source_type", "")).strip()
        if source_type and source_type not in VALID_SOURCE_TYPES:
            errors.append(f"Source '{source_id or index}' has invalid source_type '{source_type}'")
        _validate_year(item.get("publication_year"), "publication_year", f"Source '{source_id or index}'", errors)

    document_paths = list(_iter_clean_document_paths(subject_path))
    if not document_paths:
        errors.append("No clean documents found under clean/")
        return errors

    seen_document_ids: set[str] = set()
    for path in document_paths:
        try:
            raw_text = path.read_text(encoding="utf-8")
            metadata, body = _parse_front_matter(raw_text)
        except Exception as exc:
            errors.append(f"Document {path.name} has invalid front matter: {exc}")
            continue

        if not isinstance(metadata, dict):
            errors.append(f"Document {path.name} front matter must contain a mapping/object")
            continue

        document_id = str(metadata.get("document_id", "")).strip()
        source_id = str(metadata.get("source_id", "")).strip()
        work_title = str(metadata.get("work_title", "")).strip()
        document_title = str(metadata.get("document_title", "")).strip()
        author = str(metadata.get("author", "")).strip()
        source_type = str(metadata.get("source_type", "")).strip()
        text = normalize_text(body)

        raw_document_fields = {
            "document_id": document_id,
            "source_id": source_id,
            "work_title": work_title,
            "document_title": document_title,
            "author": author,
            "source_type": source_type,
        }
        doc_missing_fields = sorted(field for field in REQUIRED_DOCUMENT_FIELDS if not raw_document_fields[field])
        if doc_missing_fields:
            errors.append(f"Document {path.name} is missing required fields: {', '.join(doc_missing_fields)}")

        if document_id:
            if document_id in seen_document_ids:
                errors.append(f"Duplicate document id: {document_id}")
            seen_document_ids.add(document_id)

        if source_type and source_type not in VALID_SOURCE_TYPES:
            errors.append(f"Document {path.name} has invalid source_type '{source_type}'")
        _validate_year(metadata.get("composed_year"), "composed_year", f"Document {path.name}", errors)

        if source_id and source_id not in source_metadata:
            errors.append(f"Document {path.name} references unknown source_id '{source_id}'")
        elif source_id:
            source_info = source_metadata[source_id]
            if source_type and source_info.get("source_type") and source_type != source_info["source_type"]:
                errors.append(
                    f"Document {path.name} has source_type mismatch for source_id '{source_id}': "
                    f"document={source_type}, source={source_info['source_type']}"
                )
            if author and source_info.get("author") and author != source_info["author"]:
                errors.append(
                    f"Document {path.name} has author mismatch for source_id '{source_id}': "
                    f"document={author}, source={source_info['author']}"
                )

        if not text:
            errors.append(f"Document {path.name} has no body text")

    return errors


def _write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build_subject_pack(
    subject_dir: Path | str,
    output_dir: Path | str | None = None,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> BuildResult:
    errors = validate_subject_pack(subject_dir)
    if errors:
        raise ValueError("Subject pack validation failed: " + "; ".join(errors))

    pack = load_subject_pack(subject_dir)
    destination = Path(output_dir) if output_dir is not None else Path(subject_dir) / "exports"
    destination.mkdir(parents=True, exist_ok=True)

    corpus_records: List[Dict[str, Any]] = []
    chunk_records: List[Dict[str, Any]] = []

    subject_path = Path(subject_dir)
    for document in pack.documents:
        source = pack.sources[document.source_id]
        corpus_record = {
            "subject_id": pack.profile.id,
            "subject_name": pack.profile.display_name,
            "document_id": document.document_id,
            "document_title": document.document_title,
            "work_title": document.work_title,
            "author": document.author,
            "source_id": document.source_id,
            "source_title": source.title,
            "source_type": source.source_type,
            "publication_year": source.publication_year,
            "source_url": source.url,
            "rights": source.rights,
            "path": str(document.path.relative_to(subject_path)),
            "text": document.text,
        }
        corpus_records.append(corpus_record)

        for index, chunk in enumerate(chunk_text(document.text, chunk_size=chunk_size, overlap=chunk_overlap)):
            chunk_records.append(
                {
                    "chunk_id": f"{document.document_id}:{index}",
                    "chunk_index": index,
                    "subject_id": pack.profile.id,
                    "subject_name": pack.profile.display_name,
                    "document_id": document.document_id,
                    "document_title": document.document_title,
                    "work_title": document.work_title,
                    "author": document.author,
                    "source_id": document.source_id,
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "publication_year": source.publication_year,
                    "source_url": source.url,
                    "rights": source.rights,
                    "text": chunk,
                }
            )

    manifest = {
        "subject_id": pack.profile.id,
        "subject_name": pack.profile.display_name,
        "alias_count": len(pack.aliases),
        "source_count": len(pack.sources),
        "document_count": len(corpus_records),
        "chunk_count": len(chunk_records),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }

    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_jsonl(destination / "corpus.jsonl", corpus_records)
    _write_jsonl(destination / "chunks.jsonl", chunk_records)

    return BuildResult(
        subject_id=pack.profile.id,
        output_dir=destination,
        document_count=len(corpus_records),
        chunk_count=len(chunk_records),
    )
