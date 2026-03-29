from __future__ import annotations

import json
from pathlib import Path

from agent_rag.elevenlabs import (
    DEFAULT_ELEVENLABS_VOICE_ID,
    build_knowledge_document_text,
    build_parley_agent_payload,
    build_parley_agent_prompt,
    document_content_hash,
    evaluate_elevenlabs_agent,
    plan_sync_operations,
    render_widget_html,
    sync_elevenlabs_target,
    write_json,
)


SAMPLE_RECORD = {
    "id": "voice-of-warning-preface",
    "title": "Preface excerpt",
    "text": "When the following work was first published in America, in 1837, it was but little known.",
    "metadata": {
        "subject_id": "parley-p-pratt",
        "subject_name": "Parley P. Pratt",
        "document_id": "voice-of-warning-preface",
        "document_title": "Preface excerpt",
        "work_title": "A Voice of Warning",
        "author": "Parley P. Pratt",
        "source_id": "voice-of-warning-1837",
        "source_title": "A Voice of Warning",
        "source_type": "primary",
        "publication_year": 1837,
        "source_url": "https://www.gutenberg.org/ebooks/35554",
        "rights": "public_domain",
    },
}


class FakeElevenLabsClient:
    last_instance: "FakeElevenLabsClient | None" = None
    remote_documents: list[dict] = []
    live_agent: dict = {}

    def __init__(self, api_key: str, **_: object) -> None:
        self.api_key = api_key
        self.created_documents: list[dict] = []
        self.deleted_documents: list[str] = []
        self.rag_index_calls: list[list[str]] = []
        self.created_agents: list[dict] = []
        self.patched_agents: list[tuple[str, dict]] = []
        self.simulated: list[dict] = []
        FakeElevenLabsClient.last_instance = self

    def list_knowledge_base_documents(self):
        return [dict(doc) for doc in self.remote_documents]

    def create_text_document(self, *, name: str, text: str) -> dict:
        doc_id = f"doc-{len(self.created_documents) + 1}"
        payload = {"id": doc_id, "name": name, "text": text}
        self.created_documents.append(payload)
        return payload

    def delete_knowledge_base_document(self, documentation_id: str) -> None:
        self.deleted_documents.append(documentation_id)

    def create_rag_indexes(self, document_ids, *, model="e5_mistral_7b_instruct"):
        self.rag_index_calls.append(list(document_ids))
        return {"items": list(document_ids), "model": model}

    def find_agent_by_name(self, name: str):
        return None

    def create_agent(self, payload: dict) -> dict:
        self.created_agents.append(payload)
        return {"agent_id": "agent-test-1"}

    def patch_agent(self, agent_id: str, payload: dict) -> dict:
        self.patched_agents.append((agent_id, payload))
        return {"agent_id": agent_id}

    def get_agent(self, agent_id: str) -> dict:
        if self.live_agent:
            return dict(self.live_agent)
        return {"agent_id": agent_id}

    def simulate_conversation(self, *, agent_id: str, simulated_user_prompt: str, criteria, new_turns_limit: int = 6) -> dict:
        payload = {
            "agent_id": agent_id,
            "prompt": simulated_user_prompt,
            "criteria": list(criteria),
            "new_turns_limit": new_turns_limit,
        }
        self.simulated.append(payload)
        return {
            "simulated_conversation": [
                {"role": "user", "message": "Question"},
                {"role": "agent", "message": "Answer"},
            ],
            "analysis": {
                "evaluation_criteria_results": {
                    criteria[0]["id"]: {"result": "success", "criteria_id": criteria[0]["id"]}
                }
            },
        }


def make_target_dir(tmp_path: Path) -> Path:
    output_dir = tmp_path / "exports"
    target_dir = output_dir / "targets" / "elevenlabs"
    target_dir.mkdir(parents=True)
    (output_dir / "prompts").mkdir(parents=True)
    (output_dir / "manifest.json").write_text(json.dumps({"subject_id": "parley-p-pratt"}), encoding="utf-8")
    (output_dir / "prompts" / "system.md").write_text("System prompt\n", encoding="utf-8")
    (target_dir / "documents.jsonl").write_text(json.dumps(SAMPLE_RECORD) + "\n", encoding="utf-8")
    return target_dir


