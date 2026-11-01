"""Tool-using agent loop on top of ChatJimmy (no native function-calling API)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatjimmy_harness.client import ChatJimmy, Stats
from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec
from chatjimmy_harness.tools.registry import build_registry, tool_specs_prompt

# XML tool call — primary format we instruct the model to use.
_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<name>\s*(?P<name>[a-zA-Z0-9_]+)\s*</name>\s*"
    r"(?P<body>.*?)\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)
_ARG_RE = re.compile(
    r"<arg\s+name=\"(?P<key>[^\"]+)\"\s*>(?P<val>.*?)</arg>",
    re.DOTALL | re.IGNORECASE,
)
# Fallback: fenced JSON {"tool": "...", "args": {...}}
_JSON_TOOL_RE = re.compile(
    r"```(?:json)?\s*(\{\s*\"tool\"\s*:.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)
_JSON_TOOL_LOOSE_RE = re.compile(
    r"(\{\s*\"tool\"\s*:\s*\"[a-zA-Z0-9_]+\"\s*,\s*\"args\"\s*:\s*\{.*?\}\s*\})",
    re.DOTALL,
)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    raw: str = ""


@dataclass
class AgentStep:
    kind: str  # "assistant" | "tool"
    text: str = ""
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    ok: bool | None = None
    stats: dict[str, Any] | None = None


@dataclass
class AgentResult:
    text: str
    steps: list[AgentStep] = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0
    finished: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "finished": self.finished,
            "error": self.error,
            "steps": [
                {
                    "kind": s.kind,
                    "text": s.text,
                    "tool": s.tool,
                    "args": s.args,
                    "result": s.result,
                    "ok": s.ok,
                    "stats": s.stats,
                }
                for s in self.steps
            ],
        }


def parse_tool_call(text: str) -> ToolCall | None:
    """Extract the first tool call from model text, if any."""
    m = _TOOL_CALL_RE.search(text)
    if m:
        args = {a.group("key"): a.group("val") for a in _ARG_RE.finditer(m.group("body"))}
        return ToolCall(name=m.group("name").strip(), args=args, raw=m.group(0))

    for rx in (_JSON_TOOL_RE, _JSON_TOOL_LOOSE_RE):
        jm = rx.search(text)
        if not jm:
            continue
        try:
            data = json.loads(jm.group(1))
        except json.JSONDecodeError:
            continue
        name = data.get("tool") or data.get("name")
        args = data.get("args") or data.get("arguments") or {}
        if isinstance(name, str) and isinstance(args, dict):
            return ToolCall(name=name, args=args, raw=jm.group(0))
    return None


def _stats_dict(stats: Stats | None) -> dict[str, Any] | None:
    if stats is None:
        return None
    return {
        "prefill_tokens": stats.prefill_tokens,
        "prefill_rate": stats.prefill_rate,
        "decode_tokens": stats.decode_tokens,
        "decode_rate": stats.decode_rate,
        "ttft": stats.ttft,
        "total_time": stats.total_time,
        "roundtrip_time": stats.roundtrip_time,
        "done_reason": stats.done_reason,
    }


def _compose_system(user_system: str, registry: dict[str, ToolSpec]) -> str:
    parts = [tool_specs_prompt(registry)]
    if user_system.strip():
        parts.append(user_system.strip())
    return "\n\n".join(parts)


OnStep = Callable[[AgentStep], None]


def run_agent(
    client: ChatJimmy,
    prompt: str,
    *,
    workspace: Path,
    tools: list[str] | None = None,
    system_prompt: str = "",
    model: str = "llama3.1-8B",
    top_k: int = 8,
    max_turns: int = 8,
    allow_shell: bool = True,
    command_timeout_s: float = 30.0,
    on_step: OnStep | None = None,
    messages: list[dict[str, str]] | None = None,
) -> AgentResult:
    """Run a multi-turn tool loop until final answer or max_turns."""
    registry = build_registry(tools)
    ctx = ToolContext(
        workspace=workspace,
        allow_shell=allow_shell,
        command_timeout_s=command_timeout_s,
    )
    system = _compose_system(system_prompt, registry)

    history: list[dict[str, str]] = list(messages) if messages else []
    if prompt:
        history.append({"role": "user", "content": prompt})

    result = AgentResult(text="", finished=False)
    final_text = ""

    for turn in range(1, max_turns + 1):
        result.turns = turn
        try:
            resp = client.chat(
                messages=history,
                model=model,
                system_prompt=system,
                top_k=top_k,
            )
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            return result

        text = (resp.text or "").strip()
        final_text = text
        call = parse_tool_call(text)

        assistant_step = AgentStep(
            kind="assistant",
            text=text,
            stats=_stats_dict(resp.stats),
        )
        result.steps.append(assistant_step)
        if on_step:
            on_step(assistant_step)

        history.append({"role": "assistant", "content": text})

        if call is None:
            result.finished = True
            result.text = text
            return result

        result.tool_calls += 1
        spec = registry.get(call.name)
        if spec is None:
            tool_result = ToolResult(
                False,
                f"unknown tool {call.name!r}; choose from: {', '.join(registry)}",
            )
        else:
            try:
                tool_result = spec.handler(ctx, call.args)
            except Exception as exc:  # noqa: BLE001
                tool_result = ToolResult(False, f"{type(exc).__name__}: {exc}")

        rendered = tool_result.render()
        tool_step = AgentStep(
            kind="tool",
            tool=call.name,
            args=call.args,
            result=rendered,
            ok=tool_result.ok,
        )
        result.steps.append(tool_step)
        if on_step:
            on_step(tool_step)

        history.append(
            {
                "role": "user",
                "content": (
                    f"Tool result for {call.name}:\n{rendered}\n\n"
                    "Continue. Either call another tool with <tool_call>…</tool_call> "
                    "or give the final answer without a tool call."
                ),
            }
        )

    result.text = final_text
    result.error = f"stopped after max_turns={max_turns}"
    return result
