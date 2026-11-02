"""Assemble the default tool registry."""

from __future__ import annotations

from chatjimmy_harness.config import PLAN_BLOCKED_TOOLS, InteractionMode
from chatjimmy_harness.tools.base import ToolSpec
from chatjimmy_harness.tools.edit_tools import SPECS as EDIT_SPECS
from chatjimmy_harness.tools.exec_tools import SPECS as EXEC_SPECS
from chatjimmy_harness.tools.fs_tools import SPECS as FS_SPECS
from chatjimmy_harness.tools.search_tools import SPECS as SEARCH_SPECS

_ALL: dict[str, ToolSpec] = {
    spec.name: spec
    for group in (FS_SPECS, EDIT_SPECS, SEARCH_SPECS, EXEC_SPECS)
    for spec in group
}

DEFAULT_TOOL_NAMES = tuple(_ALL.keys())


def build_registry(
    names: list[str] | tuple[str, ...] | None = None,
    *,
    interaction_mode: InteractionMode = "act",
) -> dict[str, ToolSpec]:
    selected = list(names) if names else list(DEFAULT_TOOL_NAMES)
    missing = [n for n in selected if n not in _ALL]
    if missing:
        raise KeyError(f"unknown tools: {', '.join(missing)}")
    if interaction_mode == "plan":
        selected = [n for n in selected if n not in PLAN_BLOCKED_TOOLS]
    return {n: _ALL[n] for n in selected}


def tool_specs_prompt(registry: dict[str, ToolSpec]) -> str:
    """Human-readable tool listing (REPL /tools). Prefer instructions.compose for the model."""
    lines = [
        "You can use tools to inspect and change the local workspace.",
        "When you need a tool, emit ONE tool call in this exact XML form and stop:",
        "",
        "<tool_call>",
        "<name>TOOL_NAME</name>",
        '<arg name="ARG">value</arg>',
        "</tool_call>",
        "",
        "Rules:",
        "- Prefer tools over guessing file contents.",
        "- After a tool result, continue solving the task.",
        "- When finished, respond with a clear final answer and NO tool_call.",
        "- Paths are relative to the workspace root.",
        "",
        "Available tools:",
    ]
    for spec in registry.values():
        params = ", ".join(f"{k}: {v}" for k, v in spec.parameters.items())
        lines.append(f"- {spec.name}({params})")
        lines.append(f"  {spec.description}")
    return "\n".join(lines)
