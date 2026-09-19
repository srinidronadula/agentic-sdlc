from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.dag import Dag, default_dag
from orchestrator.engine import Orchestrator, OrchestratorError, StageResult
from orchestrator.models import RunStatus, StageId, StageStatus
from orchestrator.store import RunStore


def make_orch(tmp_path: Path, **kwargs) -> Orchestrator:
    return Orchestrator(RunStore(tmp_path), **kwargs)


def open_gate(orch: Orchestrator) -> str:
    run = orch.create("Build a URL shortener")
    run = orch.run_until_blocked(run.id)
    assert run.status is RunStatus.AWAITING_APPROVAL
    assert run.stage(StageId.DESIGN).status is StageStatus.SUCCEEDED
    assert run.stage(StageId.IMPLEMENT).status is StageStatus.PENDING
    return run.id


def test_happy_path_pauses_before_implement(tmp_path: Path) -> None:
    orch = make_orch(tmp_path)
    run_id = open_gate(orch)
    run = orch.advance(run_id)
    assert run.status is RunStatus.AWAITING_APPROVAL
    assert run.stage(StageId.IMPLEMENT).attempts == 0


def test_approve_then_completes(tmp_path: Path) -> None:
    orch = make_orch(tmp_path)
    run_id = open_gate(orch)
    orch.approve(run_id, actor="nikhil")
    run = orch.run_until_blocked(run_id)
    assert run.status is RunStatus.SUCCEEDED
    assert all(run.stage(stage).status is StageStatus.SUCCEEDED for stage in StageId)
    types = [event.type for event in run.events]
    assert types.count("approval_required") == 1
    assert types.count("approved") == 1
    assert types[-1] == "run_succeeded"


def test_test_failure_retries_implement_once(tmp_path: Path) -> None:
    calls = {"implement": 0, "test": 0}

    def implement(_run, _stage) -> StageResult:
        calls["implement"] += 1
        return StageResult(ok=True, summary=f"implement {calls['implement']}")

    def test(_run, _stage) -> StageResult:
        calls["test"] += 1
        if calls["test"] == 1:
            return StageResult(ok=False, summary="tests failed")
        return StageResult(ok=True, summary="tests passed")

    orch = make_orch(
        tmp_path,
        handlers={StageId.IMPLEMENT: implement, StageId.TEST: test},
    )
    run_id = open_gate(orch)
    orch.approve(run_id, actor="nikhil")
    run = orch.run_until_blocked(run_id)

    assert calls == {"implement": 2, "test": 2}
    assert run.test_retries == 1
    assert run.status is RunStatus.SUCCEEDED
    assert run.stage(StageId.IMPLEMENT).attempts == 2
    assert any(event.type == "retry_scheduled" for event in run.events)


def test_second_test_failure_stops(tmp_path: Path) -> None:
    def test(_run, _stage) -> StageResult:
        return StageResult(ok=False, summary="still red")

    orch = make_orch(tmp_path, handlers={StageId.TEST: test})
    run_id = open_gate(orch)
    orch.approve(run_id, actor="nikhil")
    run = orch.run_until_blocked(run_id)

    assert run.status is RunStatus.FAILED
    assert run.test_retries == 1
    assert run.stage(StageId.TEST).attempts == 2
    assert any(event.type == "retry_exhausted" for event in run.events)
    assert run.stop_reason == "test failed after retry"


def test_non_test_failure_does_not_retry(tmp_path: Path) -> None:
    def design(_run, _stage) -> StageResult:
        return StageResult(ok=False, summary="ambiguous requirements")

    orch = make_orch(tmp_path, handlers={StageId.DESIGN: design})
    run = orch.create("unclear ask")
    run = orch.run_until_blocked(run.id)
    assert run.status is RunStatus.FAILED
    assert run.test_retries == 0
    assert run.stage(StageId.IMPLEMENT).status is StageStatus.PENDING


def test_stop_is_terminal(tmp_path: Path) -> None:
    orch = make_orch(tmp_path)
    run = orch.create("stop me")
    orch.advance(run.id)
    run = orch.stop(run.id, reason="operator halt")
    assert run.status is RunStatus.STOPPED
    assert run.stage(StageId.DESIGN).status is StageStatus.CANCELLED
    again = orch.advance(run.id)
    assert again.status is RunStatus.STOPPED


def test_reject_stops_at_gate(tmp_path: Path) -> None:
    orch = make_orch(tmp_path)
    run_id = open_gate(orch)
    run = orch.reject(run_id, actor="nikhil", note="scope too large")
    assert run.status is RunStatus.STOPPED
    assert run.approvals[0].decision == "rejected"
    with pytest.raises(OrchestratorError):
        orch.approve(run_id, actor="nikhil")


def test_state_reloads_from_disk(tmp_path: Path) -> None:
    orch = make_orch(tmp_path)
    run_id = open_gate(orch)
    restored = Orchestrator(RunStore(tmp_path))
    loaded = restored.get(run_id)
    assert loaded.status is RunStatus.AWAITING_APPROVAL
    assert loaded.stage(StageId.UNDERSTAND).status is StageStatus.SUCCEEDED


def test_parallel_ready_nodes_on_custom_dag(tmp_path: Path) -> None:
    dag = Dag(
        deps={
            StageId.UNDERSTAND: (),
            StageId.DESIGN: (StageId.UNDERSTAND,),
            StageId.IMPLEMENT: (StageId.DESIGN,),
            StageId.TEST: (StageId.IMPLEMENT,),
            StageId.DOCS: (StageId.IMPLEMENT,),
        }
    )
    orch = make_orch(tmp_path, dag=dag)
    run_id = open_gate(orch)
    orch.approve(run_id, actor="nikhil")
    run = orch.advance(run_id)
    assert run.stage(StageId.IMPLEMENT).status is StageStatus.SUCCEEDED
    assert dag.ready(run) == [StageId.TEST, StageId.DOCS]


def test_default_graph_is_sequential() -> None:
    dag = default_dag()
    assert dag.predecessors(StageId.IMPLEMENT) == (StageId.DESIGN,)
    assert dag.gate_before(StageId.IMPLEMENT) is not None
    assert dag.gate_before(StageId.TEST) is None
