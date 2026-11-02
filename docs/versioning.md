# Versioning

Stay on the **`0.0.N`** line. Do not jump to `0.1.x` or `1.x` as a habit — keep one continuous flow.

## Rules

| Change type | Bump | Example |
|-------------|------|---------|
| Small fix / polish | **+1** | `0.0.5` → `0.0.6` |
| Major feature / UX shift | **+5** | `0.0.5` → `0.0.10` |

- `N` counts normally through **0…99** (`0.0.9` → `0.0.10`, not a new major).
- After `0.0.99`, roll to `0.0.100` only if needed — still the same flow (or discuss resetting intentionally).
- Always bump **together**: `pyproject.toml`, `src/chatjimmy_harness/__init__.py`, and the client `User-Agent`.

## Current

**0.0.10** — harness config layer (budgets, act/plan modes, context compaction, tool-call repair, workspace `AGENTS.md`) sized for the ~6k prefill window.
