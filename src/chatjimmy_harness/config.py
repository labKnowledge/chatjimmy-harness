"""Harness configuration — the knobs that make the agent capable on a small model.

ChatJimmy (Llama 3.1 8B on HC1) has ~6064 prefill tokens and no native
function calling. Capability comes from tight budgets, marked truncation,
mode-aware tools, and recovery nudges — not from dumping more prompt text.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Literal

InteractionMode = Literal["act", "plan"]
RuntimeMode = Literal["approval-required", "auto", "full-access"]
TruncationKeep = Literal["head", "tail"]

# Soft ceiling under the observed ~6064 prefill hard limit.
DEFAULT_MAX_PREFILL_TOKENS = 5500
# Pessimistic: ~4 chars ≈ 1 token for English + XML markup.
DEFAULT_CHARS_PER_TOKEN = 4.0


@dataclass(frozen=True)
class HarnessConfig:
    """Central agent/harness knobs. Prefer changing these over hardcoding in the loop."""

    max_prefill_tokens: int = DEFAULT_MAX_PREFILL_TOKENS
    chars_per_token: float = DEFAULT_CHARS_PER_TOKEN
    # Cap injected system/instruction text so tools + history still fit.
    system_budget_chars: int = 3_200
    # Per tool-result render limit (exec dumps often need the tail).
    tool_result_limit: int = 4_000
    tool_result_keep: TruncationKeep = "tail"
    # Leave room inside the prefill window after system + history estimate.
    history_reserve_chars: int = 600
    max_turns: int = 12
    # When the model almost emits a tool call but XML/JSON is broken, nudge once.
    max_repair_nudges: int = 2
    empty_response_retries: int = 1
    interaction_mode: InteractionMode = "act"
    runtime_mode: RuntimeMode = "auto"
    load_workspace_instructions: bool = True
    instruction_file_names: tuple[str, ...] = (
        "AGENTS.md",
        ".chatjimmy.md",
        "CLAUDE.md",
    )
    max_workspace_instruction_chars: int = 1_800
    # Compact older tool results in-history when approaching budget.
    compact_tool_preview_chars: int = 240
    # After compaction, re-inject a short tool-format reminder (providers lose system).
    reinject_format_after_compact: bool = True

    def prefill_char_budget(self) -> int:
        return int(self.max_prefill_tokens * self.chars_per_token)

    def with_overrides(self, **kwargs: object) -> HarnessConfig:
        return replace(self, **kwargs)


_RUNTIME_RANK = {
    "approval-required": 0,
    "auto": 1,
    "full-access": 2,
}


def clamp_runtime_mode(requested: RuntimeMode, ceiling: RuntimeMode) -> RuntimeMode:
    if _RUNTIME_RANK[requested] <= _RUNTIME_RANK[ceiling]:
        return requested
    return ceiling


def config_from_env(base: HarnessConfig | None = None) -> HarnessConfig:
    """Apply CHATJIMMY_* env overrides on top of defaults / a base config."""
    cfg = base or HarnessConfig()
    updates: dict[str, object] = {}

    def _int(name: str, key: str) -> None:
        raw = os.environ.get(name)
        if raw and raw.strip().isdigit():
            updates[key] = int(raw.strip())

    def _float(name: str, key: str) -> None:
        raw = os.environ.get(name)
        if not raw:
            return
        try:
            updates[key] = float(raw.strip())
        except ValueError:
            pass

    def _bool(name: str, key: str) -> None:
        raw = os.environ.get(name)
        if raw is None:
            return
        updates[key] = raw.strip().lower() in {"1", "true", "yes", "on"}

    def _choice(name: str, key: str, allowed: set[str]) -> None:
        raw = os.environ.get(name)
        if raw and raw.strip().lower() in allowed:
            updates[key] = raw.strip().lower()

    _int("CHATJIMMY_MAX_PREFILL_TOKENS", "max_prefill_tokens")
    _float("CHATJIMMY_CHARS_PER_TOKEN", "chars_per_token")
    _int("CHATJIMMY_SYSTEM_BUDGET_CHARS", "system_budget_chars")
    _int("CHATJIMMY_TOOL_RESULT_LIMIT", "tool_result_limit")
    _int("CHATJIMMY_MAX_TURNS", "max_turns")
    _int("CHATJIMMY_MAX_REPAIR_NUDGES", "max_repair_nudges")
    _choice("CHATJIMMY_MODE", "interaction_mode", {"act", "plan"})
    _choice(
        "CHATJIMMY_RUNTIME_MODE",
        "runtime_mode",
        {"approval-required", "auto", "full-access"},
    )
    _choice("CHATJIMMY_TOOL_RESULT_KEEP", "tool_result_keep", {"head", "tail"})
    _bool("CHATJIMMY_LOAD_WORKSPACE_INSTRUCTIONS", "load_workspace_instructions")

    return cfg.with_overrides(**updates) if updates else cfg


# Write/exec tools blocked in plan mode (read-only investigation).
PLAN_BLOCKED_TOOLS = frozenset(
    {
        "write_file",
        "delete_path",
        "mkdir",
        "str_replace",
        "run_shell",
        "run_python",
    }
)

# Under approval-required, mutating tools are still available but the loop
# records them for audit; shell stays gated by allow_shell separately.
MUTATING_TOOLS = PLAN_BLOCKED_TOOLS
