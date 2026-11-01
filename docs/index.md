# chatjimmy-harness docs

CLI evaluation harness for [chatjimmy.ai](https://chatjimmy.ai) — a public Taalas demo running Llama 3.1 8B on HC1 silicon (~17k–20k+ tok/s decode).

Client protocol adapted from [0xMH/chatjimmy-api](https://github.com/0xMH/chatjimmy-api) (MIT), with incremental streaming for the REPL and ask command.

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
| [dev.md](dev.md) | Develop / test / release this repo |

## Quick start

```bash
# after install (see install.md)
cj doctor
cj "Explain recursion in one sentence." --stats
cj agent "list files and read README.md" -w .
chatjimmy run examples/smoke.json -o results.json
chatjimmy bench -n 5
```

Bare prompts work — no subcommand required: `cj "What is 2+2?"`

## Commands at a glance

| Command | Purpose |
|---------|---------|
| `cj "…"` / `chatjimmy ask …` | Single-turn (streams by default); stdin via `-` |
| `cj agent "…"` | Tool loop: read/write/edit/search/shell/python |
| `cj tools` | List built-in tools |
| `chatjimmy doctor` | PATH + API readiness in one shot |
| `chatjimmy health` | Probe API + HC1 backend |
| `chatjimmy models` | List models |
| `chatjimmy chat` | Interactive multi-turn REPL |
| `chatjimmy run <suite>` | Run eval suite (supports agent cases) |
| `chatjimmy bench [prompt]` | Timed repeated runs |
| `chatjimmy version` | Print harness version |

Aliases: `chatjimmy`, `cj`, `cjh` — all invoke the same CLI.
