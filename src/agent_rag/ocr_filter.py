from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

import yaml
from spellchecker import SpellChecker


_LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "ft",
    "ﬆ": "st",
}

_QUOTE_NORMALIZATION = str.maketrans(
    {
        "«": '"',
        "»": '"',
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)

_HONORIFICS = {"mr", "mrs", "ms", "dr", "rev", "st", "sec", "no"}
_HONORIFIC_INITIAL_RE = re.compile(r"^(?:Mr|Mrs|Ms|Dr|Rev|St|Sec|No)\.[A-Z]\.?$")
_ARCHAIC_ALLOWLIST = {
    "thro",
    "thro'",
    "hath",
    "doth",
    "saith",
    "unto",
    "wherein",
    "whereof",
    "thereof",
    "wherefore",
    "whosoever",
    "whatsoever",
    "inasmuch",
    "therewith",
    "thereunto",
    "thereby",
    "therein",
    "begat",
    "whither",
    "thither",
    "hither",
    "publick",
    "connexion",
    "labour",
    "favour",
    "honour",
    "saviour",
    "nephite",
    "nephites",
    "gentile",
    "gentiles",
    "mahommedism",
    "sunderland",
    "swedenborg",
    "deseret",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’.-]*")
_PAGE_ARTIFACT_RE = re.compile(r"^\(?\s*\d+\s*\)?$")
_HONORIFIC_SPACING_RE = re.compile(r"\b(Mr|Mrs|Ms|Dr|Rev|St|Sec|No)[,.]\s*([A-Z])\.")
_PUNCTUATION_NOISE_RE = re.compile(r"\b\S*[\^*_«»]+\S*\b")
_ROMAN_RE = re.compile(r"^[IVXLCDM]+$", re.I)
_SENTENCE_END_RE = re.compile(r'^(?P<body>.*?)(?P<terminal>[1Il|7.;:!?])?(?P<trailer>["\')\]”’]*)$')
_SENTENCE_START_RE = re.compile(r'^["“‘(\[]?[A-Z]')
_QUESTION_SEGMENT_RE = re.compile(
    r'(?i)(?:^|[;:—]\s+|\b(?:but|and|or|nor|yet)\b\s+)(?:who|what|when|where|why|how)\b|(?:^|[;:—]\s+|\b(?:but|and|or|nor|yet)\b\s+)(?:do|does|did|is|are|was|were|have|has|had|can|could|would|should|will|shall|may|might|must)\b'
)
_EXCLAMATION_SEGMENT_RE = re.compile(r'(?i)^(?:["“‘(\[]*)?(?:o\b|what\s+(?:a|an)\b|how\s+\w+)')

_SPELLCHECKER = SpellChecker(distance=2)


@dataclass(frozen=True)
class OCRIssue:
    line_number: int
    token: str
    category: str
    suggestion: str | None
    context: str


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _normalize_lookup_token(token: str) -> str:
    normalized = token.translate(_QUOTE_NORMALIZATION)
    normalized = normalized.strip("\"'.,;:!?()[]{}“”‘’")
    normalized = normalized.replace("’", "'")
    if normalized.endswith("'s"):
        normalized = normalized[:-2]
    return normalized


def _is_allowed_word(token: str) -> bool:
    lowered = token.lower()
    return (
        lowered in _ARCHAIC_ALLOWLIST
        or lowered in _HONORIFICS
        or lowered.endswith(("eth", "est"))
        or token.isupper()
        or "-" in token
        or bool(_ROMAN_RE.fullmatch(token))
        or bool(_HONORIFIC_INITIAL_RE.fullmatch(token))
    )


def _smartify_quotes(text: str) -> str:
    text = re.sub(r"(?<=\w)'(?=\w)", "’", text)
    result: list[str] = []
    for index, char in enumerate(text):
        if char not in {'"', "'"}:
            result.append(char)
            continue

        prev = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        prev_nonspace = next((text[pos] for pos in range(index - 1, -1, -1) if not text[pos].isspace()), "")
        next_nonspace = next((text[pos] for pos in range(index + 1, len(text)) if not text[pos].isspace()), "")
        if char == '"':
            is_opening = bool(
                next_nonspace
                and next_nonspace.isalnum()
                and (not prev or prev.isspace() or prev in "([{—<")
            )
            is_closing = bool(
                not next_nonspace
                or next_nonspace in ",.;:!?)]}—"
                or (prev and not prev.isspace() and prev not in "([{—<")
            )
            result.append("“" if is_opening and not is_closing else "”")
        else:
            if prev.isalnum() and next_char.isalnum():
                result.append("’")
            else:
                is_opening = bool(
                    next_nonspace
                    and next_nonspace.isalnum()
                    and (not prev or prev.isspace() or prev in "([{—<")
                )
                result.append("‘" if is_opening else "’")
    return "".join(result)


def _infer_sentence_force(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return "statement"
    normalized = normalized.translate(_QUOTE_NORMALIZATION)
    if _QUESTION_SEGMENT_RE.search(normalized):
        return "question"
    if _EXCLAMATION_SEGMENT_RE.search(normalized):
        return "exclamation"
    return "statement"


def _apply_terminal_punctuation(text: str, punctuation: str) -> str:
    match = _SENTENCE_END_RE.fullmatch(text.strip())
    if not match:
        return text
    body = match.group("body").rstrip()
    terminal = match.group("terminal") or ""
    trailer = match.group("trailer") or ""
    if terminal == punctuation:
        return f"{body}{terminal}{trailer}"
    if terminal:
        return f"{body}{punctuation}{trailer}"
    return f"{body}{punctuation}{trailer}"


def _looks_like_sentence_boundary(current: str, next_line: str) -> bool:
    match = _SENTENCE_END_RE.fullmatch(current.strip())
    if not match:
        return False

    terminal = match.group("terminal") or ""
    body = match.group("body").rstrip()
    if not terminal:
        return False
    if terminal in ";:":
        return False
    if terminal == ".":
        if re.search(r"\b(?:Mr|Mrs|Ms|Dr|Rev|St|Sec|No|Gen|Gov|Col|Capt|Lt|Maj|Sgt|Hon|Jr|Sr|Esq)\.$", body):
            return False
        if re.search(r"\b[A-Z]\.$", body):
            return False
    if next_line and not _SENTENCE_START_RE.match(next_line):
        return False
    return True


def _reconstruct_sentence_candidates(lines: list[str]) -> list[str]:
    candidates: list[str] = []
    current = ""

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if not current:
            current = line
            continue
        if _looks_like_sentence_boundary(current, line):
            candidates.append(current)
            current = line
        else:
            current = f"{current} {line}"

    if current:
        candidates.append(current)
    return candidates


def _repair_sentence_terminal_punctuation(sentence: str) -> str:
    force = _infer_sentence_force(sentence)
    if force == "statement":
        return sentence
    punctuation = "?" if force == "question" else "!"
    return _apply_terminal_punctuation(sentence, punctuation)


def _normalize_typography(text: str) -> str:
    text = re.sub(r"-\s*—|—\s*-", " — ", text)
    text = re.sub(r"(?<=\w)——+(?=\w)", "—", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+—\s+", " — ", text)
    text = _smartify_quotes(text)
    text = re.sub(r"(?<=[A-Za-z0-9,.;:!?])“", " “", text)
    text = re.sub(r"”(?=[A-Za-z0-9])", "” ", text)
    text = re.sub(r"([“‘])\s+", r"\1", text)
    text = re.sub(r"\s+([”’])", r"\1", text)
    return text


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
        stanzas = []
        for stanza in re.split(r"\n\s*\n", normalized.strip()):
            lines = [re.sub(r"\s+", " ", line.strip()) for line in stanza.split("\n") if line.strip()]
            if not lines:
                continue
            stanzas.append("<br>\n".join(lines))
        normalized = "\n\n".join(stanzas)
        normalized = _normalize_typography(normalized).strip()
        return normalized + "\n" if normalized else ""

    paragraphs = re.split(r"\n\s*\n", normalized.strip())
    cleaned = []
    for paragraph in paragraphs:
        lines = [re.sub(r"\s+", " ", line.strip()) for line in paragraph.split("\n") if line.strip()]
        if not lines:
            continue
        sentence_candidates = _reconstruct_sentence_candidates(lines)
        repaired_sentences = [_repair_sentence_terminal_punctuation(sentence) for sentence in sentence_candidates]
        cleaned.append(" ".join(repaired_sentences))

    if not cleaned:
        return ""
    return _normalize_typography("\n\n".join(cleaned)).strip() + "\n"


def find_ocr_issues(text: str) -> List[OCRIssue]:
    issues: List[OCRIssue] = []
    seen: set[tuple[int, str, str]] = set()
    in_front_matter = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if line_number == 1 and stripped == "---":
            in_front_matter = True
            continue
        if in_front_matter:
            if stripped == "---":
                in_front_matter = False
            continue
        if not stripped:
            continue

        if _PAGE_ARTIFACT_RE.fullmatch(stripped):
            issue = OCRIssue(
                line_number=line_number,
                token=stripped,
                category="page_artifact",
                suggestion=None,
                context=stripped,
            )
            key = (issue.line_number, issue.token, issue.category)
            seen.add(key)
            issues.append(issue)
            continue

        for match in _HONORIFIC_SPACING_RE.finditer(line):
            token = match.group(0)
            issue = OCRIssue(
                line_number=line_number,
                token=token,
                category="honorific_spacing",
                suggestion=f"{match.group(1)}. {match.group(2)}.",
                context=stripped,
            )
            key = (issue.line_number, issue.token, issue.category)
            if key not in seen:
                seen.add(key)
                issues.append(issue)

        for match in _PUNCTUATION_NOISE_RE.finditer(line):
            token = match.group(0)
            cleaned = token.translate(_QUOTE_NORMALIZATION)
            cleaned = re.sub(r'["\'^*_]', '', cleaned)
            if '-' in cleaned and cleaned.replace('-', '').isalpha():
                cleaned = cleaned.replace('-', '')
            issue = OCRIssue(
                line_number=line_number,
                token=token,
                category="ocr_punctuation_noise",
                suggestion=cleaned if cleaned and cleaned != token else None,
                context=stripped,
            )
            key = (issue.line_number, issue.token, issue.category)
            if key not in seen:
                seen.add(key)
                issues.append(issue)

        for match in _WORD_RE.finditer(line):
            token = match.group(0)
            lookup = _normalize_lookup_token(token)
            if len(lookup) < 4 or _is_allowed_word(lookup):
                continue

            lowered = lookup.lower()
            if lowered not in _SPELLCHECKER:
                suggestion = _SPELLCHECKER.correction(lowered)
                if suggestion == lowered:
                    suggestion = None
                elif suggestion is not None:
                    if token and token[0].isupper():
                        suggestion = suggestion.capitalize()
                    if _edit_distance(lowered, suggestion.lower()) > 2:
                        suggestion = None

                category = "proper_noun_or_archaism" if token[:1].isupper() else "likely_spelling_error"
                issue = OCRIssue(
                    line_number=line_number,
                    token=token,
                    category=category,
                    suggestion=suggestion,
                    context=stripped,
                )
                key = (issue.line_number, issue.token, issue.category)
                if key not in seen:
                    seen.add(key)
                    issues.append(issue)

    return issues


def render_lint_report_markdown(issues: List[OCRIssue]) -> str:
    if not issues:
        return "# OCR lint report\n\nNo suspicious tokens detected.\n"

    lines = ["# OCR lint report", "", f"Issue count: {len(issues)}", ""]
    for issue in issues:
        lines.extend(
            [
                f"## Line {issue.line_number}: `{issue.token}`",
                "",
                f"- category: `{issue.category}`",
                f"- suggestion: `{issue.suggestion or 'none'}`",
                f"- context: `{issue.context}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_lint_reports(output_dir: Path, issues: List[OCRIssue]) -> None:
    (output_dir / "lint_report.md").write_text(render_lint_report_markdown(issues), encoding="utf-8")
    payload = {"issue_count": len(issues), "issues": [asdict(issue) for issue in issues]}
    (output_dir / "lint_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    issues = find_ocr_issues(normalized)

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
    write_lint_reports(output_dir, issues)
    return output_dir
