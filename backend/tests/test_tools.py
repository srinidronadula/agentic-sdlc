from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.tools import ToolError, read_file, run_tests, safe_path, write_file


def test_write_and_read_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    write_file("hello.txt", "hi")
    assert read_file("hello.txt") == "hi"


def test_rejects_path_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    with pytest.raises(ToolError):
        safe_path("../secret.txt")
    with pytest.raises(ToolError):
        write_file(".env", "KEY=1")


def test_run_tests_reports_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    write_file("test_ok.py", "def test_ok():\n    assert True\n")
    output = run_tests()
    assert output.startswith("exit=0")
