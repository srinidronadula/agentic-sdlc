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

IMPLEMENT_SPEC = """Build a tiny URL shortener in workspace/ using FastAPI (already installed).

Must include:
- POST /shorten  JSON {"url": "https://example.com"} -> {"code": "<short>"}
- GET /{code}    302 redirect to the original URL
- GET /stats/{code}  JSON {"url": "...", "clicks": N}
- sqlite persistence (urls.db) so clicks survive process restart
- pytest tests using fastapi.TestClient covering shorten, redirect, click count, and 404

Use only tools write_file, read_file, run_tests.
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
            + "\n\nStage: understand. Restate intent, list ambiguities, and state assumptions. "
            "Do not write code. If the ask is a URL shortener, assume: random codes, http(s) URLs only, "
            "in-process sqlite, no auth.",
        )
        return _result(True, text)

    def design(run: Run, _stage: StageId) -> StageResult:
        text = get_llm().run(
            SYSTEM,
            _context(run)
            + "\n\nStage: design. Propose modules, API contracts, sqlite schema, and a test plan. "
            "Do not write implementation files.",
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
