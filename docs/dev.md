# Developer guide

How to work on chatjimmy-harness itself.

## Layout

| Path | Role |
|------|------|
| `src/chatjimmy_harness/client.py` | HTTP adapter + streaming/stats parse |
| `src/chatjimmy_harness/agent.py` | Tool-call parse + multi-turn agent loop |
| `src/chatjimmy_harness/tools/` | File/search/edit/shell/python tool adapters |
| `src/chatjimmy_harness/harness.py` | Suite/bench domain logic |
| `src/chatjimmy_harness/cli.py` | Typer/Rich adapter; argv rewrite for bare prompts |
| `tests/` | Unit tests (no live network required) |
| `examples/` | Suites + coding workspaces |
| `docs/` | User + developer docs |

**Core / adapters:** agent loop + checks are framework-free; `tools/` and `cli.py` are adapters. Protocol parsing lives in `client.py`.

## Setup

```bash
cd chatjimmy-harness
uv sync --group dev
uv run pytest
```

Editable user install (so `cj` picks up local edits, except entry-point/dependency changes):

```bash
uv tool install -e .
# after changing [project.scripts] or dependencies:
uv tool install --force -e .
```

## Versioning

See [versioning.md](versioning.md): stay on `0.0.N`; small = +1, major = +5; `N` goes past 9 to 99.

## UX contracts to preserve

1. **`cj` alone** — starts the interactive agent REPL (not help text).
2. **`-p` / `--print`** — one-shot print answer (`cj -p "What is 2+2?"`).
3. **Bare prompt** — `cj "What is 2+2?"` still works (rewritten to `ask`).
4. **stdin** — `cj ask -` / `cj -p -` style flows must work where documented.
5. **doctor** — one command answers “is this machine + API ready?”
6. **Stats on stderr** — keep stdout clean for pipes.
7. **Exit codes** — `health` / `run` / `bench` / `doctor` / `agent` use `0`/`1`.
8. **Workspace jail** — tools must not read/write outside `--workspace`.

## Tests

```bash
uv run pytest -q
```

Prefer pure unit tests for `check_case`, `load_suite`, `_iter_chat_chunks`, and argv rewrite. Live API smoke is manual:

```bash
cj doctor
cj -p "Reply with exactly: pong"
chatjimmy run examples/smoke.json
```

## Release checklist

1. Bump version per [versioning.md](versioning.md) (`pyproject.toml`, `__init__.py`, User-Agent)
2. Update docs if CLI surface changed
3. `uv run pytest`
4. `uv tool install --force -e .` and `cj doctor`

## Design north star

Maximize value, minimize effort: absorb complexity in the tool so the user types a question or a suite path — not flags they should not have to remember.
