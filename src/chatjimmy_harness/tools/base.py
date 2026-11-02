"""Tool primitives — pure data + workspace-safe path helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, str]  # name -> short description
    handler: Callable[["ToolContext", dict[str, Any]], "ToolResult"]


@dataclass
class ToolResult:
    ok: bool
    output: str
    meta: dict[str, Any] = field(default_factory=dict)

    def render(
        self,
        *,
        limit: int = 4_000,
        keep: str = "tail",
    ) -> str:
        from chatjimmy_harness.context import truncate_marked

        status = "ok" if self.ok else "error"
        text = truncate_marked(self.output, limit, keep=keep)
        return f"[{status}]\n{text}"


@dataclass
class ToolContext:
    """Runtime context for tool execution (workspace jail)."""

    workspace: Path
    allow_shell: bool = True
    command_timeout_s: float = 30.0
    max_read_bytes: int = 200_000
    # When runtime_mode is approval-required, mutating tools still run but are logged.
    require_approval: bool = False
    approved_tools: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.workspace = self.workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def resolve(self, rel: str) -> Path:
        """Resolve a path inside the workspace; reject escapes."""
        raw = (rel or "").strip() or "."
        path = Path(raw)
        if not path.is_absolute():
            path = self.workspace / path
        resolved = path.resolve()
        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError(
                f"path escapes workspace: {rel!r} (workspace={self.workspace})"
            ) from exc
        return resolved
