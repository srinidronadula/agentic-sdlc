from __future__ import annotations

from dataclasses import dataclass

from orchestrator.models import STAGE_ORDER, Run, StageId, StageStatus


@dataclass(frozen=True)
class Gate:
    """A human checkpoint that must pass before `before` can start."""

    before: StageId
    kind: str = "human_approval"


# Edges are dependencies: a stage is ready when every predecessor has succeeded.
# This is a graph, not a for-loop — parallel ready-nodes are allowed if two stages
# share the same predecessors.
DEFAULT_DEPS: dict[StageId, tuple[StageId, ...]] = {
    StageId.UNDERSTAND: (),
    StageId.DESIGN: (StageId.UNDERSTAND,),
    StageId.IMPLEMENT: (StageId.DESIGN,),
    StageId.TEST: (StageId.IMPLEMENT,),
    StageId.DOCS: (StageId.TEST,),
}

DEFAULT_GATES: tuple[Gate, ...] = (Gate(before=StageId.IMPLEMENT),)


@dataclass(frozen=True)
class Dag:
    deps: dict[StageId, tuple[StageId, ...]]
    gates: tuple[Gate, ...] = DEFAULT_GATES
    order: tuple[StageId, ...] = STAGE_ORDER

    def predecessors(self, stage: StageId) -> tuple[StageId, ...]:
        return self.deps[stage]

    def successors(self, stage: StageId) -> tuple[StageId, ...]:
        return tuple(node for node, preds in self.deps.items() if stage in preds)

    def gate_before(self, stage: StageId) -> Gate | None:
        for gate in self.gates:
            if gate.before == stage:
                return gate
        return None

    def ready(self, run: Run) -> list[StageId]:
        ready: list[StageId] = []
        for stage in self.order:
            if run.stage(stage).status is not StageStatus.PENDING:
                continue
            preds = self.predecessors(stage)
            if all(run.stage(pred).status is StageStatus.SUCCEEDED for pred in preds):
                ready.append(stage)
        return ready

    def all_succeeded(self, run: Run) -> bool:
        return all(run.stage(stage).status is StageStatus.SUCCEEDED for stage in self.order)


def default_dag() -> Dag:
    return Dag(deps=DEFAULT_DEPS, gates=DEFAULT_GATES)
