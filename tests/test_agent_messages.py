from pathlib import Path
from unittest.mock import MagicMock

from chatjimmy_harness.agent import AgentResult, run_agent
from chatjimmy_harness.client import ChatResponse, Stats


def test_run_agent_returns_history(tmp_path: Path):
    client = MagicMock()
    client.chat.side_effect = [
        ChatResponse(
            text=(
                "<tool_call>\n<name>list_dir</name>\n"
                '<arg name="path">.</arg>\n</tool_call>'
            ),
            stats=Stats(decode_tokens=1),
        ),
        ChatResponse(text="done listing", stats=Stats(decode_tokens=2)),
    ]

    result = run_agent(
        client,
        "list files",
        workspace=tmp_path,
        tools=["list_dir"],
        max_turns=4,
        allow_shell=False,
    )
    assert isinstance(result, AgentResult)
    assert result.finished
    assert result.text == "done listing"
    assert result.tool_calls == 1
    assert result.messages[0]["role"] == "user"
    assert result.messages[0]["content"] == "list files"
    assert any(m["role"] == "assistant" for m in result.messages)
    assert len(result.messages) >= 3
