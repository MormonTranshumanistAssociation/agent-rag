from __future__ import annotations

import json
from pathlib import Path
from urllib import request

from agent_rag.cli import main
from agent_rag.ocr_proofreader import (
    GeminiProofreader,
    OpenAICompatibleProofreader,
    _chunk_paragraphs,
    proofread_ocr_review_packet,
    resolve_proofreader_client,
)


class FakeProofreader:
    model = "fake-model"
    base_url = "https://example.invalid/v1"

    def __init__(self) -> None:
        self.calls = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        prompt = messages[-1]["content"]
        marker = "## MAIN TEXT TO CORRECT\n\n"
        start = prompt.index(marker) + len(marker)
        end = prompt.index("\n\n## Context after\n\n", start)
        main_text = prompt[start:end]
        return main_text.replace("teh", "the").replace(" artefact", " artifact")


def test_chunk_paragraphs_groups_paragraphs_under_limit() -> None:
    paragraphs = ["a" * 20, "b" * 20, "c" * 20]

    assert _chunk_paragraphs(paragraphs, max_chars=45) == [(0, 2), (2, 3)]


def test_proofread_ocr_review_packet_writes_proofread_outputs(tmp_path: Path) -> None:
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    candidate = review_dir / "candidate.md"
    candidate.write_text(
        "---\n"
        "document_id: sample\n"
        "source_id: source-1\n"
        "work_title: Sample Work\n"
        "document_title: Sample Doc\n"
        "author: Tester\n"
        "source_type: primary\n"
        "---\n"
        "\n"
        "First teh paragraph.\n\nSecond artefact paragraph.\n\nThird paragraph.\n",
        encoding="utf-8",
    )
    (review_dir / "proofread_prompt.md").write_text("Proofread conservatively.", encoding="utf-8")
    (review_dir / "lint_report.json").write_text(
        json.dumps({"issue_count": 2, "issues": [{"token": "teh", "context": "First teh paragraph."}, {"token": "artefact", "context": "Second artefact paragraph."}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    fake = FakeProofreader()
    output_path = proofread_ocr_review_packet(review_dir, client=fake, chunk_chars=40, context_paragraphs=1)

    assert output_path == review_dir / "proofread.md"
    proofread_text = output_path.read_text(encoding="utf-8")
    assert "First the paragraph." in proofread_text
    assert "Second artifact paragraph." in proofread_text
    assert "Third paragraph." in proofread_text

    manifest = json.loads((review_dir / "proofread_manifest.json").read_text(encoding="utf-8"))
    assert manifest["model"] == "fake-model"
    assert manifest["chunk_count"] == 3
    assert fake.calls
    assert any("teh" in message[-1]["content"] for message in fake.calls)


def test_resolve_proofreader_client_supports_gemini(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    client = resolve_proofreader_client(provider="gemini", model="gemini-2.5-pro")

    assert isinstance(client, GeminiProofreader)
    assert client.model == "gemini-2.5-pro"


def test_resolve_proofreader_client_supports_openai(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    client = resolve_proofreader_client(provider="openai", model="gpt-test")

    assert isinstance(client, OpenAICompatibleProofreader)
    assert client.model == "gpt-test"


def test_gemini_proofreader_complete_parses_response(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps({
                "candidates": [
                    {"content": {"parts": [{"text": "Corrected text"}]}}
                ]
            }).encode("utf-8")

    def fake_urlopen(req: request.Request, timeout: int = 0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    client = GeminiProofreader(model="gemini-2.5-pro", api_key="test-key")
    output = client.complete([
        {"role": "system", "content": "System guidance"},
        {"role": "user", "content": "Please correct this text."},
    ])

    assert output == "Corrected text"
    assert captured["url"].startswith("https://generativelanguage.googleapis.com/")
    assert captured["body"]["systemInstruction"]["parts"][0]["text"] == "System guidance"
    assert captured["body"]["contents"][0]["parts"][0]["text"] == "Please correct this text."


def test_cli_proofread_ocr_invokes_proofreader(monkeypatch, tmp_path: Path) -> None:
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    output_path = review_dir / "proofread.md"
    output_path.write_text("ok\n", encoding="utf-8")

    called = {}

    def fake_proofread(review_dir_arg: Path, **kwargs: object) -> Path:
        called["review_dir"] = review_dir_arg
        called.update(kwargs)
        return output_path

    monkeypatch.setattr("agent_rag.cli.proofread_ocr_review_packet", fake_proofread)

    exit_code = main([
        "proofread-ocr",
        str(review_dir),
        "--provider",
        "gemini",
        "--model",
        "gemini-2.5-pro",
        "--chunk-chars",
        "1234",
        "--context-paragraphs",
        "2",
    ])

    assert exit_code == 0
    assert called["review_dir"] == review_dir
    assert called["provider"] == "gemini"
    assert called["model"] == "gemini-2.5-pro"
    assert called["chunk_chars"] == 1234
    assert called["context_paragraphs"] == 2
