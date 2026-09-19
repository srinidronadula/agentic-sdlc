from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class StageId(str, Enum):
    UNDERSTAND = "understand"
    DESIGN = "design"
    IMPLEMENT = "implement"
    TEST = "test"
    DOCS = "docs"


STAGE_ORDER: tuple[StageId, ...] = (
    StageId.UNDERSTAND,
    StageId.DESIGN,
    StageId.IMPLEMENT,
    StageId.TEST,
    StageId.DOCS,
)


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


TERMINAL_STATUSES = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.STOPPED}
)


@dataclass
class AuditEvent:
    ts: str
    type: str
    message: str
    stage: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "type": self.type,
            "message": self.message,
            "stage": self.stage,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AuditEvent:
        return cls(
            ts=raw["ts"],
            type=raw["type"],
            message=raw["message"],
            stage=raw.get("stage"),
            data=raw.get("data") or {},
        )


@dataclass
class StageAttempt:
    attempt: int
    status: StageStatus
    summary: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "status": self.status.value,
            "summary": self.summary,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StageAttempt:
        return cls(
            attempt=raw["attempt"],
            status=StageStatus(raw["status"]),
            summary=raw["summary"],
            started_at=raw["started_at"],
            finished_at=raw["finished_at"],
        )


@dataclass
class StageRecord:
    id: StageId
    status: StageStatus = StageStatus.PENDING
    attempts: int = 0
    summary: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    history: list[StageAttempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id.value,
            "status": self.status.value,
            "attempts": self.attempts,
            "summary": self.summary,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "history": [item.to_dict() for item in self.history],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StageRecord:
        return cls(
            id=StageId(raw["id"]),
            status=StageStatus(raw["status"]),
            attempts=raw.get("attempts", 0),
            summary=raw.get("summary"),
            started_at=raw.get("started_at"),
            finished_at=raw.get("finished_at"),
            history=[StageAttempt.from_dict(item) for item in raw.get("history") or []],
        )


@dataclass
class Approval:
    actor: str
    ts: str
    decision: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Approval:
        return cls(
            actor=raw["actor"],
            ts=raw["ts"],
            decision=raw["decision"],
            note=raw.get("note", ""),
        )


@dataclass
class Run:
    id: str
    requirement: str
    status: RunStatus
    created_at: str
    updated_at: str
    stages: dict[str, StageRecord]
    events: list[AuditEvent] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    test_retries: int = 0
    stop_reason: str | None = None

    def stage(self, stage_id: StageId) -> StageRecord:
        return self.stages[stage_id.value]

    def has_approval(self) -> bool:
        return any(item.decision == "approved" for item in self.approvals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "requirement": self.requirement,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "test_retries": self.test_retries,
            "stop_reason": self.stop_reason,
            "stages": {key: value.to_dict() for key, value in self.stages.items()},
            "approvals": [item.to_dict() for item in self.approvals],
            "events": [item.to_dict() for item in self.events],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Run:
        return cls(
            id=raw["id"],
            requirement=raw["requirement"],
            status=RunStatus(raw["status"]),
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            stages={key: StageRecord.from_dict(value) for key, value in raw["stages"].items()},
            events=[AuditEvent.from_dict(item) for item in raw.get("events") or []],
            approvals=[Approval.from_dict(item) for item in raw.get("approvals") or []],
            test_retries=raw.get("test_retries", 0),
            stop_reason=raw.get("stop_reason"),
        )
