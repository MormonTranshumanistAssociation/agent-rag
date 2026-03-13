from __future__ import annotations

import json
from pathlib import Path

from agent_rag.cli import main


def make_subject_pack(base_dir: Path) -> Path:
    subject_dir = base_dir / "subjects" / "parley-p-pratt"
    clean_dir = subject_dir / "clean" / "primary"
    clean_dir.mkdir(parents=True)

    (subject_dir / "profile.yaml").write_text(
        """id: parley-p-pratt
display_name: Parley P. Pratt
canonical_name: Parley Parker Pratt
birth_year: 1807
death_year: 1857
summary: Early Latter Day Saint apostle, missionary, writer, and theologian.
""",
        encoding="utf-8",
    )
    (subject_dir / "aliases.yaml").write_text(
        """aliases:
  - Parley P. Pratt
  - Parley Parker Pratt
""",
        encoding="utf-8",
    )
    (subject_dir / "sources.yaml").write_text(
        """sources:
  - id: autobiography-1888
    title: The Autobiography of Parley Parker Pratt
    author: Parley P. Pratt
    publication_year: 1888
    source_type: primary
    genre: autobiography
    url: https://www.gutenberg.org/ebooks/44896
    rights: public_domain
""",
        encoding="utf-8",
    )
    (clean_dir / "autobiography-opening.md").write_text(
        """---
document_id: autobiography-opening
source_id: autobiography-1888
work_title: The Autobiography of Parley Parker Pratt
document_title: Opening excerpt
author: Parley P. Pratt
composed_year: 1888
source_type: primary
---
My father was a hard working man, and generally occupied in agricultural pursuits.

He taught us to venerate our Father in Heaven, Jesus Christ, His prophets and Apostles, as well as the Scriptures written by them.
""",
        encoding="utf-8",
    )
    return subject_dir


def test_cli_validate_and_build(tmp_path: Path, capsys) -> None:
    subject_dir = make_subject_pack(tmp_path)
    output_dir = tmp_path / "exports"

    validate_exit = main(["validate", str(subject_dir)])
    build_exit = main(["build", str(subject_dir), "--output-dir", str(output_dir), "--chunk-size", "80", "--chunk-overlap", "10"])

    captured = capsys.readouterr()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert validate_exit == 0
    assert build_exit == 0
    assert "Validation passed" in captured.out
    assert "Built subject pack" in captured.out
    assert manifest["subject_id"] == "parley-p-pratt"
    assert manifest["chunk_count"] >= 2
