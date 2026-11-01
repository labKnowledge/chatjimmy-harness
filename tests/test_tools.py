from pathlib import Path

import pytest

from chatjimmy_harness.agent import parse_tool_call
from chatjimmy_harness.tools.base import ToolContext
from chatjimmy_harness.tools.registry import build_registry


def test_parse_xml_tool_call():
    text = """
I'll look at the file.
<tool_call>
<name>read_file</name>
<arg name="path">src/app.py</arg>
</tool_call>
"""
    call = parse_tool_call(text)
    assert call is not None
    assert call.name == "read_file"
    assert call.args["path"] == "src/app.py"


def test_parse_json_tool_call():
    text = '```json\n{"tool": "grep", "args": {"pattern": "TODO", "path": "."}}\n```'
    call = parse_tool_call(text)
    assert call is not None
    assert call.name == "grep"
    assert call.args["pattern"] == "TODO"


def test_workspace_jail(tmp_path: Path):
    ctx = ToolContext(workspace=tmp_path)
    inside = ctx.resolve("ok.txt")
    assert inside == (tmp_path / "ok.txt").resolve()
    with pytest.raises(PermissionError):
        ctx.resolve("../escape.txt")


def test_fs_roundtrip(tmp_path: Path):
    reg = build_registry(["write_file", "read_file", "list_dir", "str_replace"])
    ctx = ToolContext(workspace=tmp_path)
    w = reg["write_file"].handler(ctx, {"path": "a.txt", "content": "hello world"})
    assert w.ok
    r = reg["read_file"].handler(ctx, {"path": "a.txt"})
    assert r.ok and r.output == "hello world"
    s = reg["str_replace"].handler(
        ctx, {"path": "a.txt", "old": "world", "new": "jimmy"}
    )
    assert s.ok
    assert reg["read_file"].handler(ctx, {"path": "a.txt"}).output == "hello jimmy"
    listing = reg["list_dir"].handler(ctx, {"path": "."})
    assert "a.txt" in listing.output


def test_run_python(tmp_path: Path):
    reg = build_registry(["run_python"])
    ctx = ToolContext(workspace=tmp_path)
    res = reg["run_python"].handler(ctx, {"code": "print(2 + 2)"})
    assert res.ok
    assert "4" in res.output
