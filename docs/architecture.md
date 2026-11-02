# Architecture

## Package layout

```
chatjimmy-harness/
├── docs/
├── examples/                  # suites + sample workspaces
├── src/chatjimmy_harness/
│   ├── client.py              # HTTP adapter
│   ├── config.py              # harness knobs (budgets, modes)
│   ├── instructions.py        # budgeted system-prompt sections
│   ├── context.py             # prefill-aware history shaping
│   ├── agent.py               # tool-call parse + agent loop (core)
│   ├── harness.py             # suite/bench domain logic
│   ├── tools/                 # local tool adapters (fs, edit, search, exec)
│   ├── display.py             # Markdown / live terminal rendering
│   └── cli.py                 # Typer UI adapter
├── tests/
└── pyproject.toml
```

Console scripts (`chatjimmy`, `cj`, `cjh`) all map to `chatjimmy_harness.cli:run` (argv rewrite for bare prompts, then Typer).

## Upstream

HTTP shapes and dataclass fields follow [0xMH/chatjimmy-api](https://github.com/0xMH/chatjimmy-api). This harness:

- Adds a Typer/Rich CLI, suite runner, and bench summary
- Streams chat responses incrementally (upstream buffers the full body before yielding)

## HTTP API (chatjimmy.ai)

Base URL default: `https://chatjimmy.ai`

| Method | Path | Body / notes |
|--------|------|----------------|
| `GET` | `/api/health` | JSON health + `backendDetails` |
| `GET` | `/api/models` | `{ "object": "list", "data": [ Model… ] }` |
| `POST` | `/api/chat` | Streaming text + optional stats trailer |

### Chat request body

```json
{
  "messages": [{"role": "user", "content": "…"}],
  "chatOptions": {
    "selectedModel": "llama3.1-8B",
    "systemPrompt": "",
    "topK": 8
  },
  "attachment": null
}
```

`attachment`, when set: `{ "name", "size", "content" }` (string content).

No authentication headers are required. Client sets `User-Agent: chatjimmy-harness/<version>` and `Content-Type: application/json`.

### Chat response stream

The response body is plain text tokens, then a final trailer:

```text
…generated text…<|stats|>{…json…}<|/stats|>
```

`client._iter_chat_chunks` yields visible text as bytes arrive, holding back a short suffix so a split `<|stats|>` open tag never leaks into printed output. When the close tag arrives, it yields `("", Stats)`.

## Data flow

```
CLI (cli.py)
  ├─ ask/chat ──► ChatJimmy (client.py) ──HTTP──► chatjimmy.ai
  ├─ agent ──► run_agent (agent.py)
  │              ├─ config + instructions (budgeted system)
  │              ├─ context.select (prefill compact)
  │              ├─ parse <tool_call> (+ repair nudge)
  │              ├─ tools/* (workspace jail, mode-filtered)
  │              └─ feed truncated result back into messages
  └─ run/bench ──► harness.py (optional agent cases)
```

## Design notes

- **Not a daemon** — the harness is a CLI; each invocation is a short-lived process.
- **Capability is configuration** — budgets, modes, compaction, and repair live in `config` / `instructions` / `context`; see [harness.md](harness.md).
- **Bare prompt** — `cli._rewrite_bare_prompt_argv` inserts `ask` when the first positional is not a known command.
- **Stats on stderr** — `--stats` / `CHATJIMMY_STATS` print HC1 tables on stderr so piped stdout stays clean.
- **Markdown on stdout** — `display.py` renders assistant replies with Rich Markdown in a TTY (live during streams); `CHATJIMMY_PLAIN=1` keeps raw text.
- **Suite checks** — intentionally simple (substring / length); extend `harness.check_case`.
