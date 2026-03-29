from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from .elevenlabs import (
    DEFAULT_ELEVENLABS_AGENT_NAME,
    evaluate_elevenlabs_agent,
    sync_elevenlabs_subject,
)
from .env import load_repo_env
from .export_targets import DEFAULT_EXPORT_TARGETS, EXPORT_TARGETS
from .ocr_filter import prepare_ocr_review_packet
from .ocr_proofreader import proofread_ocr_review_packet
from .subject_pack import build_subject_pack, validate_subject_pack


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-rag", description="Provenance-aware tooling for historical RAG corpora")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a subject pack")
    validate_parser.add_argument("subject_dir", type=Path)

    build_parser = subparsers.add_parser("build", help="Build canonical corpus outputs and target packages for a subject pack")
    build_parser.add_argument("subject_dir", type=Path)
    build_parser.add_argument("--output-dir", type=Path, default=None)
    build_parser.add_argument("--chunk-size", type=int, default=900)
    build_parser.add_argument("--chunk-overlap", type=int, default=120)
    build_parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        choices=sorted(EXPORT_TARGETS),
        default=None,
        help=(
            "Limit provider-specific package generation to the named target(s). "
            f"Defaults to recommended targets: {', '.join(DEFAULT_EXPORT_TARGETS)}"
        ),
    )

    prepare_ocr_parser = subparsers.add_parser(
        "prepare-ocr",
        help="Normalize OCR text and generate a proofreader-ready review packet",
    )
    prepare_ocr_parser.add_argument("input_path", type=Path)
    prepare_ocr_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_ocr_parser.add_argument("--document-id", required=True)
    prepare_ocr_parser.add_argument("--source-id", required=True)
    prepare_ocr_parser.add_argument("--work-title", required=True)
    prepare_ocr_parser.add_argument("--document-title", required=True)
    prepare_ocr_parser.add_argument("--author", required=True)
    prepare_ocr_parser.add_argument("--source-type", default="primary")
    prepare_ocr_parser.add_argument("--composed-year", type=int, default=None)
    prepare_ocr_parser.add_argument("--preserve-linebreaks", action="store_true")

    proofread_ocr_parser = subparsers.add_parser(
        "proofread-ocr",
        help="Use an OpenAI-compatible or native Gemini LLM to conservatively proofread an OCR review packet",
    )
    proofread_ocr_parser.add_argument("review_dir", type=Path)
    proofread_ocr_parser.add_argument("--provider", choices=["openai", "gemini"], default=os.getenv("AGENT_RAG_LLM_PROVIDER", "openai"))
    proofread_ocr_parser.add_argument("--model", default=None)
    proofread_ocr_parser.add_argument("--base-url", default=None)
    proofread_ocr_parser.add_argument("--api-key", default=None)
    proofread_ocr_parser.add_argument("--chunk-chars", type=int, default=6000)
    proofread_ocr_parser.add_argument("--context-paragraphs", type=int, default=1)

    elevenlabs_sync_parser = subparsers.add_parser(
        "elevenlabs-sync",
        help="Sync the ElevenLabs target package into ElevenLabs knowledge base, update/create a Parley's Ghost agent, and emit a local widget page",
    )
    elevenlabs_sync_parser.add_argument("subject_dir", type=Path)
    elevenlabs_sync_parser.add_argument("--output-dir", type=Path, default=None)
    elevenlabs_sync_parser.add_argument("--rebuild", action="store_true")
    elevenlabs_sync_parser.add_argument("--api-key", default=None)
    elevenlabs_sync_parser.add_argument("--agent-name", default=DEFAULT_ELEVENLABS_AGENT_NAME)
    elevenlabs_sync_parser.add_argument("--voice-id", default=None)
    elevenlabs_sync_parser.add_argument("--voice-name", default=None)

    elevenlabs_eval_parser = subparsers.add_parser(
        "elevenlabs-eval",
        help="Run simple simulated-conversation evals against the synced ElevenLabs agent",
    )
    elevenlabs_eval_parser.add_argument("subject_dir", type=Path)
    elevenlabs_eval_parser.add_argument("--output-dir", type=Path, default=None)
    elevenlabs_eval_parser.add_argument("--api-key", default=None)
    elevenlabs_eval_parser.add_argument("--agent-id", default=None)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_repo_env()
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "validate":
        errors = validate_subject_pack(args.subject_dir)
        if errors:
            print("Validation failed:")
            for error in errors:
                print(f"- {error}")
            return 1

        print(f"Validation passed for {args.subject_dir}")
        return 0

    if args.command == "build":
        result = build_subject_pack(
            args.subject_dir,
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            targets=args.targets,
        )
        print(
            f"Built subject pack {result.subject_id} -> {result.output_dir} "
            f"({result.document_count} documents, {result.chunk_count} chunks)"
        )
        return 0

    if args.command == "prepare-ocr":
        output_dir = prepare_ocr_review_packet(
            input_path=args.input_path,
            output_dir=args.output_dir,
            document_id=args.document_id,
            source_id=args.source_id,
            work_title=args.work_title,
            document_title=args.document_title,
            author=args.author,
            source_type=args.source_type,
            composed_year=args.composed_year,
            preserve_linebreaks=args.preserve_linebreaks,
        )
        print(f"Prepared OCR review packet -> {output_dir}")
        return 0

    if args.command == "proofread-ocr":
        output_path = proofread_ocr_review_packet(
            args.review_dir,
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            chunk_chars=args.chunk_chars,
            context_paragraphs=args.context_paragraphs,
        )
        print(f"Proofread OCR review packet -> {output_path}")
        return 0

    if args.command == "elevenlabs-sync":
        result = sync_elevenlabs_subject(
            args.subject_dir,
            output_dir=args.output_dir,
            rebuild=args.rebuild,
            api_key=args.api_key,
            agent_name=args.agent_name,
            voice_id=args.voice_id,
            voice_name=args.voice_name,
        )
        print(
            f"Synced ElevenLabs target -> {result.document_count} docs "
            f"(created {result.created_documents}, recreated {result.recreated_documents}, reused {result.reused_documents}, deleted {result.deleted_documents}); "
            f"agent {result.agent_name} ({result.agent_id}), voice {result.voice_id}, widget {result.widget_path}"
        )
        return 0

    if args.command == "elevenlabs-eval":
        resolved_output_dir = args.output_dir or args.subject_dir / "exports"
        results = evaluate_elevenlabs_agent(
            target_dir=resolved_output_dir / "targets" / "elevenlabs",
            agent_id=args.agent_id,
            api_key=args.api_key,
        )
        print(f"Ran {len(results)} ElevenLabs eval scenario(s)")
        for result in results:
            summaries = []
            for criteria_id, criteria in sorted(result.criteria_results.items()):
                verdict = criteria.get("result") or "unknown"
                summaries.append(f"{criteria_id}={verdict}")
            joined = ", ".join(summaries) if summaries else "no criteria returned"
            print(f"- {result.scenario_id}: {joined}")
        return 0

    parser.error(f"Unknown command: {args.command}")



if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
