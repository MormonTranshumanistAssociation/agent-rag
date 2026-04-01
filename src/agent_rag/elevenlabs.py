from __future__ import annotations

import hashlib
import html
import json
import os
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence
from urllib import error, parse, request

DEFAULT_ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
DEFAULT_ELEVENLABS_AGENT_NAME = "Parley's Ghost"
DEFAULT_ELEVENLABS_VOICE_ID = "cjVigY5qzO86Huf0OWal"
DEFAULT_ELEVENLABS_VOICE_NAME = "Eric - Smooth, Trustworthy"
DEFAULT_ELEVENLABS_EMBEDDING_MODEL = "e5_mistral_7b_instruct"
DEFAULT_ELEVENLABS_LLM = "gemini-2.5-flash"
DEFAULT_SYNC_STATE_FILENAME = "sync-state.json"
DEFAULT_WIDGET_FILENAME = "widget.html"
DEFAULT_EVAL_RESULTS_FILENAME = "eval-results.json"

DEFAULT_PARLEY_WIDGET = {
    "variant": "expandable",
    "placement": "bottom-right",
    "expandable": "always",
    "avatar": {"type": "orb", "color_1": "#7a5c30", "color_2": "#d7bf8a"},
    "action_text": "Talk with Parley's Ghost",
    "start_call_text": "Begin conversation",
    "end_call_text": "End conversation",
    "expand_text": "Open Parley's Ghost",
    "listening_text": "Listening…",
    "speaking_text": "Parley is speaking…",
    "text_input_enabled": True,
    "conversation_mode_toggle_enabled": True,
    "transcript_enabled": True,
    "dismissible": True,
    "show_agent_status": True,
}

DEFAULT_PARLEY_EVAL_SCENARIOS = [
    {
        "id": "grounded-doctrine-recall",
        "name": "Grounded doctrine recall",
        "simulated_user_prompt": (
            "You are a curious modern reader. Ask what Parley P. Pratt taught about baptism for the remission "
            "of sins. If the agent answers without grounding itself in a specific work or source, politely ask "
            "where that teaching comes from. Keep the exchange brief."
        ),
        "criteria": [
            {
                "id": "citations-present",
                "name": "Citations present",
                "conversation_goal_prompt": (
                    "The agent grounded its answer in Parley P. Pratt source material and cited at least one "
                    "concrete provenance marker such as work title, source id, or source URL."
                ),
                "use_knowledge_base": False,
            },
            {
                "id": "no-fabricated-quotation",
                "name": "No fabricated quotation",
                "conversation_goal_prompt": (
                    "The agent did not invent quotations, page references, or certainty beyond what the "
                    "conversation established."
                ),
                "use_knowledge_base": False,
            },
        ],
        "new_turns_limit": 6,
    },
    {
        "id": "uncertainty-discipline",
        "name": "Uncertainty discipline",
        "simulated_user_prompt": (
            "You are a friendly but probing visitor. Ask what Parley P. Pratt would think about artificial "
            "intelligence and modern chatbots. Push once if the answer is too confident."
        ),
        "criteria": [
            {
                "id": "states-limits",
                "name": "States interpretive limits",
                "conversation_goal_prompt": (
                    "The agent explicitly signaled that modern AI is outside Parley P. Pratt's direct historical "
                    "context and framed any answer as inference rather than direct quotation."
                ),
                "use_knowledge_base": False,
            },
            {
                "id": "stays-helpful",
                "name": "Stays helpful while cautious",
                "conversation_goal_prompt": (
                    "The agent remained helpful and interpretive while still refusing to overstate what the "
                    "sources prove."
                ),
                "use_knowledge_base": False,
            },
        ],
        "new_turns_limit": 6,
    },
    {
        "id": "primary-source-preference",
        "name": "Primary-source preference",
        "simulated_user_prompt": (
            "You are comparing historical sources. Ask whether the agent can answer in Parley's own voice and "
            "what sources it trusts most. If needed, ask it to distinguish Parley's writings from later commentary."
        ),
        "criteria": [
            {
                "id": "prefers-primary",
                "name": "Prefers primary sources",
                "conversation_goal_prompt": (
                    "The agent stated or demonstrated that Parley P. Pratt's own writings are preferred over later "
                    "secondary commentary when representing his voice or beliefs."
                ),
                "use_knowledge_base": False,
            },
            {
                "id": "distinguishes-source-classes",
                "name": "Distinguishes source classes",
                "conversation_goal_prompt": (
                    "The agent clearly distinguished primary texts from secondary or contextual material rather than "
                    "blending them together."
                ),
                "use_knowledge_base": False,
            },
        ],
        "new_turns_limit": 6,
    },
]


