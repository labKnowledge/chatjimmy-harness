"""In-place edit tool."""

from __future__ import annotations

from typing import Any

from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec


def _str_replace(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = ctx.resolve(str(args.get("path", "")))
    old = args.get("old")
    new = args.get("new")
    if old is None or new is None:
        return ToolResult(False, "need args: old, new")
    old_s, new_s = str(old), str(new)
    if not path.exists() or not path.is_file():
        return ToolResult(False, f"file not found: {path.relative_to(ctx.workspace)}")
    text = path.read_text(encoding="utf-8")
    count = text.count(old_s)
    if count == 0:
        return ToolResult(False, "old string not found in file")
    replace_all = str(args.get("replace_all", "")).lower() in {"1", "true", "yes"}
    if count > 1 and not replace_all:
        return ToolResult(
            False,
            f"old string found {count} times; pass replace_all=true or make old unique",
        )
    updated = text.replace(old_s, new_s) if replace_all else text.replace(old_s, new_s, 1)
    path.write_text(updated, encoding="utf-8")
    rel = path.relative_to(ctx.workspace)
    return ToolResult(
        True,
        f"updated {rel} ({count if replace_all else 1} replacement(s))",
        {"path": str(rel), "replacements": count if replace_all else 1},
    )


SPECS = [
    ToolSpec(
        name="str_replace",
        description=(
            "Replace an exact substring in a file. Prefer unique `old` snippets. "
            "Set replace_all=true to replace every occurrence."
        ),
        parameters={
            "path": "File path",
            "old": "Exact text to find",
            "new": "Replacement text",
            "replace_all": "Optional: true to replace all matches",
        },
        handler=_str_replace,
    ),
]
