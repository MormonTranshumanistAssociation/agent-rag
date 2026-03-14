from __future__ import annotations

from pathlib import Path

from agent_rag.cli import main
from agent_rag.ocr_filter import normalize_ocr_text, prepare_ocr_review_packet


def test_normalize_ocr_text_fixes_ligatures_and_unwraps_prose() -> None:
    raw_text = "In the begin-\nning God created the hea-\nvens.\nThis para-\ngraph uses a ﬂ ligature.\n\nSecond para-\ngraph here.\n"

    normalized = normalize_ocr_text(raw_text)

    assert normalized == (
        "In the beginning God created the heavens. This paragraph uses a fl ligature.\n\n"
        "Second paragraph here.\n"
    )


def test_normalize_ocr_text_can_preserve_linebreaks() -> None:
    raw_text = "Roses are red,\nViolets are blue,\nﬁ ligatures appear here too.\n"

    normalized = normalize_ocr_text(raw_text, preserve_linebreaks=True)

    assert normalized == "Roses are red,\nViolets are blue,\nfi ligatures appear here too.\n"


def test_normalize_ocr_text_fixes_common_ocr_debris_patterns() -> None:
    raw_text = "Mr.S. said «' in«-\nterpretation ^ should be cleaned.\nMr, S. agreed.\n( 4 )\n"

    normalized = normalize_ocr_text(raw_text)

    assert normalized == 'Mr. S. said " interpretation should be cleaned. Mr. S. agreed.\n'


def test_prepare_ocr_review_packet_writes_normalized_text_candidate_and_prompt(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.txt"
    input_path.write_text("Mis-\ntaken ﬂowers bloom.\n", encoding="utf-8")

    output_dir = tmp_path / "review"
    prepare_ocr_review_packet(
        input_path=input_path,
        output_dir=output_dir,
        document_id="late-persecutions-chapter-01",
        source_id="late-persecutions-1840",
        work_title="Late Persecutions of the Church of Jesus Christ of Latter-day Saints",
        document_title="Chapter I",
        author="Parley P. Pratt",
        source_type="primary",
    )

    normalized_text = (output_dir / "normalized.txt").read_text(encoding="utf-8")
    candidate_text = (output_dir / "candidate.md").read_text(encoding="utf-8")
    prompt_text = (output_dir / "proofread_prompt.md").read_text(encoding="utf-8")

    assert normalized_text == "Mistaken flowers bloom.\n"
    assert "document_id: late-persecutions-chapter-01" in candidate_text
    assert "source_id: late-persecutions-1840" in candidate_text
    assert candidate_text.rstrip().endswith("Mistaken flowers bloom.")
    assert "Do not modernize the prose" in prompt_text
    assert "Confidently normalize obvious OCR debris" in prompt_text
    assert "late-persecutions-chapter-01" in prompt_text


def test_cli_prepare_ocr_writes_review_packet(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.txt"
    input_path.write_text("Po-\nems remain.\n", encoding="utf-8")
    output_dir = tmp_path / "packet"

    exit_code = main(
        [
            "prepare-ocr",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--document-id",
            "millennium-poem-01",
            "--source-id",
            "millennium-and-other-poems-1840",
            "--work-title",
            "The Millennium and Other Poems",
            "--document-title",
            "Poem 1",
            "--author",
            "Parley P. Pratt",
            "--preserve-linebreaks",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "normalized.txt").read_text(encoding="utf-8") == "Poems remain.\n"
    assert (output_dir / "candidate.md").exists()
    assert (output_dir / "proofread_prompt.md").exists()
