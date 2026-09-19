from __future__ import annotations

from orchestrator.engine import Handler, StageResult
from orchestrator.llm import AnthropicLLM, default_executor, tool_specs
from orchestrator.models import STAGE_ORDER, Run, StageId
from orchestrator.tools import run_tests

SYSTEM = """You are a stage in a governed SDLC orchestrator.
Stay inside the current stage. Do not skip the human implement gate.
Never write secrets, .env files, or files outside workspace/.
Prefer small, boring, testable Python.
"""

IMPLEMENT_SPEC = """workspace/ already has a FastAPI URL shortener (sqlite, pytest, TestClient).

Use only tools write_file, read_file, run_tests.
First read_file: shortener/app.py, shortener/service.py, shortener/db.py, tests/test_shortener.py.

Greenfield: if those files are missing, create a tiny shortener
(POST /shorten, GET /{code} 302, GET /stats/{code}, sqlite, tests).
Brownfield: patch the existing modules. Keep current APIs working.
Do not rewrite the service from scratch.

Keep going until run_tests returns exit=0.
Do not explain instead of writing files.
"""


def _context(run: Run) -> str:
    parts = [f"Requirement:\n{run.requirement}"]
    for stage in STAGE_ORDER:
        record = run.stage(stage)
        if record.summary:
            parts.append(f"Completed {stage.value}:\n{record.summary}")
    return "\n\n".join(parts)


def _result(ok: bool, text: str) -> StageResult:
    summary = text.strip() or ("succeeded" if ok else "failed")
    return StageResult(ok=ok, summary=summary[:4000])


def llm_handlers(llm: AnthropicLLM | None = None) -> dict[StageId, Handler]:
    client = llm

    def get_llm() -> AnthropicLLM:
        nonlocal client
        if client is None:
            client = AnthropicLLM()
        return client

    def understand(run: Run, _stage: StageId) -> StageResult:
        text = get_llm().run(
            SYSTEM,
            _context(run)
            + "\n\nStage: understand. Restate intent. List ambiguities as questions. "
            "State the bounded assumptions you will proceed with — especially if the ask is vague "
            "(e.g. 'more reliable' / 'production-ready'). Do not write code. "
            "If workspace already contains a URL shortener, treat this as a change to that system. "
            "Default assumptions when unspecified: http(s) URLs only, sqlite, no auth, no new cloud infra.",
        )
        return _result(True, text)

    def design(run: Run, _stage: StageId) -> StageResult:
        text = get_llm().run(
            SYSTEM,
            _context(run)
            + "\n\nStage: design. Propose the smallest change that satisfies the assumptions. "
            "Name impacted files, API/schema diffs, and tests. Do not write implementation files. "
            "If this is brownfield, say what you will not rewrite.",
        )
        return _result(True, text)

    def implement(run: Run, _stage: StageId) -> StageResult:
        text = get_llm().run(
            SYSTEM,
            _context(run) + "\n\nStage: implement.\n" + IMPLEMENT_SPEC,
            tools=tool_specs(),
            executor=default_executor,
        )
        return _result(True, text)

    def test(run: Run, _stage: StageId) -> StageResult:
        first = run_tests()
        if first.startswith("exit=0"):
            return _result(True, first)
        text = get_llm().run(
            SYSTEM,
            _context(run)
            + "\n\nStage: test. pytest failed. Read the files, fix them with tools, and re-run until exit=0.\n\n"
            + first,
            tools=tool_specs(),
            executor=default_executor,
        )
        final = run_tests()
        ok = final.startswith("exit=0")
        return _result(ok, f"{text}\n\n{final}")

    def docs(run: Run, _stage: StageId) -> StageResult:
        text = get_llm().run(
            SYSTEM,
            _context(run)
            + "\n\nStage: docs. write_file a workspace/README.md covering run instructions, APIs, "
            "and limitations. Then stop.",
            tools=tool_specs(),
            executor=default_executor,
        )
        return _result(True, text)

    return {
        StageId.UNDERSTAND: understand,
        StageId.DESIGN: design,
        StageId.IMPLEMENT: implement,
        StageId.TEST: test,
        StageId.DOCS: docs,
    }
