from __future__ import annotations

import os
from pathlib import Path

from agent_rag.env import load_repo_env


def test_load_repo_env_loads_dotenv_without_overriding_existing(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (repo / ".env").write_text(
        "ELEVENLABS_API_KEY=repo-key\nSHARED_KEY=from-dotenv\nexport QUOTED='hello world'\n",
        encoding="utf-8",
    )
    (repo / ".env.local").write_text(
        "ELEVENLABS_API_KEY=local-key\nLOCAL_ONLY=present\n",
        encoding="utf-8",
    )
    nested = repo / "nested" / "deeper"
    nested.mkdir(parents=True)

    monkeypatch.setenv("SHARED_KEY", "already-set")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)
    monkeypatch.delenv("LOCAL_ONLY", raising=False)

    repo_root = load_repo_env(nested)

    assert repo_root == repo
    assert os.getenv("ELEVENLABS_API_KEY") == "local-key"
    assert os.getenv("SHARED_KEY") == "already-set"
    assert os.getenv("QUOTED") == "hello world"
    assert os.getenv("LOCAL_ONLY") == "present"


def test_load_repo_env_returns_none_when_no_repo_found(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert load_repo_env(tmp_path) is None
    assert os.getenv("ELEVENLABS_API_KEY") is None
