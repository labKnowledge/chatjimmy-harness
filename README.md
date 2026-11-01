# chatjimmy-harness

CLI evaluation harness for [chatjimmy.ai](https://chatjimmy.ai) — Taalas HC1 running Llama 3.1 8B.

**Docs:** [docs/index.md](docs/index.md)

Client protocol adapted from [0xMH/chatjimmy-api](https://github.com/0xMH/chatjimmy-api) (MIT), with incremental streaming for the REPL.

## Install

```bash
cd chatjimmy-harness
uv tool install -e .
# ensure ~/.local/bin is on PATH
cj doctor
cj "hi"
```

Full install / update / uninstall: [docs/install.md](docs/install.md)

## Quick commands

```bash
cj doctor
cj "Explain recursion in one sentence." --stats
cj agent "list files and summarize README" -w .
cj tools
chatjimmy run examples/smoke.json -o results.json
chatjimmy run examples/agent_tools.json
chatjimmy bench "Say hi in three words." -n 5
```

Aliases: `chatjimmy`, `cj`, `cjh` — bare prompts work: `cj "What is 2+2?"`

## Documentation

| Doc | Topic |
|-----|-------|
| [docs/index.md](docs/index.md) | Overview |
| [docs/install.md](docs/install.md) | Install on PATH |
| [docs/cli.md](docs/cli.md) | CLI reference |
| [docs/agent.md](docs/agent.md) | Tool-using agent |
| [docs/suites.md](docs/suites.md) | Eval suite format |
| [docs/bench.md](docs/bench.md) | Benchmarking |
| [docs/python-api.md](docs/python-api.md) | Python client |
| [docs/architecture.md](docs/architecture.md) | Layout + HTTP protocol |
| [docs/limits.md](docs/limits.md) | Caps and caveats |
| [docs/dev.md](docs/dev.md) | Develop this repo |

## License

MIT
