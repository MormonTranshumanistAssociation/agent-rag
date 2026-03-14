from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

import yaml


_LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "ft",
    "ﬆ": "st",
}

_QUOTE_NORMALIZATION = str.maketrans({
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
})


def normalize_ocr_text(text: str, preserve_linebreaks: bool = False) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xad", "")
    normalized = normalized.translate(_QUOTE_NORMALIZATION)
    for source, target in _LIGATURES.items():
        normalized = normalized.replace(source, target)

    normalized = re.sub(r"(?im)^\(\s*\d+\s*\)\s*$", "", normalized)
    normalized = re.sub(r"(?im)^\[\s*\d+\s*\]\s*$", "", normalized)
    normalized = re.sub(r"\^", "", normalized)
    normalized = re.sub(r"\b(Mr|Mrs|Ms|Dr|Rev|St|Sec|No)[,.]\s*(?=[A-Z])", r"\1. ", normalized)
    normalized = re.sub(r"[\"']{2,}", '"', normalized)
    normalized = re.sub(r"(?<=\w)[\"']+-\n(?=\w)", "", normalized)
    normalized = re.sub(r"(?<=\w)-\n(?=\w)", "", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    if preserve_linebreaks:
        lines = [line.rstrip() for line in normalized.split("\n")]
        normalized = "\n".join(lines).strip()
        return normalized + "\n" if normalized else ""

    paragraphs = re.split(r"\n\s*\n", normalized.strip())
    cleaned = []
    for paragraph in paragraphs:
        lines = [re.sub(r"\s+", " ", line.strip()) for line in paragraph.split("\n") if line.strip()]
        if not lines:
            continue
        cleaned.append(" ".join(lines))

    if not cleaned:
        return ""
    return "\n\n".join(cleaned) + "\n"


def render_proofread_prompt(
    *,
    document_id: str,
    source_id: str,
    work_title: str,
    document_title: str,
    preserve_linebreaks: bool = False,
) -> str:
    layout_note = (
        "Preserve meaningful poetic or line-based structure exactly unless a line break is clearly an OCR artifact."
        if preserve_linebreaks
        else "Reconstruct normal prose paragraphs when line wrapping is clearly an OCR artifact."
    )
    return (
        f"# OCR proofread prompt for {document_id}\n\n"
        f"- **Source ID:** {source_id}\n"
        f"- **Work Title:** {work_title}\n"
        f"- **Document Title:** {document_title}\n\n"
        "## Instructions\n\n"
        "Proofread the normalized OCR text conservatively.\n\n"
        "- Correct obvious OCR mistakes only.\n"
        "- Confidently normalize obvious OCR debris instead of preserving meaningless noise verbatim.\n"
        "- Do not modernize the prose, spelling, punctuation, or theology.\n"
        "- Do not silently add content that is not supported by the source.\n"
        "- Mark genuinely uncertain readings with `[[unclear]]` instead of guessing.\n"
        f"- {layout_note}\n"
        "- Preserve the author's voice and keep editorial or non-authorial material separated if encountered.\n\n"
        "## Desired output\n\n"
        "Return the corrected document body only, ready to replace the body of `candidate.md` after review.\n"
    )


def _candidate_front_matter(
    *,
    document_id: str,
    source_id: str,
    work_title: str,
    document_title: str,
    author: str,
    source_type: str,
    composed_year: int | None,
    preserve_linebreaks: bool,
) -> str:
    payload: Dict[str, object] = {
        "document_id": document_id,
        "source_id": source_id,
        "work_title": work_title,
        "document_title": document_title,
        "author": author,
        "source_type": source_type,
        "ocr_status": "needs_proofread",
        "selection_notes": "Generated from OCR normalization; proofread before moving into clean/.",
        "preserve_linebreaks": preserve_linebreaks,
    }
    if composed_year is not None:
        payload["composed_year"] = composed_year
    return "---\n" + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def prepare_ocr_review_packet(
    *,
    input_path: Path,
    output_dir: Path,
    document_id: str,
    source_id: str,
    work_title: str,
    document_title: str,
    author: str,
    source_type: str = "primary",
    composed_year: int | None = None,
    preserve_linebreaks: bool = False,
) -> Path:
    raw_text = input_path.read_text(encoding="utf-8")
    normalized = normalize_ocr_text(raw_text, preserve_linebreaks=preserve_linebreaks)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "normalized.txt").write_text(normalized, encoding="utf-8")
    (output_dir / "candidate.md").write_text(
        _candidate_front_matter(
            document_id=document_id,
            source_id=source_id,
            work_title=work_title,
            document_title=document_title,
            author=author,
            source_type=source_type,
            composed_year=composed_year,
            preserve_linebreaks=preserve_linebreaks,
        )
        + normalized,
        encoding="utf-8",
    )
    (output_dir / "proofread_prompt.md").write_text(
        render_proofread_prompt(
            document_id=document_id,
            source_id=source_id,
            work_title=work_title,
            document_title=document_title,
            preserve_linebreaks=preserve_linebreaks,
        ),
        encoding="utf-8",
    )
    return output_dir
