from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .export_targets import DEFAULT_EXPORT_TARGETS, EXPORT_TARGETS
from .ocr_filter import prepare_ocr_review_packet
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

    return parser


def main(argv: Sequence[str] | None = None) -> int:
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

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
