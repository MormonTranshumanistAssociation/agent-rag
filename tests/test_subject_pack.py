from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_rag.subject_pack import build_subject_pack, validate_subject_pack


VALID_PROFILE = """id: parley-p-pratt
display_name: Parley P. Pratt
canonical_name: Parley Parker Pratt
birth_year: 1807
death_year: 1857
summary: Early Latter Day Saint apostle, missionary, writer, and theologian.
"""

VALID_ALIASES = """aliases:
  - Parley P. Pratt
  - Parley Parker Pratt
  - Elder Parley P. Pratt
"""

VALID_SOURCES = """sources:
  - id: voice-of-warning-1837
    title: A Voice of Warning
    author: Parley P. Pratt
    publication_year: 1837
    source_type: primary
    genre: theological_treatise
    url: https://www.gutenberg.org/ebooks/35554
    rights: public_domain
  - id: autobiography-1888
    title: The Autobiography of Parley Parker Pratt
    author: Parley P. Pratt
    publication_year: 1888
    source_type: primary
    genre: autobiography
    url: https://www.gutenberg.org/ebooks/44896
    rights: public_domain
"""

VALID_DOCUMENT = """---
document_id: voice-of-warning-preface
source_id: voice-of-warning-1837
work_title: A Voice of Warning
document_title: Preface excerpt
author: Parley P. Pratt
composed_year: 1837
source_type: primary
---
When the following work was first published in America, in 1837, it was but little known and seemed to meet with little or no encouragement.

But, to the astonishment of the author, it worked itself into notice more and more, by the blessing of God, and by virtue of its own real merits.

The author has now in his possession the testimony of hundreds of people, from different states and nations, all bearing witness that this work has been a means, in the hands of God, of saving them from infidelity and sectarian error.
"""


@pytest.fixture()
def subject_dir(tmp_path: Path) -> Path:
    subject_dir = tmp_path / "subjects" / "parley-p-pratt"
    clean_dir = subject_dir / "clean" / "primary"
    clean_dir.mkdir(parents=True)

    (subject_dir / "profile.yaml").write_text(VALID_PROFILE, encoding="utf-8")
    (subject_dir / "aliases.yaml").write_text(VALID_ALIASES, encoding="utf-8")
    (subject_dir / "sources.yaml").write_text(VALID_SOURCES, encoding="utf-8")
    (clean_dir / "voice-of-warning-preface.md").write_text(VALID_DOCUMENT, encoding="utf-8")
    return subject_dir


def test_validate_subject_pack_accepts_valid_fixture(subject_dir: Path) -> None:
    errors = validate_subject_pack(subject_dir)

    assert errors == []


def test_validate_subject_pack_reports_duplicate_source_ids(subject_dir: Path) -> None:
    (subject_dir / "sources.yaml").write_text(
        """sources:
  - id: duplicate
    title: First
    author: Parley P. Pratt
    publication_year: 1837
    source_type: primary
    genre: tract
    url: https://example.com/first
    rights: public_domain
  - id: duplicate
    title: Second
    author: Parley P. Pratt
    publication_year: 1838
    source_type: primary
    genre: tract
    url: https://example.com/second
    rights: public_domain
""",
        encoding="utf-8",
    )

    errors = validate_subject_pack(subject_dir)

    assert any("duplicate source id" in error.lower() for error in errors)


def test_validate_subject_pack_allows_missing_publication_year(subject_dir: Path) -> None:
    (subject_dir / "sources.yaml").write_text(
        """sources:
  - id: voice-of-warning-1837
    title: A Voice of Warning
    author: Parley P. Pratt
    source_type: primary
    genre: theological_treatise
    url: https://www.gutenberg.org/ebooks/35554
    rights: public_domain
""",
        encoding="utf-8",
    )

    errors = validate_subject_pack(subject_dir)

    assert errors == []


