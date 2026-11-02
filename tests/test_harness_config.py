from pathlib import Path

from chatjimmy_harness.agent import looks_like_tool_attempt, parse_tool_calls
from chatjimmy_harness.config import HarnessConfig, PLAN_BLOCKED_TOOLS
from chatjimmy_harness.context import select_messages_for_budget, truncate_marked
from chatjimmy_harness.instructions import compose_system_prompt, load_workspace_instructions
from chatjimmy_harness.tools.registry import build_registry


def test_truncate_marked_tail_keeps_end():
    text = "AAAA" + ("B" * 100) + "END"
    out = truncate_marked(text, 40, keep="tail")
    assert "END" in out
    assert "[truncated" in out


def test_truncate_marked_head_keeps_start():
    text = "START" + ("X" * 100)
    out = truncate_marked(text, 40, keep="head")
    assert out.startswith("START")
    assert "[truncated" in out


def test_select_messages_compacts_and_marks():
    cfg = HarnessConfig(
        max_prefill_tokens=100,
        chars_per_token=4.0,
        history_reserve_chars=0,
        system_budget_chars=200,
        compact_tool_preview_chars=80,
    )
    system = "sys" * 20
    messages = [{"role": "user", "content": "task zero " + ("a" * 200)}]
    for i in range(12):
        messages.append({"role": "assistant", "content": f"step {i} " + ("b" * 80)})
        messages.append(
            {"role": "user", "content": f"Tool result for t{i}:\n" + ("c" * 200)}
        )
    shaped = select_messages_for_budget(messages, system=system, cfg=cfg)
    assert shaped.compacted
    assert shaped.omitted > 0
    blob = " ".join(m["content"] for m in shaped.messages)
    assert "omitted" in blob or "[truncated]" in blob


def test_plan_mode_filters_mutating_tools():
    reg = build_registry(interaction_mode="plan")
    assert "read_file" in reg
    assert "grep" in reg
    for name in PLAN_BLOCKED_TOOLS:
        assert name not in reg


def test_compose_system_stays_under_budget(tmp_path: Path):
    cfg = HarnessConfig(system_budget_chars=2_500)
    reg = build_registry()
    (tmp_path / "AGENTS.md").write_text("# Agent rules\n" + ("keep short. " * 400), encoding="utf-8")
    prompt = compose_system_prompt(
        registry=reg,
        cfg=cfg,
        user_system="extra " * 200,
        workspace=tmp_path,
    )
    assert len(prompt) <= cfg.system_budget_chars
    assert "Harness rules" in prompt
    assert "AGENTS.md" in prompt or "Workspace instructions" in prompt


def test_load_workspace_instructions_prefers_agents_md(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("prefer this", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("not this", encoding="utf-8")
    text = load_workspace_instructions(tmp_path, HarnessConfig())
    assert text is not None
    assert "prefer this" in text


def test_parse_multiple_xml_tool_calls():
    text = """
<tool_call>
<name>list_dir</name>
<arg name="path">.</arg>
</tool_call>
then
<tool_call>
<name>read_file</name>
<arg name="path">a.txt</arg>
</tool_call>
"""
    calls = parse_tool_calls(text)
    assert [c.name for c in calls] == ["list_dir", "read_file"]


def test_looks_like_tool_attempt():
    assert looks_like_tool_attempt("<tool_call><name>broken")
    assert not looks_like_tool_attempt("just a normal answer")
    good = (
        "<tool_call>\n<name>list_dir</name>\n"
        '<arg name="path">.</arg>\n</tool_call>'
    )
    assert not looks_like_tool_attempt(good)
