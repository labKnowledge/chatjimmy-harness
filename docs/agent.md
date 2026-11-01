# Agent + tools

ChatJimmy has no native function-calling API. The harness adds a **local tool loop**: the model emits a `<tool_call>`, the harness runs it in a workspace jail, feeds the result back, and repeats until a final answer (or `max_turns`).

## Quick start

```bash
cj                                # interactive agent REPL (default)
cj -w examples/workspaces/hello_bug
cj -p "What is 2+2?"              # one-shot print (no tools)
cj tools                          # list tools
cj agent "list files here" -w .   # one-shot tool task
cj agent -i "list files" -w .     # one task, then stay in agent REPL
```

### Interactive REPL

`cj` (or `cj agent`) opens a multi-turn session. Each message runs a tool loop; conversation history (including prior tool results) is kept.

| Slash command | Action |
|---------------|--------|
| `/reset` | Clear history |
| `/tools` | Show enabled tools |
| `/workspace <path>` | Switch sandbox root |
| `/system <text>` | Set extra system prompt |
| `/max-turns <n>` | Cap tool-loop turns per message |
| `/help` | List commands |
| `/exit` | Quit |

## Built-in tools

| Tool | Purpose |
|------|---------|
| `read_file` | Read a text file |
| `write_file` | Create/overwrite a text file |
| `list_dir` | List a directory |
| `mkdir` | Create directories |
| `delete_path` | Delete a file or empty directory |
| `str_replace` | Exact substring edit |
| `glob` | Find paths by glob |
| `grep` | Regex search in files |
| `run_shell` | Shell command (`cwd=workspace`) |
| `run_python` | Run a Python snippet in the workspace |

All file paths are **jailed** to `--workspace` (default `.`). Shell/python inherit that cwd. Use `--no-shell` to disable exec tools.

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

## CLI flags

| Flag | Meaning |
|------|---------|
| `-w` / `--workspace` | Sandbox root |
| `-t` / `--tool` | Enable one tool (repeat); default all |
| `--max-turns` | Cap model↔tool loops (default 8) |
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
- Prefill grows each turn (tool results accumulate). Stay under ~6k prefill ([limits.md](limits.md)).
- Shell is powerful; keep workspaces disposable and prefer `--no-shell` for untrusted prompts.
