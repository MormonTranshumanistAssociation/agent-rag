"""agent-rag: provenance-aware corpus tooling for historical RAG projects."""

from .subject_pack import build_subject_pack, validate_subject_pack

__all__ = ["build_subject_pack", "validate_subject_pack"]
__version__ = "0.1.0"
