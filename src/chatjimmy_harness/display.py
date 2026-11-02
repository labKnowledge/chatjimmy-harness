"""Terminal rendering for assistant messages (markdown when the TTY can show it)."""

from __future__ import annotations

import os
from typing import Iterator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown


def markdown_enabled(console: Console) -> bool:
    """Render Markdown in interactive terminals unless explicitly disabled."""
    if os.environ.get("CHATJIMMY_PLAIN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False
    raw = os.environ.get("CHATJIMMY_MARKDOWN", "1").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(console.is_terminal)


def print_assistant(console: Console, text: str) -> None:
    """Print a complete assistant reply (Markdown when enabled)."""
    if not text:
        return
    if markdown_enabled(console):
        console.print(Markdown(text))
    else:
        console.print(text, markup=False, soft_wrap=True)


def stream_assistant(console: Console, chunks: Iterator[str]):
    """
    Consume a token iterator, rendering Markdown live when possible.

    Returns ``(final_text, stop_value)`` where ``stop_value`` is whatever the
    generator returned via ``StopIteration.value`` (e.g. a ChatResponse).
    """
    parts: list[str] = []
    stop_value = None

    if markdown_enabled(console):
        with Live(
            console=console,
            refresh_per_second=12,
            vertical_overflow="visible",
        ) as live:
            try:
                while True:
                    chunk = next(chunks)
                    parts.append(chunk)
                    live.update(Markdown("".join(parts)), refresh=True)
            except StopIteration as stop:
                stop_value = stop.value
                if parts:
                    live.update(Markdown("".join(parts)), refresh=True)
        return "".join(parts), stop_value

    try:
        while True:
            chunk = next(chunks)
            parts.append(chunk)
            console.print(chunk, end="", markup=False, soft_wrap=True)
    except StopIteration as stop:
        stop_value = stop.value
    console.print()
    return "".join(parts), stop_value
