from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .subject_pack import build_subject_pack, validate_subject_pack


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-rag", description="Provenance-aware tooling for historical RAG corpora")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a subject pack")
    validate_parser.add_argument("subject_dir", type=Path)

    build_parser = subparsers.add_parser("build", help="Build corpus and chunk exports for a subject pack")
    build_parser.add_argument("subject_dir", type=Path)
    build_parser.add_argument("--output-dir", type=Path, default=None)
    build_parser.add_argument("--chunk-size", type=int, default=900)
    build_parser.add_argument("--chunk-overlap", type=int, default=120)

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
        )
        print(
            f"Built subject pack {result.subject_id} -> {result.output_dir} "
            f"({result.document_count} documents, {result.chunk_count} chunks)"
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
