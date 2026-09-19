from __future__ import annotations

import os
from typing import Any, Callable

import anthropic

from orchestrator.tools import TOOL_SPECS, execute_tool

Executor = Callable[[str, dict[str, Any]], str]


class LLMError(RuntimeError):
    pass


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = (api_key or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.model = (model or os.environ.get("ANTHROPIC_MODEL") or "claude-haiku-4-5").strip()
        self._client = anthropic.Anthropic(api_key=key)

    def run(
        self,
        system: str,
        user: str,
        *,
        tools: list[dict] | None = None,
        executor: Executor | None = None,
        max_rounds: int = 24,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        tool_list = tools or []
        texts: list[str] = []
        for _ in range(max_rounds):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": 8192,
                "system": system,
                "messages": messages,
            }
            if tool_list:
                kwargs["tools"] = tool_list
            response = self._client.messages.create(**kwargs)
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "tool_use":
                if executor is None:
                    raise LLMError("model requested tools but no executor was provided")
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    try:
                        output = executor(block.name, dict(block.input or {}))
                    except Exception as exc:  # noqa: BLE001 — tool failure is returned to the model
                        output = f"ERROR: {exc}"
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(output)[:12000],
                        }
                    )
                messages.append({"role": "user", "content": results})
                continue
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    texts.append(block.text)
            return "\n".join(texts).strip() or "completed"
        raise LLMError("tool loop exceeded max rounds")


def default_executor(name: str, args: dict[str, Any]) -> str:
    return execute_tool(name, args)


def tool_specs() -> list[dict]:
    return TOOL_SPECS
