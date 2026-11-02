"""Budgeted, versioned instruction sections for the agent system prompt.

Keep each section self-contained and under a char budget; compose only what
the current mode and tool set need; wrap harness text separately from user extras.
"""

from __future__ import annotations

from pathlib import Path

from chatjimmy_harness.config import HarnessConfig, InteractionMode
from chatjimmy_harness.tools.base import ToolSpec

INSTRUCTION_VERSION = "cj-harness-1"

_CORE_RULES = """## Harness rules
- Prefer tools over guessing file contents or command output.
- Emit ONE tool call, then stop and wait for the result.
- Use this exact XML form (no markdown fences around it):
<tool_call>
<name>TOOL_NAME</name>
<arg name="ARG">value</arg>
</tool_call>
- Paths are relative to the workspace root.
- When finished, give a clear final answer with NO tool_call.
- If a tool errors, fix the args or try another tool — do not invent results."""

_ACT_MODE = """## Mode: act
Carry out the task. Make reasonable assumptions. Ask only when a missing
decision would materially change the result. Prefer small, verifiable steps."""

_PLAN_MODE = """## Mode: plan
Investigate with read-only tools only. Do not edit files or run shell/python.
When requirements are clear, return a concrete implementation plan and stop.
Do not start implementing."""

_FORMAT_REMINDER = (
    "Reminder: emit exactly one <tool_call><name>…</name>"
    '<arg name="…">…</arg></tool_call> or a final answer with no tool_call.'
)


def _clip(text: str, limit: int, *, label: str = "section") -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    keep = max(0, limit - 32)
    return text[:keep] + f"\n…[truncated {label} {len(text) - keep} chars]"


def load_workspace_instructions(
    workspace: Path,
    cfg: HarnessConfig,
) -> str | None:
    """Load the first present instruction file under the workspace (AGENTS.md etc.)."""
    if not cfg.load_workspace_instructions:
        return None
    root = workspace.resolve()
    for name in cfg.instruction_file_names:
        path = root / name
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        body = _clip(raw, cfg.max_workspace_instruction_chars, label=name)
        return f"## Workspace instructions ({name})\n{body}"
    return None


def tool_catalog(registry: dict[str, ToolSpec], *, budget_chars: int) -> str:
    """Compact tool list sized for small-model prefill."""
    lines = ["## Available tools"]
    for spec in registry.values():
        params = ", ".join(f"{k}" for k in spec.parameters)
        entry = f"- {spec.name}({params}): {spec.description}"
        lines.append(entry)
    text = "\n".join(lines)
    return _clip(text, budget_chars, label="tools")


def mode_section(mode: InteractionMode) -> str:
    return _PLAN_MODE if mode == "plan" else _ACT_MODE


def compose_system_prompt(
    *,
    registry: dict[str, ToolSpec],
    cfg: HarnessConfig,
    user_system: str = "",
    workspace: Path | None = None,
) -> str:
    """Build a budgeted system prompt from ordered sections."""
    budget = cfg.system_budget_chars
    sections: list[str] = [
        f"<!-- {INSTRUCTION_VERSION} -->",
        _CORE_RULES,
        mode_section(cfg.interaction_mode),
    ]

    remaining = budget - sum(len(s) + 2 for s in sections)
    # Reserve a slice for workspace + user extras.
    extras_reserve = min(1_200, max(400, remaining // 3))
    tool_budget = max(400, remaining - extras_reserve)
    sections.append(tool_catalog(registry, budget_chars=tool_budget))

    used = sum(len(s) + 2 for s in sections)
    left = max(0, budget - used)

    if workspace is not None and left > 80:
        ws = load_workspace_instructions(workspace, cfg)
        if ws:
            chunk = _clip(ws, min(left, cfg.max_workspace_instruction_chars), label="ws")
            sections.append(chunk)
            left -= len(chunk) + 2

    if user_system.strip() and left > 40:
        sections.append(
            "## Extra system\n"
            + _clip(user_system.strip(), left - 20, label="user-system")
        )

    body = "\n\n".join(sections)
    if len(body) > budget:
        body = _clip(body, budget, label="system")
    return body


def format_repair_nudge(registry: dict[str, ToolSpec]) -> str:
    names = ", ".join(registry)
    return (
        "Your previous reply looked like a tool call but could not be parsed. "
        f"{_FORMAT_REMINDER} Tools: {names}"
    )


def continue_after_tool(tool_name: str, rendered: str) -> str:
    return (
        f"Tool result for {tool_name}:\n{rendered}\n\n"
        "Continue. Either call another tool with <tool_call>…</tool_call> "
        "or give the final answer without a tool call."
    )


def format_reminder_message() -> str:
    return _FORMAT_REMINDER
