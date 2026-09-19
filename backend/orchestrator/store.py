from __future__ import annotations

import json
from pathlib import Path

from orchestrator.models import Run


class RunStore:
    """JSON document per run. Atomic replace so a crash does not leave half a file."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        return self.root / f"{run_id}.json"

    def save(self, run: Run) -> None:
        path = self.path(run.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(run.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    def load(self, run_id: str) -> Run:
        return Run.from_dict(json.loads(self.path(run_id).read_text(encoding="utf-8")))
