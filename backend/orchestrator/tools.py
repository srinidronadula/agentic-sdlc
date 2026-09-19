from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from orchestrator.paths import workspace_root


class ToolError(ValueError):
    pass


TOOL_SPECS = [
    {
        "name": "write_file",
        "description": "Create or overwrite a UTF-8 text file under workspace/. Path is relative.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file under workspace/. Path is relative.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_tests",
        "description": "Run pytest in workspace/. Returns exit code and output. No arguments.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def safe_path(relative: str) -> Path:
    raw = (relative or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/"):
        raise ToolError("path must be a relative workspace path")
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ToolError("path must stay inside workspace")
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ToolError("path escapes workspace") from exc
    if ".env" in resolved.parts or resolved.suffix == ".pem":
        raise ToolError("refusing to touch secrets")
    return resolved


def write_file(path: str, content: str) -> str:
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {path} ({len(content)} bytes)"


def read_file(path: str) -> str:
    target = safe_path(path)
    if not target.exists():
        raise ToolError(f"not found: {path}")
    return target.read_text(encoding="utf-8")


def run_tests() -> str:
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if len(output) > 8000:
        output = output[-8000:]
    return f"exit={result.returncode}\n{output}"


def execute_tool(name: str, args: dict) -> str:
    if name == "write_file":
        return write_file(str(args.get("path", "")), str(args.get("content", "")))
    if name == "read_file":
        return read_file(str(args.get("path", "")))
    if name == "run_tests":
        return run_tests()
    raise ToolError(f"unknown tool: {name}")
