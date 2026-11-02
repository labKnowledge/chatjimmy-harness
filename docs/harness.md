# Harness configuration

Agent capability on ChatJimmy (Llama 3.1 8B, ~6k prefill, no native tools) comes from **configuration**, not from a bigger model. Budgets, modes, compaction, and repair are sized for a tiny context window.

## What the harness owns

| Concern | Module | Behavior |
|---------|--------|----------|
| Knobs / budgets | `config.py` | Prefill ceiling, truncation, modes, turn caps |
| System prompt | `instructions.py` | Versioned, budgeted sections; workspace `AGENTS.md` |
| History shaping | `context.py` | Pin first user + newest fill; mark omissions |
| Tool loop | `agent.py` | Parse, repair nudges, empty-response recovery, compact |
| Tool adapters | `tools/` | Workspace jail; mode-filtered registry |

## Interaction modes

| Mode | CLI | Effect |
|------|-----|--------|
| `act` (default) | `--mode act` / `/mode act` | Full tool set; carry out the task |
| `plan` | `--mode plan` / `/mode plan` | Read-only tools only; return a plan, do not edit |

## Runtime modes

`runtime_mode` (env `CHATJIMMY_RUNTIME_MODE`):

| Value | Meaning |
|-------|---------|
| `approval-required` | Mark mutating tools for audit (shell still gated by `--no-shell`) |
| `auto` (default) | Normal tool execution |
| `full-access` | Same as auto today; reserved for future sandbox ceilings |

## Prefill budget

Defaults assume the observed ~**6064** prefill hard limit:

- Soft ceiling: **5500** tokens (`CHATJIMMY_MAX_PREFILL_TOKENS`)
- Char estimate: **4** chars/token (`CHATJIMMY_CHARS_PER_TOKEN`)
- System prompt budget: **3200** chars
- Tool results: **4000** chars, **tail** kept (shell dumps matter at the end)
- On overflow risk: drop middle history, insert `[omitted N earlier messages…]`, re-inject a short format reminder

Empty API bodies (common overflow symptom) trigger one history trim + retry.

## Instruction composition

System text is assembled as ordered sections, each clipped with an explicit `[truncated …]` marker:

1. Core harness rules + exact `<tool_call>` schema
2. Mode section (`act` / `plan`)
3. Compact tool catalog
4. Workspace file if present: `AGENTS.md`, then `.chatjimmy.md`, then `CLAUDE.md`
5. Caller `--system` extras

Never silently clip — the model must see that something was cut.

## Format repair

If the model emits something that *looks* like a tool call (`<tool_call`, `"tool":`, …) but does not parse, the harness sends a short repair nudge (default up to **2**) instead of treating it as a final answer. Critical for an 8B model without native function calling.

## Environment knobs

| Env | Purpose |
|-----|---------|
| `CHATJIMMY_MAX_PREFILL_TOKENS` | Soft prefill ceiling |
| `CHATJIMMY_CHARS_PER_TOKEN` | Char→token estimate |
| `CHATJIMMY_SYSTEM_BUDGET_CHARS` | Max system prompt size |
| `CHATJIMMY_TOOL_RESULT_LIMIT` | Per-result render cap |
| `CHATJIMMY_TOOL_RESULT_KEEP` | `head` or `tail` |
| `CHATJIMMY_MAX_TURNS` | Default tool-loop turns |
| `CHATJIMMY_MAX_REPAIR_NUDGES` | Broken tool-call retries |
| `CHATJIMMY_MODE` | `act` / `plan` |
| `CHATJIMMY_RUNTIME_MODE` | `approval-required` / `auto` / `full-access` |
| `CHATJIMMY_LOAD_WORKSPACE_INSTRUCTIONS` | Load `AGENTS.md` etc. |

## Python

```python
from pathlib import Path
from chatjimmy_harness.client import ChatJimmy
from chatjimmy_harness.config import HarnessConfig
from chatjimmy_harness.agent import run_agent

cfg = HarnessConfig(interaction_mode="plan", max_turns=10, tool_result_keep="tail")
result = run_agent(
    ChatJimmy(),
    "How should we fix the flaky test?",
    workspace=Path("."),
    config=cfg,
)
```

## Design taste

- Own the turn lifecycle in the harness; the model only proposes tool calls.
- Capability from budgets and recovery, not from dumping more prompt text.
- Mark every truncation.
- Gate optional sections behind mode / flags.
- Keep instruction sections self-contained and short enough for the model that will read them.
