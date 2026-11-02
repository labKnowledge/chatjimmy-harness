from pathlib import Path
from unittest.mock import MagicMock

from chatjimmy_harness.agent import run_agent
from chatjimmy_harness.client import ChatResponse, Stats
from chatjimmy_harness.config import HarnessConfig


def test_repair_nudge_then_finish(tmp_path: Path):
    client = MagicMock()
    client.chat.side_effect = [
        ChatResponse(text="<tool_call><name>list_dir", stats=Stats(decode_tokens=1)),
        ChatResponse(text="listed nothing useful", stats=Stats(decode_tokens=2)),
    ]
    result = run_agent(
        client,
        "list files",
        workspace=tmp_path,
        tools=["list_dir"],
        allow_shell=False,
        config=HarnessConfig(max_turns=4, max_repair_nudges=2, load_workspace_instructions=False),
    )
    assert result.repair_nudges == 1
    assert result.finished
    assert result.text == "listed nothing useful"
    assert any(s.kind == "repair" for s in result.steps)


def test_empty_response_compacts_history(tmp_path: Path):
    client = MagicMock()
    client.chat.side_effect = [
        ChatResponse(text="", stats=None),
        ChatResponse(text="recovered", stats=Stats(decode_tokens=3)),
    ]
    # Seed history long enough that empty-retry trims it.
    prior = [
        {"role": "user", "content": "start"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "tool dump"},
        {"role": "assistant", "content": "a2"},
    ]
    result = run_agent(
        client,
        "",
        workspace=tmp_path,
        tools=["list_dir"],
        allow_shell=False,
        messages=prior,
        config=HarnessConfig(
            max_turns=4,
            empty_response_retries=1,
            load_workspace_instructions=False,
        ),
    )
    assert result.finished
    assert result.text == "recovered"
    assert client.chat.call_count == 2
