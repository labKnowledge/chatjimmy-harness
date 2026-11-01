"""Search tools: glob and grep."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".tox", "dist", "build"}


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        yield path


def _glob(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    pattern = str(args.get("pattern", "")).strip()
    if not pattern:
        return ToolResult(False, "missing pattern")
    base = ctx.resolve(str(args.get("path", ".") or "."))
    if not base.exists():
        return ToolResult(False, f"not found: {base.relative_to(ctx.workspace)}")
    matches = []
    for path in sorted(base.glob(pattern)):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            matches.append(str(path.relative_to(ctx.workspace)))
        except ValueError:
            continue
        if len(matches) >= 200:
            matches.append("…[truncated]")
            break
    return ToolResult(True, "\n".join(matches) if matches else "(no matches)")


def _grep(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    pattern = str(args.get("pattern", ""))
    if not pattern:
        return ToolResult(False, "missing pattern")
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return ToolResult(False, f"invalid regex: {exc}")

    base = ctx.resolve(str(args.get("path", ".") or "."))
    if base.is_file():
        files = [base]
    elif base.is_dir():
        files = list(_iter_files(base))
    else:
        return ToolResult(False, f"not found: {base.relative_to(ctx.workspace)}")

    hits: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                rel = path.relative_to(ctx.workspace)
                hits.append(f"{rel}:{i}:{line[:240]}")
                if len(hits) >= 100:
                    hits.append("…[truncated]")
                    return ToolResult(True, "\n".join(hits))
    return ToolResult(True, "\n".join(hits) if hits else "(no matches)")


SPECS = [
    ToolSpec(
        name="glob",
        description="Find files by glob pattern under the workspace (e.g. **/*.py).",
        parameters={
            "pattern": "Glob pattern",
            "path": "Optional subdirectory to search from (default: .)",
        },
        handler=_glob,
    ),
    ToolSpec(
        name="grep",
        description="Search file contents with a Python regex; returns path:line:text.",
        parameters={
            "pattern": "Regex pattern",
            "path": "File or directory to search (default: .)",
        },
        handler=_grep,
    ),
]
