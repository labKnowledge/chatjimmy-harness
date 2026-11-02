# chatjimmy-harness

CLI evaluation harness for [chatjimmy.ai](https://chatjimmy.ai) — Taalas HC1 running Llama 3.1 8B.

**Docs:** [docs/index.md](docs/index.md)

## Install

```bash
cd chatjimmy-harness
uv tool install -e .
# ensure ~/.local/bin is on PATH
cj doctor
cj -p "hi"
```

Full install / update / uninstall: [docs/install.md](docs/install.md)

## Quick commands

```bash
cj doctor
cj                                 # interactive agent (default)
cj -p "Explain recursion." --stats # one-shot print
cj agent "list files" -w .         # one-shot tool task
cj tools
chatjimmy run examples/smoke.json -o results.json
chatjimmy bench "Say hi in three words." -n 5
```

Aliases: `chatjimmy`, `cj`, `cjh` · versioning: [docs/versioning.md](docs/versioning.md) (`0.0.N`, major +5)

## Documentation

| Doc | Topic |
|-----|-------|
| [docs/index.md](docs/index.md) | Overview |
| [docs/install.md](docs/install.md) | Install on PATH |
| [docs/cli.md](docs/cli.md) | CLI reference |
| [docs/agent.md](docs/agent.md) | Tool-using agent |
| [docs/harness.md](docs/harness.md) | Config, budgets, modes, compaction |
| [docs/suites.md](docs/suites.md) | Eval suite format |
| [docs/bench.md](docs/bench.md) | Benchmarking |
| [docs/python-api.md](docs/python-api.md) | Python client |
| [docs/architecture.md](docs/architecture.md) | Layout + HTTP protocol |
| [docs/limits.md](docs/limits.md) | Caps and caveats |
| [docs/dev.md](docs/dev.md) | Develop this repo |
| [docs/versioning.md](docs/versioning.md) | `0.0.N` (+1 / +5) |

## License

MIT

## Influence and learning from

- [pingdotgg/t3code](https://github.com/pingdotgg/t3code) — agent harness control-plane patterns (budgets, modes, instruction sections, marked truncation)
- [0xMH/chatjimmy-api](https://github.com/0xMH/chatjimmy-api) — ChatJimmy HTTP client protocol (MIT); this harness adds streaming, the CLI, and the local tool loop
