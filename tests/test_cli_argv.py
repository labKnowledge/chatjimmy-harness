import sys

from chatjimmy_harness.cli import _rewrite_bare_prompt_argv


def test_rewrite_inserts_ask(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cj", "What is 2+2?"])
    _rewrite_bare_prompt_argv()
    assert sys.argv == ["cj", "ask", "What is 2+2?"]


def test_rewrite_keeps_known_command(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cj", "health"])
    _rewrite_bare_prompt_argv()
    assert sys.argv == ["cj", "health"]


def test_rewrite_skips_global_flags(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["cj", "--timeout", "30", "--base-url", "https://x", "hello"]
    )
    _rewrite_bare_prompt_argv()
    assert sys.argv == [
        "cj",
        "--timeout",
        "30",
        "--base-url",
        "https://x",
        "ask",
        "hello",
    ]


def test_rewrite_noop_on_help(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cj", "--help"])
    _rewrite_bare_prompt_argv()
    assert sys.argv == ["cj", "--help"]
