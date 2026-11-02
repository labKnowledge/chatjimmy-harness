"""Prefill-aware message shaping: pin anchors, fill newest-first, mark truncation.

Never silently clip — always leave a marker so the model knows history was omitted.
"""

from __future__ import annotations

from dataclasses import dataclass

from chatjimmy_harness.config import HarnessConfig
from chatjimmy_harness.instructions import format_reminder_message


@dataclass
class CompactResult:
    messages: list[dict[str, str]]
    omitted: int
    compacted: bool
    estimated_chars: int


def estimate_chars(messages: list[dict[str, str]], system: str = "") -> int:
    total = len(system)
    for m in messages:
        total += len(m.get("role", "")) + len(m.get("content", "")) + 8
    return total


def estimate_tokens(chars: int, cfg: HarnessConfig) -> int:
    return max(1, int(chars / cfg.chars_per_token))


def _compact_content(content: str, limit: int) -> str:
    text = " ".join(content.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 14)] + "…[truncated]"


def select_messages_for_budget(
    messages: list[dict[str, str]],
    *,
    system: str,
    cfg: HarnessConfig,
) -> CompactResult:
    """Pin first user + newest messages until the char budget is filled.

    Older middle messages are dropped with an explicit omission marker.
    Oversized kept messages are aggressively compacted (tool dumps).
    """
    budget = cfg.prefill_char_budget() - cfg.history_reserve_chars
    system_cost = len(system) + 16
    available = max(256, budget - system_cost)

    if not messages:
        return CompactResult([], 0, False, system_cost)

    raw_total = estimate_chars(messages, system)
    if raw_total <= budget:
        return CompactResult(list(messages), 0, False, raw_total)

    # Pin first user message when present.
    pinned: list[dict[str, str]] = []
    rest = list(messages)
    if rest and rest[0].get("role") == "user":
        pinned.append(rest.pop(0))

    preview = cfg.compact_tool_preview_chars

    def _fit(msg: dict[str, str], room: int) -> dict[str, str] | None:
        content = msg.get("content", "")
        role = msg.get("role", "user")
        overhead = len(role) + 8
        if room <= overhead + 32:
            return None
        limit = room - overhead
        # Tool-result user messages and long assistant traces compact hard.
        if len(content) > limit:
            content = _compact_content(content, min(limit, max(preview, limit)))
        return {"role": role, "content": content}

    # Fill newest-first into remaining budget after pinned.
    selected_rev: list[dict[str, str]] = []
    used = 0
    for msg in pinned:
        fitted = _fit(msg, available - used)
        if fitted is None:
            break
        selected_rev.append(fitted)  # will reorder: pinned stay first
        used += len(fitted["role"]) + len(fitted["content"]) + 8

    # Rebuild: pinned already in selected_rev; now take from end of rest.
    newer: list[dict[str, str]] = []
    for msg in reversed(rest):
        fitted = _fit(msg, available - used)
        if fitted is None:
            break
        newer.append(fitted)
        used += len(fitted["role"]) + len(fitted["content"]) + 8

    newer.reverse()
    kept = selected_rev + newer
    omitted = len(messages) - len(kept)
    # If we dropped middle messages but kept pin + newer, insert a marker.
    if omitted > 0 and pinned and newer:
        marker = {
            "role": "user",
            "content": (
                f"[omitted {omitted} earlier messages to fit the context window; "
                "rely on the latest tool results and the original request]"
            ),
        }
        # Insert marker between pin and newer if it fits.
        marker_cost = len(marker["content"]) + 16
        if used + marker_cost < available:
            kept = selected_rev + [marker] + newer
            used += marker_cost
        else:
            kept = selected_rev + newer
    elif omitted > 0 and not pinned:
        marker = {
            "role": "user",
            "content": f"[omitted {omitted} earlier messages to fit the context window]",
        }
        kept = [marker] + newer

    if cfg.reinject_format_after_compact and omitted > 0:
        reminder = {"role": "user", "content": format_reminder_message()}
        rem_cost = len(reminder["content"]) + 16
        if used + rem_cost < available:
            kept = kept + [reminder]
            used += rem_cost

    return CompactResult(
        messages=kept,
        omitted=max(0, omitted),
        compacted=True,
        estimated_chars=used + system_cost,
    )


def truncate_marked(text: str, limit: int, *, keep: str = "tail") -> str:
    """Clip text with an explicit truncation marker (never silent)."""
    if limit <= 0 or len(text) <= limit:
        return text
    # Reserve room for the longest plausible marker for this string.
    marker_room = len(f"…[truncated {len(text)} chars]")
    body = max(1, limit - marker_room)
    marker = f"…[truncated {len(text) - body} chars]"
    if keep == "tail":
        return text[-body:] + marker
    return text[:body] + marker
