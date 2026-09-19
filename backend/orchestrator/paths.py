from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    override = os.environ.get("WORKSPACE_DIR")
    if override:
        return Path(override).resolve()
    return (repo_root() / "workspace").resolve()
