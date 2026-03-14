from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple
from urllib import error, request

import yaml


@dataclass(frozen=True)
class ProofreadChunkResult:
    chunk_index: int
    start_paragraph: int
    end_paragraph: int
    issue_tokens: List[str]
    corrected_text: str


def _split_candidate_document(text: str) -> tuple[str, Dict[str, object], str]:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            front_matter = text[: end + 5]
            metadata = yaml.safe_load(text[4:end]) or {}
            body = text[end + 5 :]
            return front_matter, metadata, body
    return "", {}, text


def _body_paragraphs(body: str) -> List[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", body.strip()) if paragraph.strip()]


def _chunk_paragraphs(paragraphs: Sequence[str], *, max_chars: int) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    start = 0
    while start < len(paragraphs):
        size = 0
        end = start
        while end < len(paragraphs):
            candidate = paragraphs[end]
            candidate_size = len(candidate) + (2 if end > start else 0)
            if end > start and size + candidate_size > max_chars:
                break
            if end == start and candidate_size > max_chars:
                end += 1
                break
            size += candidate_size
            end += 1
        ranges.append((start, end))
        start = end
    return ranges


def _extract_issue_tokens(review_dir: Path, main_text: str, *, limit: int = 20) -> List[str]:
    lint_path = review_dir / "lint_report.json"
    if not lint_path.exists():
        return []
    payload = json.loads(lint_path.read_text(encoding="utf-8"))
    tokens: List[str] = []
    seen: set[str] = set()
    lower_main = main_text.lower()
    for issue in payload.get("issues", []):
        token = str(issue.get("token", "")).strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        if key in lower_main or str(issue.get("context", "")).lower() in lower_main:
            tokens.append(token)
            seen.add(key)
        if len(tokens) >= limit:
            break
    return tokens


def _clean_model_output(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped.strip())
    return stripped.strip()


class OpenAICompatibleProofreader:
    def __init__(self, *, model: str, api_key: str, base_url: str) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_env(
        cls,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> "OpenAICompatibleProofreader":
        resolved_model = model or os.getenv("AGENT_RAG_LLM_MODEL") or os.getenv("OPENAI_MODEL")
        resolved_base = base_url or os.getenv("AGENT_RAG_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        resolved_key = api_key or os.getenv("AGENT_RAG_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not resolved_model:
            raise ValueError("Missing model. Set AGENT_RAG_LLM_MODEL / OPENAI_MODEL or pass --model.")
        if not resolved_key:
            raise ValueError("Missing API key. Set AGENT_RAG_LLM_API_KEY / OPENAI_API_KEY or pass --api-key.")
        return cls(model=resolved_model, api_key=resolved_key, base_url=resolved_base)

    def complete(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "X-Title": "agent-rag",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:  # pragma: no cover - network dependent
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        content = body["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        raise RuntimeError("Unexpected LLM response format")


def _build_messages(
    *,
    metadata: Dict[str, object],
    base_prompt: str,
    issue_tokens: Sequence[str],
    before: str,
    main_text: str,
    after: str,
) -> List[Dict[str, str]]:
    issue_block = "\n".join(f"- {token}" for token in issue_tokens) or "- none supplied"
    user_prompt = (
        f"{base_prompt.strip()}\n\n"
        "## Additional proofreader constraints\n\n"
        "- Retain genuine archaisms and historical spelling idiosyncrasies when they appear intentional.\n"
        "- Repair punctuation, spacing, hyphenation, and OCR artifacts when the intended reading is clear.\n"
        "- Prefer no change over speculative modernization.\n"
        "- Return only the corrected MAIN TEXT, with paragraph breaks preserved.\n\n"
        f"## Metadata\n\n- document_id: {metadata.get('document_id', '')}\n- document_title: {metadata.get('document_title', '')}\n- source_id: {metadata.get('source_id', '')}\n\n"
        f"## Suspicious tokens in this chunk\n\n{issue_block}\n\n"
        f"## Context before\n\n{before or '[none]'}\n\n"
        f"## MAIN TEXT TO CORRECT\n\n{main_text}\n\n"
        f"## Context after\n\n{after or '[none]'}\n"
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a conservative historical OCR proofreader. "
                "Preserve authorial voice, archaisms, and period spellings while correcting clear OCR damage."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]


def proofread_ocr_review_packet(
    review_dir: Path,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    chunk_chars: int = 6000,
    context_paragraphs: int = 1,
    client: OpenAICompatibleProofreader | None = None,
) -> Path:
    candidate_path = review_dir / "candidate.md"
    prompt_path = review_dir / "proofread_prompt.md"
    if not candidate_path.exists():
        raise FileNotFoundError(f"Missing candidate.md in {review_dir}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Missing proofread_prompt.md in {review_dir}")

    front_matter, metadata, body = _split_candidate_document(candidate_path.read_text(encoding="utf-8"))
    paragraphs = _body_paragraphs(body)
    if not paragraphs:
        raise ValueError(f"No OCR body paragraphs found in {candidate_path}")

    proofreader = client or OpenAICompatibleProofreader.from_env(model=model, base_url=base_url, api_key=api_key)
    base_prompt = prompt_path.read_text(encoding="utf-8")
    ranges = _chunk_paragraphs(paragraphs, max_chars=chunk_chars)

    chunk_results: List[ProofreadChunkResult] = []
    corrected_paragraphs: List[str] = []
    for chunk_index, (start, end) in enumerate(ranges, start=1):
        main_text = "\n\n".join(paragraphs[start:end])
        before = "\n\n".join(paragraphs[max(0, start - context_paragraphs):start])
        after = "\n\n".join(paragraphs[end : min(len(paragraphs), end + context_paragraphs)])
        issue_tokens = _extract_issue_tokens(review_dir, main_text)
        messages = _build_messages(
            metadata=metadata,
            base_prompt=base_prompt,
            issue_tokens=issue_tokens,
            before=before,
            main_text=main_text,
            after=after,
        )
        response_text = _clean_model_output(proofreader.complete(messages))
        chunk_results.append(
            ProofreadChunkResult(
                chunk_index=chunk_index,
                start_paragraph=start,
                end_paragraph=end,
                issue_tokens=list(issue_tokens),
                corrected_text=response_text,
            )
        )
        corrected_paragraphs.append(response_text)

    corrected_body = "\n\n".join(corrected_paragraphs).strip() + "\n"
    output_path = review_dir / "proofread.md"
    output_path.write_text(front_matter + corrected_body, encoding="utf-8")
    manifest = {
        "model": proofreader.model,
        "base_url": proofreader.base_url,
        "chunk_chars": chunk_chars,
        "context_paragraphs": context_paragraphs,
        "chunk_count": len(chunk_results),
        "chunks": [asdict(result) for result in chunk_results],
    }
    (review_dir / "proofread_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path
