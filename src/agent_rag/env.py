from __future__ import annotations

import os
import shlex
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if value and value[0] in {'"', "'"}:
        try:
            parsed = shlex.split(value, posix=True)
            if parsed:
                value = parsed[0]
        except ValueError:
            value = value.strip('"\'')
    return key, value


def load_repo_env(start_dir: Path | None = None) -> Path | None:
    """Load a repo-local .env or .env.local without overriding existing env vars.

    Searches upward from *start_dir* (or cwd) until it finds a directory containing
    ``pyproject.toml``. If found, loads ``.env`` then ``.env.local`` from that repo root.
    Returns the repo root when one is found, otherwise ``None``.
    """
    current = (start_dir or Path.cwd()).resolve()
    repo_root: Path | None = None
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists():
            repo_root = candidate
            break
    if repo_root is None:
        return None

    original_keys = set(os.environ)
    for env_name in (".env", ".env.local"):
        env_path = repo_root / env_name
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if key in original_keys:
                continue
            os.environ[key] = value
    return repo_root
