"""Shell and Python execution tools (workspace-scoped)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Any

from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec


def _run_shell(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if not ctx.allow_shell:
        return ToolResult(False, "shell tools disabled")
    command = str(args.get("command", "")).strip()
    if not command:
        return ToolResult(False, "missing command")
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(ctx.workspace),
            capture_output=True,
            text=True,
            timeout=ctx.command_timeout_s,
            env={**os.environ, "PWD": str(ctx.workspace)},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"timed out after {ctx.command_timeout_s}s")
    except OSError as exc:
        return ToolResult(False, str(exc))

    out = []
    if proc.stdout:
        out.append(proc.stdout.rstrip())
    if proc.stderr:
        out.append(("stderr:\n" + proc.stderr.rstrip()) if proc.stdout else proc.stderr.rstrip())
    body = "\n".join(out) if out else "(no output)"
    ok = proc.returncode == 0
    return ToolResult(
        ok,
        f"exit {proc.returncode}\n{body}",
        {"exit_code": proc.returncode},
    )


def _run_python(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if not ctx.allow_shell:
        return ToolResult(False, "exec tools disabled")
    code = args.get("code")
    if code is None:
        return ToolResult(False, "missing code")
    code_s = str(code)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".py",
        dir=ctx.workspace,
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(code_s)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            cwd=str(ctx.workspace),
            capture_output=True,
            text=True,
            timeout=ctx.command_timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"timed out after {ctx.command_timeout_s}s")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    out = []
    if proc.stdout:
        out.append(proc.stdout.rstrip())
    if proc.stderr:
        out.append(("stderr:\n" + proc.stderr.rstrip()) if proc.stdout else proc.stderr.rstrip())
    body = "\n".join(out) if out else "(no output)"
    return ToolResult(
        proc.returncode == 0,
        f"exit {proc.returncode}\n{body}",
        {"exit_code": proc.returncode},
    )


SPECS = [
    ToolSpec(
        name="run_shell",
        description=(
            "Run a shell command with cwd=workspace. Use for tests, git, compilers. "
            "Prefer run_python for short Python snippets."
        ),
        parameters={"command": "Shell command string"},
        handler=_run_shell,
    ),
    ToolSpec(
        name="run_python",
        description="Execute a Python code string inside the workspace (temporary file).",
        parameters={"code": "Python source to run"},
        handler=_run_python,
    ),
]