def test_validate_subject_pack_reports_invalid_year_duplicate_document_id_and_metadata_mismatch(subject_dir: Path) -> None:
    (subject_dir / "sources.yaml").write_text(
        """sources:
  - id: voice-of-warning-1837
    title: A Voice of Warning
    author: Parley P. Pratt
    publication_year: not-a-year
    source_type: primary
    genre: theological_treatise
    url: https://www.gutenberg.org/ebooks/35554
    rights: public_domain
""",
        encoding="utf-8",
    )
    (subject_dir / "clean" / "primary" / "voice-of-warning-preface-copy.md").write_text(
        """---
document_id: voice-of-warning-preface
source_id: voice-of-warning-1837
work_title: A Voice of Warning
document_title: Duplicate excerpt
author: Someone Else
composed_year: not-a-year
source_type: secondary
---
A short duplicate document.
""",
        encoding="utf-8",
    )

    errors = validate_subject_pack(subject_dir)

    assert any("invalid publication_year" in error.lower() for error in errors)
    assert any("invalid composed_year" in error.lower() for error in errors)
    assert any("duplicate document id" in error.lower() for error in errors)
    assert any("source_type mismatch" in error.lower() for error in errors)
    assert any("author mismatch" in error.lower() for error in errors)


def test_validate_subject_pack_reports_malformed_aliases_and_front_matter(subject_dir: Path) -> None:
    (subject_dir / "aliases.yaml").write_text("aliases: [unterminated\n", encoding="utf-8")
    (subject_dir / "clean" / "primary" / "voice-of-warning-preface.md").write_text(
        "---\ndocument_id: broken\nsource_id: voice-of-warning-1837\n", encoding="utf-8"
    )

    errors = validate_subject_pack(subject_dir)

    assert any("aliases.yaml" in error for error in errors)
    assert any("front matter" in error.lower() or "document" in error.lower() for error in errors)


def test_validate_subject_pack_reports_non_mapping_yaml_shapes(subject_dir: Path) -> None:
    (subject_dir / "profile.yaml").write_text("- not-a-mapping\n", encoding="utf-8")
    (subject_dir / "clean" / "primary" / "voice-of-warning-preface.md").write_text(
        "---\n- not-a-mapping\n---\nBody text.\n", encoding="utf-8"
    )

    errors = validate_subject_pack(subject_dir)

    assert any("profile.yaml" in error and "mapping" in error.lower() for error in errors)
    assert any("front matter" in error.lower() and "mapping" in error.lower() for error in errors)


