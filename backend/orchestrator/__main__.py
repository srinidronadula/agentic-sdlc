from __future__ import annotations

from pathlib import Path

from orchestrator.engine import Orchestrator
from orchestrator.store import RunStore


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "var" / "runs"
    orch = Orchestrator(RunStore(root))
    run = orch.create("Build a URL shortener (orchestrator stub; no LLM yet)")
    run = orch.run_until_blocked(run.id)
    print(f"run {run.id}")
    print(f"status: {run.status.value}")
    print(f"state:  {orch.store.path(run.id)}")
    print("events:")
    for event in run.events:
        stage = f" [{event.stage}]" if event.stage else ""
        print(f"  - {event.type}{stage}: {event.message}")
    if run.status.value == "awaiting_approval":
        print("next: orch.approve(run_id, actor='human') then run_until_blocked")


if __name__ == "__main__":
    main()
