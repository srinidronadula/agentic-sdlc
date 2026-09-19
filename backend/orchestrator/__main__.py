from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orchestrator.factory import build_orchestrator, has_llm_key, load_env
from orchestrator.store import RunStore


def main() -> None:
    load_env()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run the SDLC orchestrator")
    parser.add_argument(
        "requirement",
        nargs="?",
        default="Build a URL shortener with create, redirect, and click counts.",
    )
    parser.add_argument("--approve", action="store_true", help="pass the implement gate")
    parser.add_argument("--actor", default="human")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent / "var" / "runs"
    orch = build_orchestrator(RunStore(root))
    run = orch.create(args.requirement)
    run = orch.run_until_blocked(run.id)
    if args.approve and run.status.value == "awaiting_approval":
        orch.approve(run.id, actor=args.actor, note="CLI approve")
        run = orch.run_until_blocked(run.id)

    print(f"run {run.id}")
    print(f"llm:  {'anthropic' if has_llm_key() else 'stub'}")
    print(f"status: {run.status.value}")
    print(f"state:  {orch.store.path(run.id)}")
    print("events:")
    for event in run.events:
        stage = f" [{event.stage}]" if event.stage else ""
        print(f"  - {event.type}{stage}: {event.message}")
    if run.status.value == "awaiting_approval":
        print("next: python -m orchestrator --approve")


if __name__ == "__main__":
    main()