def test_build_subject_pack_exports_corpus_and_chunks(subject_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "build"

    result = build_subject_pack(subject_dir, output_dir=output_dir, chunk_size=120, chunk_overlap=20)

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    corpus_lines = [json.loads(line) for line in (output_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if line]
    chunk_lines = [json.loads(line) for line in (output_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]

    assert result.document_count == 1
    assert result.chunk_count == len(chunk_lines)
    assert manifest["subject_id"] == "parley-p-pratt"
    assert manifest["document_count"] == 1
    assert corpus_lines[0]["source_id"] == "voice-of-warning-1837"
    assert corpus_lines[0]["subject_id"] == "parley-p-pratt"
    assert len(chunk_lines) >= 2
    assert all(chunk["subject_id"] == "parley-p-pratt" for chunk in chunk_lines)
    assert all(chunk["source_id"] == "voice-of-warning-1837" for chunk in chunk_lines)
    assert chunk_lines[0]["chunk_id"] == "voice-of-warning-preface:0"


def test_build_subject_pack_exports_default_elevenlabs_and_bedrock_targets(subject_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "build"

    build_subject_pack(subject_dir, output_dir=output_dir, chunk_size=120, chunk_overlap=20)

    elevenlabs_dir = output_dir / "targets" / "elevenlabs"
    bedrock_dir = output_dir / "targets" / "bedrock"
    elevenlabs_manifest = json.loads((elevenlabs_dir / "manifest.json").read_text(encoding="utf-8"))
    elevenlabs_lines = [
        json.loads(line)
        for line in (elevenlabs_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    bedrock_manifest = json.loads((bedrock_dir / "manifest.json").read_text(encoding="utf-8"))
    bedrock_lines = [
        json.loads(line)
        for line in (bedrock_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]

    assert elevenlabs_manifest["target"] == "elevenlabs"
    assert elevenlabs_manifest["recommended_ingestion_unit"] == "document"
    assert elevenlabs_manifest["recommended_system_prompt"] == "../../prompts/system.md"
    assert elevenlabs_manifest["record_count"] == 1
    assert elevenlabs_lines[0]["id"] == "voice-of-warning-preface"
    assert elevenlabs_lines[0]["metadata"]["source_id"] == "voice-of-warning-1837"
    assert elevenlabs_lines[0]["metadata"]["source_url"] == "https://www.gutenberg.org/ebooks/35554"

    assert bedrock_manifest["target"] == "bedrock"
    assert bedrock_manifest["recommended_ingestion_unit"] == "chunk"
    assert bedrock_manifest["record_count"] == len(bedrock_lines)
    assert bedrock_lines[0]["id"] == "voice-of-warning-preface:0"
    assert bedrock_lines[0]["metadata"]["document_id"] == "voice-of-warning-preface"
    assert bedrock_lines[0]["metadata"]["source_id"] == "voice-of-warning-1837"


def test_build_subject_pack_removes_stale_target_outputs_on_rebuild(subject_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "build"

    build_subject_pack(subject_dir, output_dir=output_dir, chunk_size=120, chunk_overlap=20)
    build_subject_pack(subject_dir, output_dir=output_dir, chunk_size=120, chunk_overlap=20, targets=["elevenlabs"])

    assert (output_dir / "targets" / "elevenlabs" / "manifest.json").exists()
    assert not (output_dir / "targets" / "bedrock").exists()


def test_build_subject_pack_rejects_unknown_targets_before_writing_outputs(subject_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "build"

    with pytest.raises(ValueError, match="Unknown export target"):
        build_subject_pack(subject_dir, output_dir=output_dir, targets=["bogus"])

    assert not output_dir.exists()


def test_build_subject_pack_generates_default_system_prompt(subject_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "build"

    build_subject_pack(subject_dir, output_dir=output_dir, chunk_size=120, chunk_overlap=20)

    system_prompt = (output_dir / "prompts" / "system.md").read_text(encoding="utf-8")

    assert "Parley P. Pratt" in system_prompt
    assert "Prefer primary sources" in system_prompt
    assert "Surface uncertainty" in system_prompt
    assert "Do not invent quotations" in system_prompt


def test_build_subject_pack_copies_authored_system_prompt(subject_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "build"
    prompts_dir = subject_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text("Custom system prompt\n", encoding="utf-8")

    build_subject_pack(subject_dir, output_dir=output_dir, chunk_size=120, chunk_overlap=20)

    assert (output_dir / "prompts" / "system.md").read_text(encoding="utf-8") == "Custom system prompt\n"


def test_build_subject_pack_rejects_output_dir_that_overlaps_source_prompts(subject_dir: Path) -> None:
    prompts_dir = subject_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    system_prompt_path = prompts_dir / "system.md"
    system_prompt_path.write_text("Custom system prompt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="overlaps the subject prompt directory"):
        build_subject_pack(subject_dir, output_dir=subject_dir)

    assert system_prompt_path.read_text(encoding="utf-8") == "Custom system prompt\n"


def test_build_subject_pack_rejects_output_dir_overlap_even_without_source_prompts(subject_dir: Path) -> None:
    with pytest.raises(ValueError, match="overlaps the subject prompt directory"):
        build_subject_pack(subject_dir, output_dir=subject_dir)

    assert not (subject_dir / "prompts").exists()


def test_build_subject_pack_rejects_output_dir_nested_under_source_prompts(subject_dir: Path) -> None:
    prompts_dir = subject_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    nested_output_dir = prompts_dir / "build"

    with pytest.raises(ValueError, match="overlaps the subject prompt directory"):
        build_subject_pack(subject_dir, output_dir=nested_output_dir)

    assert not nested_output_dir.exists()
