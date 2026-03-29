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
    assert manifest["system_prompt"] == "prompts/system.md"
    assert (output_dir / "prompts" / "system.md").exists()
    assert (output_dir / "targets" / "elevenlabs" / "manifest.json").exists()
    assert (output_dir / "targets" / "bedrock" / "manifest.json").exists()


def test_cli_build_accepts_explicit_targets(tmp_path: Path, capsys) -> None:
    subject_dir = make_subject_pack(tmp_path)
    output_dir = tmp_path / "exports"

    build_exit = main(
        [
            "build",
            str(subject_dir),
            "--output-dir",
            str(output_dir),
            "--chunk-size",
            "80",
            "--chunk-overlap",
            "10",
            "--target",
            "elevenlabs",
        ]
    )

    captured = capsys.readouterr()

    assert build_exit == 0
    assert "Built subject pack" in captured.out
    assert (output_dir / "targets" / "elevenlabs" / "manifest.json").exists()
    assert not (output_dir / "targets" / "bedrock" / "manifest.json").exists()


def test_cli_elevenlabs_sync_routes_to_helper(tmp_path: Path, capsys, monkeypatch) -> None:
    subject_dir = make_subject_pack(tmp_path)
    output_dir = tmp_path / "exports"

    def fake_sync(subject_dir_arg, **kwargs):
        assert subject_dir_arg == subject_dir
        assert kwargs["output_dir"] == output_dir
        assert kwargs["rebuild"] is True
        assert kwargs["agent_name"] == "Parley's Ghost"
        class Result:
            document_count = 1
            created_documents = 1
            recreated_documents = 0
            reused_documents = 0
            deleted_documents = 0
            agent_name = "Parley's Ghost"
            agent_id = "agent-123"
            voice_id = "voice-123"
            widget_path = output_dir / "targets" / "elevenlabs" / "widget.html"
        return Result()

    monkeypatch.setattr("agent_rag.cli.sync_elevenlabs_subject", fake_sync)

    exit_code = main([
        "elevenlabs-sync",
        str(subject_dir),
        "--output-dir",
        str(output_dir),
        "--rebuild",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Synced ElevenLabs target" in captured.out
    assert "agent-123" in captured.out


def test_cli_elevenlabs_eval_routes_to_helper(tmp_path: Path, capsys, monkeypatch) -> None:
    subject_dir = make_subject_pack(tmp_path)
    output_dir = tmp_path / "exports"

    class EvalResult:
        def __init__(self, scenario_id: str) -> None:
            self.scenario_id = scenario_id
            self.criteria_results = {"grounding": {"result": "success"}}

    def fake_eval(*, target_dir, agent_id, api_key):
        assert target_dir == output_dir / "targets" / "elevenlabs"
        assert agent_id == "agent-123"
        assert api_key is None
        return [EvalResult("scenario-1")]

    monkeypatch.setattr("agent_rag.cli.evaluate_elevenlabs_agent", fake_eval)

    exit_code = main([
        "elevenlabs-eval",
        str(subject_dir),
        "--output-dir",
        str(output_dir),
        "--agent-id",
        "agent-123",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ran 1 ElevenLabs eval scenario" in captured.out
    assert "scenario-1" in captured.out
