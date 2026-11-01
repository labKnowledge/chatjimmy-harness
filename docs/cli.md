# CLI reference

Entry points: `chatjimmy`, `cj`, `cjh` (identical).

```bash
cj                              # interactive agent (default)
cj -p "What is 2+2?"            # one-shot print
cj "What is 2+2?"               # print via ask rewrite
chatjimmy [GLOBAL OPTIONS] COMMAND [ARGS]...
```

## Global options

Placed **before** the subcommand (also used when `cj` has no subcommand):

| Option | Env | Default | Description |
|--------|-----|---------|-------------|
| `-p` / `--print` | | | One-shot print prompt (skips REPL) |
| `-w` / `--workspace` | | `.` | Workspace for default interactive agent |
| `--stats` | | | With `-p`, print HC1 stats |
| `--base-url` | `CHATJIMMY_BASE_URL` | `https://chatjimmy.ai` | API origin |
| `--timeout` | `CHATJIMMY_TIMEOUT` | `60` | Request timeout (seconds) |
| `--help` | | | Show help |

Related env: `CHATJIMMY_STATS=1` turns on HC1 stats for `ask` / `chat` without `--stats`.

Example:

```bash
chatjimmy --base-url https://chatjimmy.ai --timeout 120 ask "hello"
```

---

## `version`

Print harness package version.

```bash
chatjimmy version
```

---

## `doctor`

One-shot readiness: version, whether `chatjimmy`/`cj` are on `PATH`, API health, model list. Exit `0` only if everything looks good.

```bash
chatjimmy doctor
cj doctor
```

---

## `tools`

Print the built-in agent tool catalog (same text injected into the agent system prompt).

```bash
cj tools
```

---

## `agent`

Tool-using agent. See [agent.md](agent.md).

- No prompt → **interactive REPL** (history kept across messages)
- With prompt → one-shot (add `-i` to continue in the REPL after)

```bash
cj agent
cj agent -w . -i
cj agent "list files here" -w .
cj agent -i "list files" -w .
```

| Option | Description |
|--------|-------------|
| `-i` / `--interactive` | Multi-turn REPL (default when prompt is empty) |
| `-w` / `--workspace` | Sandbox root for tools |
| `-t` / `--tool` | Enable specific tools (repeatable) |
| `--max-turns` | Max model↔tool iterations per user message |
| `--no-shell` | Disable shell/python tools |
| `--cmd-timeout` | Exec timeout |
| `--json` / `-q` | One-shot machine / quiet output |

REPL slash commands: `/reset` `/tools` `/workspace` `/system` `/max-turns` `/help` `/exit`

---

## `health`

`GET /api/health`. Exit code `0` if healthy, `1` otherwise.

```bash
chatjimmy health
```

Prints status line, optional `backendDetails` JSON (hardware name, queue size), and timestamp.

---

## `models`

`GET /api/models`. Table of `id`, `owned_by`, `created`.

```bash
chatjimmy models
```

Typically a single model: `llama3.1-8B` (Taalas Inc.).

---

## `ask` (and bare prompts)

Single-turn chat. Streams tokens to stdout by default.

```bash
cj "Explain recursion in one sentence." --stats
chatjimmy ask "Explain recursion in one sentence." --stats
```

Any first positional that is **not** a known subcommand is rewritten to `ask`, so `cj "…"` works.

| Option / arg | Short | Default | Description |
|--------------|-------|---------|-------------|
| `prompt` | | | User text; `-` reads stdin; piped stdin also works |
| `--model` | `-m` | `llama3.1-8B` | Model id |
| `--system` | `-s` | `""` | System prompt |
| `--top-k` | `-k` | `8` | Top-K sampling |
| `--stream` / `--no-stream` | | stream on | Token streaming |
| `--stats` | | off | Print HC1 stats to stderr (`CHATJIMMY_STATS=1` same) |
| `--attach` | `-a` | | Attach a file |
| `--json` | | off | Emit `{text, stats}` JSON (implies buffered, not stream) |

Examples:

```bash
cj "Summarize this file" --attach notes.txt --stats
echo "ping" | cj ask - --json
CHATJIMMY_STATS=1 cj "hello"
```

---

## `chat`

Interactive multi-turn REPL. Conversation history is kept in memory for the session.

```bash
chatjimmy chat --system "Be terse." --stats
```

| Option | Short | Default |
|--------|-------|---------|
| `--model` / `-m` | | `llama3.1-8B` |
| `--system` / `-s` | | `""` |
| `--top-k` / `-k` | | `8` |
| `--stats` | | off (toggleable) |

### REPL slash commands

| Input | Action |
|-------|--------|
| `/exit`, `/quit`, `:q` | Leave the REPL |
| `/reset` | Clear message history |
| `/stats` | Toggle HC1 stats after each turn |
| `/system <text>` | Set (or clear) system prompt for following turns |
| Ctrl-D / Ctrl-C | Exit |

---

## `run`

Run an evaluation suite. See [suites.md](suites.md).

```bash
chatjimmy run examples/smoke.json -o results.json
chatjimmy run examples/smoke.jsonl --quiet
```

| Option | Short | Description |
|--------|-------|-------------|
| `--model` / `-m` | Override suite/default model |
| `--system` / `-s` | Override suite system prompt |
| `--top-k` / `-k` | Override top-k |
| `--output` / `-o` | Write full JSON results |
| `--quiet` / `-q` | Suppress table; still writes `-o` if set |

Exit code: `0` if all cases pass, `1` if any fail.

---

## `bench`

Repeated timed completions; summarizes latency and HC1 decode metrics. See [bench.md](bench.md).

```bash
chatjimmy bench "Say hi in three words." -n 5
chatjimmy bench -n 10 --json
```

| Option | Short | Default |
|--------|-------|---------|
| `--runs` / `-n` | | `5` |
| `--model` / `-m` | | `llama3.1-8B` |
| `--system` / `-s` | | `""` |
| `--top-k` / `-k` | | `8` |
| `--json` | | off |

Default prompt if omitted: `Write one short sentence about silicon.`

Exit code: `0` if all runs succeed, `1` if any error.
