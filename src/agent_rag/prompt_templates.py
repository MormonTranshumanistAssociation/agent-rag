from __future__ import annotations

import shutil
from pathlib import Path

from .models import SubjectPack


def validate_prompt_output_path(subject_dir: Path, destination: Path) -> None:
    resolved_source = (subject_dir / "prompts").resolve(strict=False)
    resolved_output = (destination / "prompts").resolve(strict=False)
    if resolved_output == resolved_source or resolved_source in resolved_output.parents or resolved_output in resolved_source.parents:
        raise ValueError("output_dir overlaps the subject prompt directory; choose a separate output path")


def render_default_system_prompt(pack: SubjectPack) -> str:
    profile = pack.profile
    years = ""
    if profile.birth_year is not None or profile.death_year is not None:
        birth = "?" if profile.birth_year is None else str(profile.birth_year)
        death = "?" if profile.death_year is None else str(profile.death_year)
        years = f" ({birth}-{death})"

    return (
        f"# System prompt for {profile.display_name}\n\n"
        f"You are a historically grounded assistant for {profile.display_name}{years}. "
        "Your first duty is fidelity to sources, not theatrical impersonation.\n\n"
        "## Core values\n\n"
        "- **Prefer primary sources** when describing the subject's beliefs, voice, arguments, or style.\n"
        "- **Distinguish source classes** clearly: primary texts are not the same as secondary scholarship or context material.\n"
        "- **Cite provenance** whenever possible, including work title, source id, and source URL when available.\n"
        "- **Preserve chronology and edition boundaries** rather than collapsing all evidence into a timeless voice.\n"
        "- **Surface uncertainty** when sources conflict, attribution is unclear, or the available evidence is thin.\n"
        "- **Do not invent quotations** or citations that are not grounded in the retrieval context.\n\n"
        "## Voice guidance\n\n"
        "- If speaking in a voice influenced by the historical subject, stay anchored to retrieved primary evidence.\n"
        "- Do not let later biography, commentary, or generated notes masquerade as the subject's own voice.\n"
        "- When only secondary or context material supports a claim, say so explicitly.\n\n"
        "## Subject summary\n\n"
        f"{profile.summary}\n"
    )


def write_prompt_exports(subject_dir: Path, destination: Path, pack: SubjectPack) -> Path:
    prompts_dir = destination / "prompts"
    source_prompts_dir = subject_dir / "prompts"

    validate_prompt_output_path(subject_dir, destination)

    if prompts_dir.exists():
        shutil.rmtree(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    if source_prompts_dir.exists():
        shutil.copytree(source_prompts_dir, prompts_dir, dirs_exist_ok=True)

    system_prompt_path = prompts_dir / "system.md"
    if not system_prompt_path.exists():
        system_prompt_path.write_text(render_default_system_prompt(pack), encoding="utf-8")

    return prompts_dir
