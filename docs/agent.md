# Agent + tools

ChatJimmy has no native function-calling API. The harness adds a **local tool loop**: the model emits a `<tool_call>`, the harness runs it in a workspace jail, feeds the result back, and repeats until a final answer (or `max_turns`).

Capability on Llama 3.1 8B comes from **harness configuration** — budgets, modes, compaction, and repair. See [harness.md](harness.md).

## Quick start

```bash
cj                                # interactive agent REPL (default)
cj -w examples/workspaces/hello_bug
cj -p "What is 2+2?"              # one-shot print (no tools)
cj tools                          # list tools
cj agent "list files here" -w .   # one-shot tool task
cj agent --mode plan "outline a fix for the flaky test"
cj agent -i "list files" -w .     # one task, then stay in agent REPL
```

### Interactive REPL

`cj` (or `cj agent`) opens a multi-turn session. Each message runs a tool loop; conversation history (including prior tool results) is kept. History is compacted automatically when it approaches the prefill budget.

| Slash command | Action |
|---------------|--------|
| `/reset` | Clear history |
| `/tools` | Show enabled tools |
| `/mode act\|plan` | Switch interaction mode |
| `/workspace <path>` | Switch sandbox root |
| `/system <text>` | Set extra system prompt |
| `/max-turns <n>` | Cap tool-loop turns per message |
| `/help` | List commands |
| `/exit` | Quit |

## Built-in tools

| Tool | Purpose | Plan mode |
|------|---------|-----------|
| `read_file` | Read a text file | yes |
| `write_file` | Create/overwrite a text file | no |
| `list_dir` | List a directory | yes |
| `mkdir` | Create directories | no |
| `delete_path` | Delete a file or empty directory | no |
| `str_replace` | Exact substring edit | no |
| `glob` | Find paths by glob | yes |
| `grep` | Regex search in files | yes |
| `run_shell` | Shell command (`cwd=workspace`) | no |
| `run_python` | Run a Python snippet in the workspace | no |

All file paths are **jailed** to `--workspace` (default `.`). Shell/python inherit that cwd. Use `--no-shell` to disable exec tools. Put project guidance in `AGENTS.md` (or `.chatjimmy.md` / `CLAUDE.md`) at the workspace root — the harness injects it into the system prompt under a char budget.

## Tool-call format

The model is instructed to emit:

```xml
<tool_call>
<name>read_file</name>
<arg name="path">README.md</arg>
</tool_call>
```

JSON fallback is also parsed:

````text
```json
{"tool": "grep", "args": {"pattern": "TODO", "path": "."}}
```
````

Broken tool-shaped replies get a **format repair nudge** (default 2) instead of ending the turn.

## CLI flags

| Flag | Meaning |
|------|---------|
| `-w` / `--workspace` | Sandbox root |
| `--mode act\|plan` | Act (default) or read-only plan |
| `-t` / `--tool` | Enable one tool (repeat); default all |
| `--max-turns` | Cap model↔tool loops (default 12) |
| `--no-shell` | Drop `run_shell` / `run_python` |
| `--cmd-timeout` | Exec timeout seconds |
| `--json` | Full step trace |
| `-q` / `--quiet` | Final answer only |

## Suite cases with tools

Set `"agent": true` on the suite or a case. Relative `workspace` paths resolve from the suite file’s directory.

```json
{
  "name": "agent-tools",
  "agent": true,
  "workspace": "workspaces/hello_bug",
  "max_turns": 10,
  "cases": [
    {
      "id": "fix-add",
      "prompt": "Fix mathutil.add and run pytest. Say FIXED when done.",
      "min_tool_calls": 2,
      "expect_contains": ["FIXED"],
      "expect_file_contains": [
        {"path": "mathutil.py", "contains": "return a + b"}
      ]
    }
  ]
}
```

Extra checks:

| Field | Pass when |
|-------|-----------|
| `min_tool_calls` | Agent invoked at least N tools |
| `expect_file_contains` | Workspace file contains substring after the run |
| `allow_max_turns` | Do not fail solely because `max_turns` was hit |
| `isolate` | Copy workspace to a temp dir before the run (default `true`) so suites do not mutate fixtures |

Example suite: `examples/agent_tools.json`.

## Limits

- Llama 3.1 8B is small — tool use is **best-effort**, not guaranteed. Prefer short tasks and clear prompts.
- Prefill grows each turn (tool results accumulate). The harness compacts history and truncates tool output with markers; stay under ~6k prefill ([limits.md](limits.md)).
- Shell is powerful; keep workspaces disposable and prefer `--no-shell` for untrusted prompts.