def test_build_knowledge_document_text_uses_human_readable_provenance_without_ids() -> None:
    text = build_knowledge_document_text(SAMPLE_RECORD)

    assert "Provenance" in text
    assert "Work title: A Voice of Warning" in text
    assert "Source title: A Voice of Warning" in text
    assert "Source URL: https://www.gutenberg.org/ebooks/35554" in text
    assert "Document ID:" not in text
    assert "Source ID:" not in text
    assert SAMPLE_RECORD["text"] in text


def test_build_parley_agent_prompt_instructs_voice_agent_not_to_read_ids_aloud() -> None:
    prompt = build_parley_agent_prompt("Base prompt")

    assert "Do not read document ids, source ids, or hash-like codes aloud" in prompt
    assert "use work titles and source names instead" in prompt


def test_build_parley_agent_prompt_allows_grounded_first_person_voice() -> None:
    prompt = build_parley_agent_prompt("Base prompt").lower()

    assert "prefer speaking in the first person as parley" in prompt
    assert "when retrieved primary passages support that voice" in prompt
    assert "if the user addresses you directly as parley" in prompt
    assert "include at least one short quotation" in prompt
    assert "shift into third person only when the evidence is secondary" in prompt
    assert "use bracketed expressive cues sparingly" in prompt


def test_plan_sync_operations_detects_create_recreate_keep_and_delete() -> None:
    previous_state = {
        "documents": {
            "voice-of-warning-preface": {"remote_id": "doc-1", "content_hash": document_content_hash(SAMPLE_RECORD)},
            "stale-doc": {"remote_id": "doc-old", "content_hash": "old"},
        }
    }
    changed_record = dict(SAMPLE_RECORD)
    changed_record["text"] = SAMPLE_RECORD["text"] + " Changed."

    operations = plan_sync_operations([changed_record, {**SAMPLE_RECORD, "id": "new-doc"}], previous_state)

    assert operations["create"] == ["new-doc"]
    assert operations["recreate"] == ["voice-of-warning-preface"]
    assert operations["keep"] == []
    assert operations["delete"] == ["stale-doc"]


def test_build_parley_agent_payload_configures_rag_voice_and_widget() -> None:
    payload = build_parley_agent_payload(
        agent_name="Parley's Ghost",
        prompt_text="Prompt body",
        knowledge_base=[{"id": "doc-1", "name": "parley/doc-1", "type": "text", "usage_mode": "auto"}],
    )

    assert payload["conversation_config"]["tts"]["voice_id"] == DEFAULT_ELEVENLABS_VOICE_ID
    assert payload["conversation_config"]["agent"]["prompt"]["rag"]["enabled"] is True
    assert payload["conversation_config"]["agent"]["prompt"]["knowledge_base"][0]["id"] == "doc-1"
    assert "from my own writings where i can" in payload["conversation_config"]["agent"]["first_message"].lower()
    assert payload["platform_settings"]["widget"]["conversation_mode_toggle_enabled"] is True
    assert payload["platform_settings"]["auth"]["enable_auth"] is False


def test_sync_elevenlabs_target_writes_state_widget_and_agent(monkeypatch, tmp_path: Path) -> None:
    target_dir = make_target_dir(tmp_path)
    FakeElevenLabsClient.remote_documents = []
    monkeypatch.setattr("agent_rag.elevenlabs.ElevenLabsClient", FakeElevenLabsClient)

    result = sync_elevenlabs_target(target_dir, api_key="test-key")

    state = json.loads((target_dir / "sync-state.json").read_text(encoding="utf-8"))
    widget = (target_dir / "widget.html").read_text(encoding="utf-8")
    fake = FakeElevenLabsClient.last_instance

    assert result.agent_id == "agent-test-1"
    assert state["agent"]["agent_id"] == "agent-test-1"
    assert "voice-of-warning-preface" in state["documents"]
    assert "<elevenlabs-convai agent-id=\"agent-test-1\"" in widget
    assert fake is not None
    assert len(fake.created_documents) == 1
    assert len(fake.created_agents) == 1
    assert fake.rag_index_calls == [["doc-1"]]


