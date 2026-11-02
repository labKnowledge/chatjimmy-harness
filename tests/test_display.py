from rich.console import Console

from chatjimmy_harness.display import markdown_enabled, print_assistant, stream_assistant


def test_markdown_enabled_respects_plain_env(monkeypatch):
    console = Console(force_terminal=True)
    monkeypatch.delenv("CHATJIMMY_PLAIN", raising=False)
    monkeypatch.delenv("CHATJIMMY_MARKDOWN", raising=False)
    assert markdown_enabled(console) is True

    monkeypatch.setenv("CHATJIMMY_PLAIN", "1")
    assert markdown_enabled(console) is False


def test_markdown_enabled_respects_markdown_off(monkeypatch):
    console = Console(force_terminal=True)
    monkeypatch.delenv("CHATJIMMY_PLAIN", raising=False)
    monkeypatch.setenv("CHATJIMMY_MARKDOWN", "0")
    assert markdown_enabled(console) is False


def test_markdown_disabled_when_not_tty(monkeypatch):
    console = Console(force_terminal=False)
    monkeypatch.delenv("CHATJIMMY_PLAIN", raising=False)
    monkeypatch.delenv("CHATJIMMY_MARKDOWN", raising=False)
    assert markdown_enabled(console) is False


def test_print_assistant_renders_heading(monkeypatch):
    monkeypatch.delenv("CHATJIMMY_PLAIN", raising=False)
    monkeypatch.delenv("CHATJIMMY_MARKDOWN", raising=False)
    console = Console(force_terminal=True, width=80, record=True)
    print_assistant(console, "# Hello\n\n- one\n- two")
    text = console.export_text()
    assert "Hello" in text
    assert "one" in text
    # Raw markdown markers should not appear as the primary heading form
    assert "# Hello" not in text


def test_print_assistant_plain_when_disabled(monkeypatch):
    monkeypatch.setenv("CHATJIMMY_PLAIN", "1")
    console = Console(force_terminal=True, width=80, record=True)
    print_assistant(console, "# Hello\n\n- one")
    text = console.export_text()
    assert "# Hello" in text


def test_stream_assistant_plain_concatenates(monkeypatch):
    monkeypatch.setenv("CHATJIMMY_PLAIN", "1")
    console = Console(force_terminal=True, width=80, record=True)

    def gen():
        yield "# Hi"
        yield " there"
        return "done-marker"

    text, stop = stream_assistant(console, gen())
    assert text == "# Hi there"
    assert stop == "done-marker"
    assert "# Hi there" in console.export_text()
