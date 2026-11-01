"""Filesystem tools: read, write, list, mkdir, delete."""

from __future__ import annotations

from typing import Any

from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec


def _read_file(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = ctx.resolve(str(args.get("path", "")))
    if not path.exists():
        return ToolResult(False, f"not found: {path.relative_to(ctx.workspace)}")
    if path.is_dir():
        return ToolResult(False, f"is a directory: {path.relative_to(ctx.workspace)}")
    data = path.read_bytes()
    if len(data) > ctx.max_read_bytes:
        return ToolResult(
            False,
            f"file too large ({len(data)} bytes); max {ctx.max_read_bytes}",
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    rel = path.relative_to(ctx.workspace)
    return ToolResult(True, text, {"path": str(rel), "bytes": len(data)})


def _write_file(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = ctx.resolve(str(args.get("path", "")))
    if "content" not in args:
        return ToolResult(False, "missing required arg: content")
    content = str(args.get("content", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    rel = path.relative_to(ctx.workspace)
    return ToolResult(True, f"wrote {rel} ({len(content)} chars)", {"path": str(rel)})


def _list_dir(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = ctx.resolve(str(args.get("path", ".") or "."))
    if not path.exists():
        return ToolResult(False, f"not found: {path.relative_to(ctx.workspace)}")
    if not path.is_dir():
        return ToolResult(False, f"not a directory: {path.relative_to(ctx.workspace)}")
    entries = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        kind = "dir" if child.is_dir() else "file"
        rel = child.relative_to(ctx.workspace)
        entries.append(f"{kind}\t{rel}")
    return ToolResult(True, "\n".join(entries) if entries else "(empty)")


def _mkdir(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = ctx.resolve(str(args.get("path", "")))
    path.mkdir(parents=True, exist_ok=True)
    return ToolResult(True, f"ensured dir {path.relative_to(ctx.workspace)}")


def _delete_path(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = ctx.resolve(str(args.get("path", "")))
    if path == ctx.workspace:
        return ToolResult(False, "refusing to delete workspace root")
    if not path.exists():
        return ToolResult(False, f"not found: {path.relative_to(ctx.workspace)}")
    if path.is_dir():
        # only empty dirs for safety
        try:
            path.rmdir()
        except OSError as exc:
            return ToolResult(False, f"cannot remove dir (must be empty): {exc}")
    else:
        path.unlink()
    return ToolResult(True, f"deleted {path.relative_to(ctx.workspace)}")


SPECS = [
    ToolSpec(
        name="read_file",
        description="Read a UTF-8 text file inside the workspace.",
        parameters={"path": "Relative path to the file"},
        handler=_read_file,
    ),
    ToolSpec(
        name="write_file",
        description="Create or overwrite a text file inside the workspace.",
        parameters={
            "path": "Relative path to write",
            "content": "Full file contents",
        },
        handler=_write_file,
    ),
    ToolSpec(
        name="list_dir",
        description="List files and directories under a workspace path.",
        parameters={"path": "Directory path (default: .)"},
        handler=_list_dir,
    ),
    ToolSpec(
        name="mkdir",
        description="Create a directory (and parents) inside the workspace.",
        parameters={"path": "Directory path to create"},
        handler=_mkdir,
    ),
    ToolSpec(
        name="delete_path",
        description="Delete a file or empty directory inside the workspace.",
        parameters={"path": "Path to delete"},
        handler=_delete_path,
    ),
]