def test_evaluate_elevenlabs_agent_uses_state_agent_and_writes_results(monkeypatch, tmp_path: Path) -> None:
    target_dir = make_target_dir(tmp_path)
    write_json(
        target_dir / "sync-state.json",
        {
            "documents": {},
            "agent": {"agent_id": "agent-test-1", "agent_name": "Parley's Ghost"},
        },
    )
    FakeElevenLabsClient.remote_documents = []
    monkeypatch.setattr("agent_rag.elevenlabs.ElevenLabsClient", FakeElevenLabsClient)

    results = evaluate_elevenlabs_agent(target_dir=target_dir, api_key="test-key")

    fake = FakeElevenLabsClient.last_instance
    saved = json.loads((target_dir / "eval-results.json").read_text(encoding="utf-8"))

    assert len(results) == 3
    assert results[0].scenario_id == "grounded-doctrine-recall"
    assert fake is not None
    assert len(fake.simulated) == 3
    assert saved[0]["scenario"]["id"] == "grounded-doctrine-recall"


def test_sync_elevenlabs_target_recreates_changed_doc_without_reusing_deleted_remote(monkeypatch, tmp_path: Path) -> None:
    target_dir = make_target_dir(tmp_path)
    changed_record = dict(SAMPLE_RECORD)
    changed_record["text"] = SAMPLE_RECORD["text"] + " Updated."
    (target_dir / "documents.jsonl").write_text(json.dumps(changed_record) + "\n", encoding="utf-8")
    write_json(
        target_dir / "sync-state.json",
        {
            "documents": {
                "voice-of-warning-preface": {
                    "remote_id": "remote-old",
                    "name": "parley-p-pratt/voice-of-warning-preface",
                    "type": "text",
                    "usage_mode": "auto",
                    "content_hash": document_content_hash(SAMPLE_RECORD),
                    "title": SAMPLE_RECORD["title"],
                }
            },
            "agent": {},
        },
    )
    FakeElevenLabsClient.remote_documents = [
        {"id": "remote-old", "name": "parley-p-pratt/voice-of-warning-preface", "type": "text"}
    ]
    monkeypatch.setattr("agent_rag.elevenlabs.ElevenLabsClient", FakeElevenLabsClient)

    result = sync_elevenlabs_target(target_dir, api_key="***")

    fake = FakeElevenLabsClient.last_instance
    state = json.loads((target_dir / "sync-state.json").read_text(encoding="utf-8"))
    assert result.recreated_documents == 1
    assert fake is not None
    assert fake.deleted_documents == ["remote-old"]
    assert len(fake.created_documents) == 1
    assert state["documents"]["voice-of-warning-preface"]["remote_id"] == "doc-1"


def test_sync_elevenlabs_target_preserves_live_voice_when_not_explicitly_overridden(monkeypatch, tmp_path: Path) -> None:
    target_dir = make_target_dir(tmp_path)
    write_json(
        target_dir / "sync-state.json",
        {
            "documents": {},
            "agent": {
                "agent_id": "agent-live-1",
                "agent_name": "Parley's Ghost",
                "voice_id": "old-state-voice",
                "voice_name": "Old state voice",
            },
        },
    )
    FakeElevenLabsClient.remote_documents = []
    FakeElevenLabsClient.live_agent = {
        "agent_id": "agent-live-1",
        "conversation_config": {
            "tts": {
                "voice_id": "live-voice-123",
            }
        },
    }
    monkeypatch.setattr("agent_rag.elevenlabs.ElevenLabsClient", FakeElevenLabsClient)

    result = sync_elevenlabs_target(target_dir, api_key="***", voice_id=None, voice_name=None)

    fake = FakeElevenLabsClient.last_instance
    state = json.loads((target_dir / "sync-state.json").read_text(encoding="utf-8"))
    assert fake is not None
    assert fake.patched_agents[0][1]["conversation_config"]["tts"]["voice_id"] == "live-voice-123"
    assert state["agent"]["voice_id"] == "live-voice-123"
    assert result.voice_id == "live-voice-123"


def test_render_widget_html_includes_agent_id() -> None:
    html_text = render_widget_html(agent_id="agent-123")

    assert "agent-123" in html_text
    assert "@elevenlabs/convai-widget-embed" in html_text
