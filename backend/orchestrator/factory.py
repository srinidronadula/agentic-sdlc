from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from orchestrator.engine import Orchestrator
from orchestrator.paths import repo_root
from orchestrator.store import RunStore


def load_env() -> None:
    load_dotenv(repo_root() / ".env", override=False)


def has_llm_key() -> bool:
    load_env()
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def build_orchestrator(store: RunStore | None = None) -> Orchestrator:
    """Use Anthropic-backed stage handlers when a key is present; otherwise stubs."""
    load_env()
    if store is None:
        store = RunStore(Path(os.environ.get("RUN_STORE_DIR", repo_root() / "backend" / "var" / "runs")))
    if has_llm_key():
        from orchestrator.agents import llm_handlers

        return Orchestrator(store, handlers=llm_handlers())
    return Orchestrator(store)
