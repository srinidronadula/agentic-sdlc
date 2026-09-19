from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from orchestrator.dag import Dag, default_dag
from orchestrator.models import (
    STAGE_ORDER,
    Approval,
    AuditEvent,
    Run,
    RunStatus,
    StageAttempt,
    StageId,
    StageRecord,
    StageStatus,
    TERMINAL_STATUSES,
)
from orchestrator.store import RunStore

RETRY_DOWNSTREAM = (StageId.IMPLEMENT, StageId.TEST, StageId.DOCS)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StageResult:
    ok: bool
    summary: str


Handler = Callable[[Run, StageId], StageResult]


def stub_handler(run: Run, stage: StageId) -> StageResult:
    return StageResult(ok=True, summary=f"{stage.value} completed (stub, no LLM)")


class OrchestratorError(RuntimeError):
    pass


class Orchestrator:
    """Advance a run one stage at a time. Persist after every mutation."""

    def __init__(
        self,
        store: RunStore,
        dag: Dag | None = None,
        handlers: dict[StageId, Handler] | None = None,
        max_test_retries: int = 1,
    ) -> None:
        self.store = store
        self.dag = dag or default_dag()
        self.handlers = handlers or {}
        self.max_test_retries = max_test_retries

    def create(self, requirement: str) -> Run:
        now = utcnow()
        run = Run(
            id=str(uuid.uuid4()),
            requirement=requirement.strip(),
            status=RunStatus.CREATED,
            created_at=now,
            updated_at=now,
            stages={stage.value: StageRecord(id=stage) for stage in self.dag.order},
        )
        self._audit(run, "run_created", "Run created")
        return self._persist(run)

    def get(self, run_id: str) -> Run:
        return self.store.load(run_id)

    def approve(self, run_id: str, actor: str, note: str = "") -> Run:
        run = self.get(run_id)
        self._require_active(run)
        if run.status is not RunStatus.AWAITING_APPROVAL:
            raise OrchestratorError("no pending approval gate")
        run.approvals.append(
            Approval(actor=actor, ts=utcnow(), decision="approved", note=note)
        )
        run.status = RunStatus.RUNNING
        self._audit(
            run,
            "approved",
            f"{actor} approved implement",
            stage=StageId.IMPLEMENT,
            actor=actor,
        )
        return self._persist(run)

    def reject(self, run_id: str, actor: str, note: str = "") -> Run:
        run = self.get(run_id)
        self._require_active(run)
        run.approvals.append(
            Approval(actor=actor, ts=utcnow(), decision="rejected", note=note)
        )
        self._persist(run)
        reason = f"rejected by {actor}"
        if note:
            reason = f"{reason}: {note}"
        return self.stop(run.id, reason=reason)

    def stop(self, run_id: str, reason: str = "human safe-stop") -> Run:
        run = self.get(run_id)
        if run.status in TERMINAL_STATUSES:
            return run
        now = utcnow()
        for record in run.stages.values():
            if record.status in {StageStatus.PENDING, StageStatus.RUNNING}:
                record.status = StageStatus.CANCELLED
                record.finished_at = now
        run.status = RunStatus.STOPPED
        run.stop_reason = reason
        self._audit(run, "stopped", reason)
        return self._persist(run)

    def run_until_blocked(self, run_id: str) -> Run:
        run = self.get(run_id)
        while run.status not in TERMINAL_STATUSES and run.status is not RunStatus.AWAITING_APPROVAL:
            snapshot = _fingerprint(run)
            run = self.advance(run.id)
            if _fingerprint(run) == snapshot:
                break
        return run

    def advance(self, run_id: str) -> Run:
        run = self.get(run_id)
        if run.status in TERMINAL_STATUSES or run.status is RunStatus.AWAITING_APPROVAL:
            return run

        ready = self.dag.ready(run)
        if not ready:
            if self.dag.all_succeeded(run):
                run.status = RunStatus.SUCCEEDED
                self._audit(run, "run_succeeded", "All stages succeeded")
                return self._persist(run)
            return run

        stage = ready[0]
        gate = self.dag.gate_before(stage)
        if gate is not None and gate.kind == "human_approval" and not run.has_approval():
            run.status = RunStatus.AWAITING_APPROVAL
            self._audit(
                run,
                "approval_required",
                f"Human approval required before {stage.value}",
                stage=stage,
                gate=gate.kind,
            )
            return self._persist(run)

        return self._execute(run, stage)

    def _execute(self, run: Run, stage: StageId) -> Run:
        record = run.stage(stage)
        record.status = StageStatus.RUNNING
        record.attempts += 1
        record.started_at = utcnow()
        record.finished_at = None
        record.summary = None
        run.status = RunStatus.RUNNING
        self._audit(
            run,
            "stage_started",
            f"Started {stage.value} (attempt {record.attempts})",
            stage=stage,
            attempt=record.attempts,
        )
        self._persist(run)

        try:
            result = self.handlers.get(stage, stub_handler)(run, stage)
        except Exception as exc:  # noqa: BLE001 — stage crash is a failed node, not a process crash
            result = StageResult(ok=False, summary=f"{stage.value} crashed: {exc}")

        record.finished_at = utcnow()
        record.summary = result.summary
        record.history.append(
            StageAttempt(
                attempt=record.attempts,
                status=StageStatus.SUCCEEDED if result.ok else StageStatus.FAILED,
                summary=result.summary,
                started_at=record.started_at,
                finished_at=record.finished_at,
            )
        )

        if result.ok:
            record.status = StageStatus.SUCCEEDED
            self._audit(run, "stage_succeeded", result.summary, stage=stage, attempt=record.attempts)
            if self.dag.all_succeeded(run):
                run.status = RunStatus.SUCCEEDED
                self._audit(run, "run_succeeded", "All stages succeeded")
            return self._persist(run)

        record.status = StageStatus.FAILED
        self._audit(run, "stage_failed", result.summary, stage=stage, attempt=record.attempts)

        if stage is StageId.TEST and run.test_retries < self.max_test_retries:
            run.test_retries += 1
            self._reset_for_test_retry(run)
            self._audit(
                run,
                "retry_scheduled",
                f"Test failed; retrying implement→test ({run.test_retries}/{self.max_test_retries})",
                stage=stage,
                retry=run.test_retries,
            )
            run.status = RunStatus.RUNNING
            return self._persist(run)

        if stage is StageId.TEST:
            run.stop_reason = "test failed after retry"
            self._audit(run, "retry_exhausted", "Test failed after retry; stopping", stage=stage)

        run.status = RunStatus.FAILED
        self._audit(run, "run_failed", f"{stage.value} failed", stage=stage)
        return self._persist(run)

    def _reset_for_test_retry(self, run: Run) -> None:
        for stage in RETRY_DOWNSTREAM:
            if stage not in {StageId(key) for key in run.stages}:
                continue
            record = run.stage(stage)
            record.status = StageStatus.PENDING
            record.summary = None
            record.started_at = None
            record.finished_at = None

    def _audit(
        self,
        run: Run,
        event_type: str,
        message: str,
        stage: StageId | None = None,
        **data: object,
    ) -> None:
        run.events.append(
            AuditEvent(
                ts=utcnow(),
                type=event_type,
                message=message,
                stage=stage.value if stage else None,
                data=data,
            )
        )
        run.updated_at = utcnow()

    def _persist(self, run: Run) -> Run:
        self.store.save(run)
        return run

    def _require_active(self, run: Run) -> None:
        if run.status in TERMINAL_STATUSES:
            raise OrchestratorError(f"run {run.id} is {run.status.value}")


def _fingerprint(run: Run) -> tuple[object, ...]:
    return (
        run.status,
        tuple(
            (stage, run.stage(stage).status, run.stage(stage).attempts)
            for stage in STAGE_ORDER
            if stage.value in run.stages
        ),
        run.test_retries,
        len(run.events),
    )
