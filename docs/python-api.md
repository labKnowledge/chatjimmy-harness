# Python API

The same client the CLI uses is importable as `chatjimmy_harness`.

```python
from chatjimmy_harness import ChatJimmy, Message, Attachment

client = ChatJimmy()  # base_url="https://chatjimmy.ai", timeout=60
```

## `ChatJimmy`

| Method | Returns | Description |
|--------|---------|-------------|
| `health()` | `HealthStatus` | `GET /api/health` |
| `models()` | `list[Model]` | `GET /api/models` |
| `ask(prompt, …)` | `str` | Single-turn; returns text only |
| `chat(messages, …)` | `ChatResponse` | Full response + stats |
| `chat_stream(messages, …)` | generator of `str` | Yields text chunks; `StopIteration.value` is `ChatResponse` |

Shared chat kwargs: `model="llama3.1-8B"`, `system_prompt=""`, `top_k=8`, `attachment=None`.

### Simple ask

```python
print(client.ask("What is the capital of France?"))
```

### Chat + stats

```python
resp = client.chat(
    messages=[{"role": "user", "content": "Explain recursion"}],
    system_prompt="You are a CS tutor.",
    top_k=4,
)
print(resp.text)
if resp.stats:
    print(resp.stats.decode_tokens, resp.stats.decode_rate)
```

### Streaming

```python
gen = client.chat_stream(messages=[{"role": "user", "content": "Write a haiku"}])
try:
    while True:
        print(next(gen), end="", flush=True)
except StopIteration as done:
    resp = done.value
print()
```

### Multi-turn

```python
messages = [{"role": "user", "content": "My name is Ada."}]
resp = client.chat(messages)
messages.append({"role": "assistant", "content": resp.text})
messages.append({"role": "user", "content": "What is my name?"})
print(client.chat(messages).text)
```

### Typed helpers

```python
from chatjimmy_harness import Message, Attachment

resp = client.chat(
    messages=[Message(role="user", content="Summarize this")],
    attachment=Attachment(name="note.txt", size=5, content="hello"),
)
```

## Dataclasses

### `ChatResponse`

- `text: str`
- `stats: Stats | None`

### `Stats` (HC1 trailer)

| Field | Meaning |
|-------|---------|
| `prefill_tokens` / `prefill_rate` | Input tokens and tok/s |
| `decode_tokens` / `decode_rate` | Output tokens and tok/s |
| `total_tokens` / `total_time` | Combined |
| `ttft` | Time to first token (seconds) |
| `roundtrip_time` | Network RTT (ms) |
| `done_reason` | e.g. `stop` |

### `HealthStatus`

- `.healthy` → `True` when `status == "ok"` and `backend == "healthy"`
- Also: `nextjs`, `backend_status`, `backend_details`, `timestamp`

### `Model`

- `id`, `object`, `created`, `owned_by`

## Harness helpers

```python
from pathlib import Path
from chatjimmy_harness.client import ChatJimmy
from chatjimmy_harness.harness import load_suite, run_suite, run_bench

client = ChatJimmy()
suite = load_suite(Path("examples/smoke.json"))
result = run_suite(client, suite)
print(result.passed, result.total)
print(result.to_dict())

bench = run_bench(client, "Say hi.", runs=3)
print(bench.summary())
```

## Exports

From `chatjimmy_harness`:

`Attachment`, `ChatJimmy`, `ChatResponse`, `HealthStatus`, `Message`, `Model`, `Stats`, `__version__`
