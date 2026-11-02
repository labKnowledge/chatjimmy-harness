# chatjimmy-harness docs

CLI evaluation harness for [chatjimmy.ai](https://chatjimmy.ai) — a public Taalas demo running Llama 3.1 8B on HC1 silicon (~17k–20k+ tok/s decode).

## Contents

| Doc | What it covers |
|-----|----------------|
| [install.md](install.md) | Install `uv`, install the harness on PATH (`chatjimmy` / `cj`), update, uninstall |
| [cli.md](cli.md) | Full CLI reference: global flags, every command, REPL slash-commands |
| [suites.md](suites.md) | Eval suite JSON / JSONL format, checks, exit codes, result schema |
| [bench.md](bench.md) | Latency / decode-rate benchmarking |
| [python-api.md](python-api.md) | Use the Python client from your own code |
| [architecture.md](architecture.md) | Project layout, HTTP endpoints, streaming + stats trailer |
| [limits.md](limits.md) | Auth, rate limits, token caps, known quirks |
| [agent.md](agent.md) | Tool-using agent (files, shell, code, search) |
| [harness.md](harness.md) | Config, budgets, act/plan modes, compaction, repair |
| [dev.md](dev.md) | Develop / test / release this repo |
| [versioning.md](versioning.md) | `0.0.N` bumps (+1 / +5) |

## Quick start

```bash
# after install (see install.md)
cj doctor
cj                          # interactive agent REPL
cj -p "Explain recursion."  # one-shot print
chatjimmy run examples/smoke.json -o results.json
chatjimmy bench -n 5
```

## Commands at a glance

| Command | Purpose |
|---------|---------|
| `cj` | Interactive agent REPL (default) |
| `cj -p "…"` | One-shot print (no tools loop) |
| `cj "…"` / `ask` | Same as print via ask rewrite |
| `cj agent` / `cj agent "…"` | Explicit agent REPL or one-shot tool loop |
| `cj tools` | List built-in tools |
| `chatjimmy doctor` | PATH + API readiness in one shot |
| `chatjimmy health` | Probe API + HC1 backend |
| `chatjimmy models` | List models |
| `chatjimmy chat` | Interactive multi-turn REPL |
| `chatjimmy run <suite>` | Run eval suite (supports agent cases) |
| `chatjimmy bench [prompt]` | Timed repeated runs |
| `chatjimmy version` | Print harness version |

Aliases: `chatjimmy`, `cj`, `cjh` — all invoke the same CLI.

## Influence and learning from

- [pingdotgg/t3code](https://github.com/pingdotgg/t3code) — agent harness control-plane patterns (budgets, modes, instruction sections, marked truncation)
- [0xMH/chatjimmy-api](https://github.com/0xMH/chatjimmy-api) — ChatJimmy HTTP client protocol (MIT); this harness adds streaming, the CLI, and the local tool loop
