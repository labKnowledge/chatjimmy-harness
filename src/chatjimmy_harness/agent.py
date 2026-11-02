"""Tool-using agent loop on top of ChatJimmy (no native function-calling API)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatjimmy_harness.client import ChatJimmy, Stats
from chatjimmy_harness.config import HarnessConfig, config_from_env
from chatjimmy_harness.context import estimate_chars, select_messages_for_budget
from chatjimmy_harness.instructions import (
    compose_system_prompt,
    continue_after_tool,
    format_repair_nudge,
)
from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec
from chatjimmy_harness.tools.registry import build_registry

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
# Broken / partial tool call signals — trigger a format repair nudge.
_TOOL_ATTEMPT_RE = re.compile(
    r"(<tool_call|</tool_call>|\btool_call\b|\{\"tool\"\s*:)",
    re.IGNORECASE,
)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    raw: str = ""


@dataclass
class AgentStep:
    kind: str  # "assistant" | "tool" | "repair" | "compact"
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
    messages: list[dict[str, str]] = field(default_factory=list)
    compacted: int = 0
    repair_nudges: int = 0
    system_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "finished": self.finished,
            "error": self.error,
            "compacted": self.compacted,
            "repair_nudges": self.repair_nudges,
            "system_prompt": self.system_prompt,
            "messages": self.messages,
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
    calls = parse_tool_calls(text)
    return calls[0] if calls else None


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Extract all well-formed tool calls (XML first, then JSON fallbacks)."""
    found: list[ToolCall] = []
    for m in _TOOL_CALL_RE.finditer(text):
        args = {a.group("key"): a.group("val") for a in _ARG_RE.finditer(m.group("body"))}
        found.append(ToolCall(name=m.group("name").strip(), args=args, raw=m.group(0)))
    if found:
        return found

    for rx in (_JSON_TOOL_RE, _JSON_TOOL_LOOSE_RE):
        for jm in rx.finditer(text):
            try:
                data = json.loads(jm.group(1))
            except json.JSONDecodeError:
                continue
            name = data.get("tool") or data.get("name")
            args = data.get("args") or data.get("arguments") or {}
            if isinstance(name, str) and isinstance(args, dict):
                found.append(ToolCall(name=name, args=args, raw=jm.group(0)))
        if found:
            return found
    return found


def looks_like_tool_attempt(text: str) -> bool:
    """True when the model tried to call a tool but parse_tool_calls found nothing."""
    if parse_tool_calls(text):
        return False
    return bool(_TOOL_ATTEMPT_RE.search(text or ""))


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


OnStep = Callable[[AgentStep], None]


def _execute_tool(
    *,
    registry: dict[str, ToolSpec],
    ctx: ToolContext,
    call: ToolCall,
) -> ToolResult:
    spec = registry.get(call.name)
    if spec is None:
        return ToolResult(
            False,
            f"unknown tool {call.name!r}; choose from: {', '.join(registry)}",
        )
    try:
        return spec.handler(ctx, call.args)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, f"{type(exc).__name__}: {exc}")


def run_agent(
    client: ChatJimmy,
    prompt: str,
    *,
    workspace: Path,
    tools: list[str] | None = None,
    system_prompt: str = "",
    model: str = "llama3.1-8B",
    top_k: int = 8,
    max_turns: int | None = None,
    allow_shell: bool = True,
    command_timeout_s: float = 30.0,
    on_step: OnStep | None = None,
    messages: list[dict[str, str]] | None = None,
    config: HarnessConfig | None = None,
) -> AgentResult:
    """Run a multi-turn tool loop until final answer or max_turns."""
    cfg = config_from_env(config or HarnessConfig())
    turns_cap = max_turns if max_turns is not None else cfg.max_turns

    registry = build_registry(tools, interaction_mode=cfg.interaction_mode)
    if not allow_shell:
        registry = {k: v for k, v in registry.items() if k not in {"run_shell", "run_python"}}

    ctx = ToolContext(
        workspace=workspace,
        allow_shell=allow_shell and cfg.interaction_mode != "plan",
        command_timeout_s=command_timeout_s,
        require_approval=cfg.runtime_mode == "approval-required",
    )
    system = compose_system_prompt(
        registry=registry,
        cfg=cfg,
        user_system=system_prompt,
        workspace=workspace,
    )

    history: list[dict[str, str]] = list(messages) if messages else []
    if prompt:
        history.append({"role": "user", "content": prompt})

    result = AgentResult(text="", finished=False, system_prompt=system)
    final_text = ""
    repair_left = cfg.max_repair_nudges
    empty_retries_left = cfg.empty_response_retries

    turn = 0
    while turn < turns_cap:
        turn += 1
        result.turns = turn

        shaped = select_messages_for_budget(history, system=system, cfg=cfg)
        send_messages = shaped.messages
        if shaped.compacted:
            result.compacted += 1
            compact_step = AgentStep(
                kind="compact",
                text=f"omitted={shaped.omitted} chars≈{shaped.estimated_chars}",
            )
            result.steps.append(compact_step)
            if on_step:
                on_step(compact_step)

        try:
            resp = client.chat(
                messages=send_messages,
                model=model,
                system_prompt=system,
                top_k=top_k,
            )
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            result.messages = history
            return result

        text = (resp.text or "").strip()
        # Empty body often means prefill overflow on chatjimmy — compact harder / retry.
        if not text:
            if empty_retries_left > 0 and len(history) > 2:
                empty_retries_left -= 1
                # Drop oldest non-pinned middle by forcing a stronger compact next loop:
                # remove the oldest assistant+tool pair after the first user message.
                if len(history) > 3:
                    history = [history[0]] + history[3:]
                continue
            result.error = "empty response (likely prefill overflow or backend blip)"
            result.messages = history
            result.text = ""
            return result

        final_text = text
        calls = parse_tool_calls(text)

        assistant_step = AgentStep(
            kind="assistant",
            text=text,
            stats=_stats_dict(resp.stats),
        )
        result.steps.append(assistant_step)
        if on_step:
            on_step(assistant_step)

        history.append({"role": "assistant", "content": text})

        if not calls:
            if looks_like_tool_attempt(text) and repair_left > 0:
                repair_left -= 1
                result.repair_nudges += 1
                nudge = format_repair_nudge(registry)
                repair_step = AgentStep(kind="repair", text=nudge)
                result.steps.append(repair_step)
                if on_step:
                    on_step(repair_step)
                history.append({"role": "user", "content": nudge})
                continue

            result.finished = True
            result.text = text
            result.messages = history
            return result

        # Execute each parsed call sequentially (usually one; tolerate multiples).
        for call in calls:
            result.tool_calls += 1
            tool_result = _execute_tool(registry=registry, ctx=ctx, call=call)
            rendered = tool_result.render(
                limit=cfg.tool_result_limit,
                keep=cfg.tool_result_keep,
            )
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
                    "content": continue_after_tool(call.name, rendered),
                }
            )

        # Prefill telemetry: if last stats show near the ceiling, mark for next compact.
        if resp.stats and resp.stats.prefill_tokens:
            # Soft warn into history only when dangerously high — compact handles it.
            _ = estimate_chars(history, system)

    result.text = final_text
    result.error = f"stopped after max_turns={turns_cap}"
    result.messages = history
    return result