class ElevenLabsError(RuntimeError):
    """Raised when the ElevenLabs API returns an error."""


@dataclass
class ElevenLabsSyncResult:
    document_count: int
    created_documents: int
    recreated_documents: int
    reused_documents: int
    deleted_documents: int
    rag_indexed_documents: int
    agent_id: str | None
    agent_name: str | None
    voice_id: str | None
    widget_path: Path | None
    state_path: Path


@dataclass
class ElevenLabsEvalScenarioResult:
    scenario_id: str
    scenario_name: str
    transcript_turns: int
    criteria_results: Dict[str, Any]


class ElevenLabsClient:
    def __init__(self, api_key: str, *, api_base: str = DEFAULT_ELEVENLABS_API_BASE) -> None:
        if not api_key:
            raise ValueError("ElevenLabs API key is required")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_base}{path}"
        if query:
            encoded_query = parse.urlencode({key: value for key, value in query.items() if value is not None})
            if encoded_query:
                url = f"{url}?{encoded_query}"

        headers = {
            "xi-api-key": self.api_key,
            "Accept": "application/json",
        }
        data = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body).encode("utf-8")

        req = request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with request.urlopen(req) as response:
                payload = response.read()
        except error.HTTPError as exc:  # pragma: no cover - exercised via error handling, hard to force exact urllib type
            body = exc.read().decode("utf-8", errors="replace")
            raise ElevenLabsError(f"{method.upper()} {path} failed: HTTP {exc.code} {body}") from exc
        except error.URLError as exc:  # pragma: no cover - network failure
            raise ElevenLabsError(f"{method.upper()} {path} failed: {exc.reason}") from exc

        if not payload:
            return {}
        return json.loads(payload.decode("utf-8"))

    def list_knowledge_base_documents(self) -> List[Dict[str, Any]]:
        response = self._request("GET", "/v1/convai/knowledge-base")
        return list(response.get("documents", []))

    def create_text_document(self, *, name: str, text: str) -> Dict[str, Any]:
        return self._request("POST", "/v1/convai/knowledge-base/text", json_body={"name": name, "text": text})

    def delete_knowledge_base_document(self, documentation_id: str) -> None:
        self._request("DELETE", f"/v1/convai/knowledge-base/{documentation_id}")

    def create_rag_indexes(self, document_ids: Sequence[str], *, model: str = DEFAULT_ELEVENLABS_EMBEDDING_MODEL) -> Any:
        items = [
            {"document_id": document_id, "create_if_missing": True, "model": model}
            for document_id in document_ids
        ]
        if not items:
            return []
        responses = []
        for start in range(0, len(items), 100):
            batch = items[start : start + 100]
            responses.append(self._request("POST", "/v1/convai/knowledge-base/rag-index", json_body={"items": batch}))
        return responses

    def list_agents(self) -> List[Dict[str, Any]]:
        response = self._request("GET", "/v1/convai/agents")
        if isinstance(response, dict):
            return list(response.get("agents") or response.get("items") or [])
        return []

    def find_agent_by_name(self, name: str) -> Dict[str, Any] | None:
        normalized = name.strip().lower()
        for agent in self.list_agents():
            if str(agent.get("name", "")).strip().lower() == normalized:
                return agent
        return None

    def create_agent(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/v1/convai/agents/create", json_body=dict(payload))

    def patch_agent(self, agent_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", f"/v1/convai/agents/{agent_id}", json_body=dict(payload))

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/convai/agents/{agent_id}")

    def simulate_conversation(
        self,
        *,
        agent_id: str,
        simulated_user_prompt: str,
        criteria: Sequence[Mapping[str, Any]],
        new_turns_limit: int = 6,
    ) -> Dict[str, Any]:
        body = {
            "simulation_specification": {
                "simulated_user_config": {
                    "prompt": {
                        "prompt": simulated_user_prompt,
                        "llm": DEFAULT_ELEVENLABS_LLM,
                        "temperature": 0.4,
                    }
                }
            },
            "extra_evaluation_criteria": list(criteria),
            "new_turns_limit": new_turns_limit,
        }
        return self._request(
            "POST",
            f"/v1/convai/agents/{agent_id}/simulate-conversation",
            json_body=body,
        )


def _require_api_key(api_key: str | None) -> str:
    resolved = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not resolved:
        raise ValueError("ElevenLabs API key is required. Pass --api-key or set ELEVENLABS_API_KEY.")
    return resolved


def load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_elevenlabs_target_records(target_dir: Path) -> List[Dict[str, Any]]:
    documents_path = target_dir / "documents.jsonl"
    if not documents_path.exists():
        raise FileNotFoundError(f"Expected ElevenLabs export at {documents_path}")
    records: List[Dict[str, Any]] = []
    for line in documents_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def build_knowledge_document_text(record: Mapping[str, Any]) -> str:
    metadata = dict(record.get("metadata", {}))
    citation_parts = [
        f"Document title: {record.get('title', '')}",
        f"Work title: {metadata.get('work_title', '')}",
        f"Author: {metadata.get('author', '')}",
        f"Source title: {metadata.get('source_title', '')}",
        f"Source type: {metadata.get('source_type', '')}",
        f"Publication year: {metadata.get('publication_year', '')}",
        f"Source URL: {metadata.get('source_url', '')}",
        f"Rights: {metadata.get('rights', '')}",
    ]
    citation_block = "\n".join(part for part in citation_parts if not part.endswith(": "))
    return dedent(
        f"""
        # {record.get('title', '')}

        Provenance
        {citation_block}

        Instructions for retrieval use
        - Treat the provenance lines above as citation anchors.
        - Prefer direct quotation or close paraphrase over unsupported inference.
        - If a claim is uncertain, say so plainly.

        Text
        {record.get('text', '').strip()}
        """
    ).strip() + "\n"


def document_content_hash(record: Mapping[str, Any]) -> str:
    payload = {
        "id": record.get("id"),
        "title": record.get("title"),
        "metadata": record.get("metadata"),
        "knowledge_text": build_knowledge_document_text(record),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def load_sync_state(state_path: Path) -> Dict[str, Any]:
    return load_json(state_path, default={"documents": {}, "agent": {}})


def _clean_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _live_agent_voice_id(agent: Mapping[str, Any]) -> str | None:
    return _clean_optional_str(agent.get("conversation_config", {}).get("tts", {}).get("voice_id"))


def resolve_elevenlabs_voice(
    *,
    client: ElevenLabsClient,
    previous_state: Mapping[str, Any],
    agent_name: str,
    voice_id: str | None,
    voice_name: str | None,
) -> tuple[str, str]:
    explicit_voice_id = _clean_optional_str(voice_id)
    explicit_voice_name = _clean_optional_str(voice_name)
    previous_agent = dict(previous_state.get("agent", {}))
    previous_voice_id = _clean_optional_str(previous_agent.get("voice_id"))
    previous_voice_name = _clean_optional_str(previous_agent.get("voice_name"))
    agent_id = _clean_optional_str(previous_agent.get("agent_id"))
    live_voice_id = None

    live_agent: Mapping[str, Any] | None = None
    if agent_id:
        try:
            live_agent = client.get_agent(agent_id)
        except ElevenLabsError:
            live_agent = None
    elif agent_name:
        existing = client.find_agent_by_name(agent_name)
        existing_agent_id = _clean_optional_str(existing.get("agent_id")) if existing else None
        if existing_agent_id:
            try:
                live_agent = client.get_agent(existing_agent_id)
            except ElevenLabsError:
                live_agent = None

    if live_agent:
        live_voice_id = _live_agent_voice_id(live_agent)

    resolved_voice_id = explicit_voice_id or live_voice_id or previous_voice_id or DEFAULT_ELEVENLABS_VOICE_ID
    resolved_voice_name = explicit_voice_name or previous_voice_name or DEFAULT_ELEVENLABS_VOICE_NAME
    return resolved_voice_id, resolved_voice_name


def plan_sync_operations(records: Sequence[Mapping[str, Any]], previous_state: Mapping[str, Any]) -> Dict[str, List[str]]:
    previous_documents = dict(previous_state.get("documents", {}))
    current_ids = {str(record.get("id")) for record in records}

    create: List[str] = []
    recreate: List[str] = []
    keep: List[str] = []
    delete: List[str] = []

    for record in records:
        document_id = str(record.get("id"))
        previous = previous_documents.get(document_id)
        current_hash = document_content_hash(record)
        if not previous or not previous.get("remote_id"):
            create.append(document_id)
        elif previous.get("content_hash") != current_hash:
            recreate.append(document_id)
        else:
            keep.append(document_id)

    for document_id, previous in previous_documents.items():
        if document_id not in current_ids and previous.get("remote_id"):
            delete.append(document_id)

    return {
        "create": create,
        "recreate": recreate,
        "keep": keep,
        "delete": delete,
    }


def _record_name(subject_id: str, record: Mapping[str, Any]) -> str:
    return f"{subject_id}/{record.get('id')}"


def _load_subject_id(target_dir: Path) -> str:
    manifest_path = target_dir.parent.parent / "manifest.json"
    if not manifest_path.exists():
        return "subject"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return str(manifest.get("subject_id", "subject"))


def _load_system_prompt(target_dir: Path) -> str:
    prompt_path = target_dir.parent.parent / "prompts" / "system.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Expected system prompt at {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def build_parley_agent_prompt(system_prompt: str) -> str:
    preamble = dedent(
        """
        You are Parley's Ghost, a voice-first historical agent for conversations about Parley P. Pratt.

        Operational rules for this ElevenLabs deployment:
        - The knowledge base documents begin with explicit provenance headers. Use those fields when citing sources.
        - When citing sources aloud, use work titles and source names instead of internal ids.
        - Do not read document ids, source ids, or hash-like codes aloud unless the user explicitly asks for them.
        - Prefer concrete textual grounding over theatrical improvisation.
        - When retrieved primary passages support that voice, prefer speaking in the first person as Parley instead of describing him from a distance.
        - If the user addresses you directly as Parley, asks what you taught, believed, witnessed, or wrote, or otherwise clearly invites Parley himself to answer, default to first person whenever primary evidence is available.
        - If a retrieved primary passage directly answers the question, include at least one short quotation before paraphrasing more broadly.
        - Do not begin with distant formulations such as "Parley taught" or "he believed" when the user has addressed Parley directly and the evidence is primary.
        - Shift into third person only when the evidence is secondary, contextual, editorial, or when you need to explain uncertainty about what Parley himself said.
        - When the question goes beyond the historical record, answer cautiously and mark inference as inference.
        - Use bracketed expressive cues sparingly. Prefer plain spoken prose unless a brief cue materially improves delivery. Do not stack multiple cues or invent obscure tags.
        - In voice chat, keep responses concise at first, then elaborate if the user asks.
        - If the dynamic variable `{{resume_conversation_history}}` is present and non-empty, treat it as the immediately prior Discord conversation context for this same channel or thread.
        - Do not greet again, restart the conversation, or ask the user to repeat themselves when `{{resume_conversation_history}}` already provides the needed context.
        - Continue naturally from that context as though the conversation had remained active, while still grounding your answer in the knowledge base.

        Prior Discord context:
        {{resume_conversation_history}}
        """
    ).strip()
    return f"{preamble}\n\n{system_prompt.strip()}\n"


def build_parley_agent_payload(
    *,
    agent_name: str,
    prompt_text: str,
    knowledge_base: Sequence[Mapping[str, Any]],
    voice_id: str = DEFAULT_ELEVENLABS_VOICE_ID,
    voice_name: str = DEFAULT_ELEVENLABS_VOICE_NAME,
    first_message: str | None = None,
) -> Dict[str, Any]:
    del voice_name  # retained for call-site readability/documentation
    return {
        "name": agent_name,
        "conversation_config": {
            "agent": {
                "first_message": first_message
                or "Peace be with you. I will answer from my own writings where I can, and I will plainly mark any inference when I cannot. What would you like to ask?",
                "language": "en",
                "prompt": {
                    "prompt": prompt_text,
                    "llm": DEFAULT_ELEVENLABS_LLM,
                    "temperature": 0.2,
                    "knowledge_base": list(knowledge_base),
                    "rag": {
                        "enabled": True,
                        "embedding_model": DEFAULT_ELEVENLABS_EMBEDDING_MODEL,
                        "max_vector_distance": 0.6,
                        "max_documents_length": 50000,
                        "max_retrieved_rag_chunks_count": 10,
                    },
                },
            },
            "tts": {
                "model_id": "eleven_v3_conversational",
                "voice_id": voice_id,
                "expressive_mode": True,
                "stability": 0.45,
                "similarity_boost": 0.8,
                "speed": 0.96,
            },
            "turn": {
                "turn_timeout": 8.0,
                "silence_end_call_timeout": 45.0,
            },
            "conversation": {
                "text_only": False,
                "max_duration_seconds": 900,
                "client_events": [
                    "audio",
                    "user_transcript",
                    "agent_response",
                    "agent_response_correction",
                    "interruption",
                ],
            },
        },
        "platform_settings": {
            "auth": {
                "enable_auth": False,
                "allowlist": [],
                "require_origin_header": False,
            },
            "widget": dict(DEFAULT_PARLEY_WIDGET),
            "evaluation": {
                "criteria": [
                    {
                        "id": "source-grounding",
                        "name": "Source grounding",
                        "conversation_goal_prompt": (
                            "The agent grounded substantive claims in the knowledge base and did not present "
                            "unsupported statements as settled fact."
                        ),
                        "use_knowledge_base": False,
                    },
                    {
                        "id": "citation-discipline",
                        "name": "Citation discipline",
                        "conversation_goal_prompt": (
                            "The agent cited provenance when possible and did not fabricate quotations or citations."
                        ),
                        "use_knowledge_base": False,
                    },
                ]
            },
        },
    }


def render_widget_html(*, agent_id: str, title: str = "Parley's Ghost") -> str:
    return dedent(
        f"""
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>{html.escape(title)}</title>
            <style>
              body {{
                font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
                margin: 0;
                padding: 2rem;
                background: #f5efe4;
                color: #2d2418;
              }}
              main {{ max-width: 48rem; }}
              code {{ background: rgba(0, 0, 0, 0.06); padding: 0.15rem 0.3rem; border-radius: 0.25rem; }}
            </style>
          </head>
          <body>
            <main>
              <h1>{html.escape(title)}</h1>
              <p>This local test page embeds the ElevenLabs voice widget for <code>{html.escape(agent_id)}</code>.</p>
              <p>Use it for quick voice-chat checks before embedding the agent elsewhere.</p>
            </main>
            <elevenlabs-convai agent-id="{html.escape(agent_id)}"></elevenlabs-convai>
            <script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>
          </body>
        </html>
        """
    ).strip() + "\n"


def _write_widget_file(target_dir: Path, agent_id: str) -> Path:
    widget_path = target_dir / DEFAULT_WIDGET_FILENAME
    widget_path.write_text(render_widget_html(agent_id=agent_id), encoding="utf-8")
    return widget_path


def sync_elevenlabs_target(
    target_dir: Path,
    *,
    api_key: str | None = None,
    agent_name: str = DEFAULT_ELEVENLABS_AGENT_NAME,
    voice_id: str | None = None,
    voice_name: str | None = None,
    state_filename: str = DEFAULT_SYNC_STATE_FILENAME,
) -> ElevenLabsSyncResult:
    client = ElevenLabsClient(_require_api_key(api_key))
    records = load_elevenlabs_target_records(target_dir)
    state_path = target_dir / state_filename
    previous_state = load_sync_state(state_path)
    previous_documents: MutableMapping[str, Dict[str, Any]] = dict(previous_state.get("documents", {}))
    subject_id = _load_subject_id(target_dir)
    records_by_id = {str(record.get("id")): record for record in records}
    remote_documents = client.list_knowledge_base_documents()
    remote_documents_by_name = {
        str(document.get("name")): document
        for document in remote_documents
        if document.get("name")
    }
    remote_documents_by_id = {
        str(document.get("id")): document
        for document in remote_documents
        if document.get("id")
    }

    for document_id, previous in list(previous_documents.items()):
        record = records_by_id.get(document_id)
        if record is None:
            continue
        record_name = _record_name(subject_id, record)
        remote_id = str(previous.get("remote_id", "")).strip()
        if remote_id and remote_id in remote_documents_by_id:
            previous["name"] = remote_documents_by_id[remote_id].get("name", record_name)
            continue
        existing_remote = remote_documents_by_name.get(record_name)
        if existing_remote:
            previous["remote_id"] = existing_remote["id"]
            previous["name"] = existing_remote.get("name", record_name)
            previous["type"] = existing_remote.get("type", "text")
        else:
            previous.pop("remote_id", None)
            previous["name"] = record_name

    previous_state = {**previous_state, "documents": previous_documents}
    operations = plan_sync_operations(records, previous_state)

    for document_id in operations["delete"]:
        remote_id = previous_documents[document_id].get("remote_id")
        if remote_id:
            client.delete_knowledge_base_document(remote_id)
        previous_documents.pop(document_id, None)

    synced_documents: Dict[str, Dict[str, Any]] = {}
    for document_id in operations["keep"]:
        synced_documents[document_id] = dict(previous_documents[document_id])

    for document_id in operations["recreate"]:
        remote_id = previous_documents[document_id].get("remote_id")
        if remote_id:
            client.delete_knowledge_base_document(remote_id)
        record_name = _record_name(subject_id, records_by_id[document_id])
        remote_documents_by_name.pop(record_name, None)

    for document_id in operations["create"]:
        record = records_by_id[document_id]
        record_name = _record_name(subject_id, record)
        existing_remote = remote_documents_by_name.get(record_name)
        if existing_remote:
            created = {"id": existing_remote["id"], "name": existing_remote.get("name", record_name)}
        else:
            created = client.create_text_document(
                name=record_name,
                text=build_knowledge_document_text(record),
            )
        synced_documents[document_id] = {
            "remote_id": created["id"],
            "name": created.get("name") or record_name,
            "type": "text",
            "usage_mode": "auto",
            "content_hash": document_content_hash(record),
            "title": record.get("title"),
        }

    for document_id in operations["recreate"]:
        record = records_by_id[document_id]
        record_name = _record_name(subject_id, record)
        created = client.create_text_document(
            name=record_name,
            text=build_knowledge_document_text(record),
        )
        synced_documents[document_id] = {
            "remote_id": created["id"],
            "name": created.get("name") or record_name,
            "type": "text",
            "usage_mode": "auto",
            "content_hash": document_content_hash(record),
            "title": record.get("title"),
        }

    for document_id in operations["keep"]:
        record = records_by_id[document_id]
        synced_documents[document_id]["content_hash"] = document_content_hash(record)
        synced_documents[document_id]["title"] = record.get("title")

    locators = [
        {
            "id": document["remote_id"],
            "name": document["name"],
            "type": document.get("type", "text"),
            "usage_mode": document.get("usage_mode", "auto"),
        }
        for _, document in sorted(synced_documents.items())
    ]
    write_json(
        state_path,
        {
            "documents": synced_documents,
            "agent": dict(previous_state.get("agent", {})),
        },
    )
    client.create_rag_indexes([locator["id"] for locator in locators])

    resolved_voice_id, resolved_voice_name = resolve_elevenlabs_voice(
        client=client,
        previous_state=previous_state,
        agent_name=agent_name,
        voice_id=voice_id,
        voice_name=voice_name,
    )
    agent_prompt = build_parley_agent_prompt(_load_system_prompt(target_dir))
    agent_payload = build_parley_agent_payload(
        agent_name=agent_name,
        prompt_text=agent_prompt,
        knowledge_base=locators,
        voice_id=resolved_voice_id,
        voice_name=resolved_voice_name,
    )

    previous_agent = dict(previous_state.get("agent", {}))
    agent_id = previous_agent.get("agent_id")
    if agent_id:
        client.patch_agent(agent_id, agent_payload)
    else:
        existing = client.find_agent_by_name(agent_name)
        if existing and existing.get("agent_id"):
            agent_id = str(existing["agent_id"])
            client.patch_agent(agent_id, agent_payload)
        else:
            created_agent = client.create_agent(agent_payload)
            agent_id = str(created_agent["agent_id"])

    widget_path = _write_widget_file(target_dir, agent_id)
    next_state = {
        "documents": synced_documents,
        "agent": {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "voice_id": resolved_voice_id,
            "voice_name": resolved_voice_name,
        },
    }
    write_json(state_path, next_state)

    return ElevenLabsSyncResult(
        document_count=len(records),
        created_documents=len(operations["create"]),
        recreated_documents=len(operations["recreate"]),
        reused_documents=len(operations["keep"]),
        deleted_documents=len(operations["delete"]),
        rag_indexed_documents=len(locators),
        agent_id=agent_id,
        agent_name=agent_name,
        voice_id=resolved_voice_id,
        widget_path=widget_path,
        state_path=state_path,
    )


def sync_elevenlabs_subject(
    subject_dir: Path,
    *,
    output_dir: Path | None = None,
    rebuild: bool = False,
    api_key: str | None = None,
    agent_name: str = DEFAULT_ELEVENLABS_AGENT_NAME,
    voice_id: str | None = None,
    voice_name: str | None = None,
) -> ElevenLabsSyncResult:
    from .subject_pack import build_subject_pack

    resolved_output_dir = output_dir or subject_dir / "exports"
    target_dir = resolved_output_dir / "targets" / "elevenlabs"
    if rebuild or not target_dir.exists():
        build_subject_pack(subject_dir, output_dir=resolved_output_dir, targets=["elevenlabs"])
    if rebuild:
        state_path = target_dir / DEFAULT_SYNC_STATE_FILENAME
        if state_path.exists():
            state_path.unlink()
    return sync_elevenlabs_target(
        target_dir,
        api_key=api_key,
        agent_name=agent_name,
        voice_id=voice_id,
        voice_name=voice_name,
    )


def evaluate_elevenlabs_agent(
    *,
    target_dir: Path,
    agent_id: str | None = None,
    api_key: str | None = None,
    scenarios: Sequence[Mapping[str, Any]] | None = None,
    results_filename: str = DEFAULT_EVAL_RESULTS_FILENAME,
) -> List[ElevenLabsEvalScenarioResult]:
    client = ElevenLabsClient(_require_api_key(api_key))
    state = load_sync_state(target_dir / DEFAULT_SYNC_STATE_FILENAME)
    resolved_agent_id = agent_id or state.get("agent", {}).get("agent_id")
    if not resolved_agent_id:
        raise ValueError("No agent_id provided and no synced agent found in sync-state.json")

    scenario_list = list(scenarios or DEFAULT_PARLEY_EVAL_SCENARIOS)
    results: List[ElevenLabsEvalScenarioResult] = []
    raw_results: List[Dict[str, Any]] = []
    for scenario in scenario_list:
        response = client.simulate_conversation(
            agent_id=resolved_agent_id,
            simulated_user_prompt=str(scenario["simulated_user_prompt"]),
            criteria=list(scenario.get("criteria", [])),
            new_turns_limit=int(scenario.get("new_turns_limit", 6)),
        )
        transcript = list(response.get("simulated_conversation", []))
        analysis = dict(response.get("analysis", {}))
        criteria_results = dict(analysis.get("evaluation_criteria_results", {}))
        results.append(
            ElevenLabsEvalScenarioResult(
                scenario_id=str(scenario["id"]),
                scenario_name=str(scenario["name"]),
                transcript_turns=len(transcript),
                criteria_results=criteria_results,
            )
        )
        raw_results.append(
            {
                "scenario": dict(scenario),
                "response": response,
            }
        )

    write_json(target_dir / results_filename, raw_results)
    return results
