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

    def render(self, *, limit: int = 12_000) -> str:
        status = "ok" if self.ok else "error"
        text = self.output if len(self.output) <= limit else (
            self.output[:limit] + f"\n…[truncated {len(self.output) - limit} chars]"
        )
        return f"[{status}]\n{text}"


@dataclass
class ToolContext:
    """Runtime context for tool execution (workspace jail)."""

    workspace: Path
    allow_shell: bool = True
    command_timeout_s: float = 30.0
    max_read_bytes: int = 200_000

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
