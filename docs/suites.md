# Eval suites

`chatjimmy run` loads a suite file, calls the API for each case, applies checks, and prints a pass/fail table.

```bash
chatjimmy run examples/smoke.json -o results.json
```

## File formats

### JSON object (recommended)

```json
{
  "name": "smoke",
  "system_prompt": "Answer briefly and precisely.",
  "model": "llama3.1-8B",
  "top_k": 8,
  "cases": [
    {
      "id": "capital-france",
      "prompt": "What is the capital of France? Reply with one word.",
      "expect_contains": ["Paris"],
      "max_chars": 200
    }
  ]
}
```

### JSON array

A bare array of case objects is accepted; suite `name` defaults to the filename stem.

### JSONL

One JSON object per line. Blank lines and `#` comments are skipped.

```jsonl
{"id": "haiku", "prompt": "Write a one-line haiku about chips.", "min_chars": 10}
{"id": "json-ish", "prompt": "Reply with exactly: ok", "expect_contains": ["ok"]}
```

## Suite-level fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Label in the summary (default: file stem) |
| `system_prompt` | string | Default system prompt for cases |
| `model` | string | Default model id |
| `top_k` | int | Default top-k |
| `cases` | array | Required for object form |

CLI `--model` / `--system` / `--top-k` override suite defaults.

## Case fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Case id (default `case-N`) |
| `prompt` | string | Single user message (required unless `messages`) |
| `messages` | array | Full message list `[{role, content}, …]` |
| `system_prompt` | string | Per-case system prompt |
| `model` | string | Per-case model |
| `top_k` | int | Per-case top-k |

### Checks

All substring checks are **case-insensitive**.

| Field | Pass when |
|-------|-----------|
| `expect_contains` | Every listed string appears in the response |
| `expect_not_contains` | None of the listed strings appear |
| `min_chars` | `len(text) >= min_chars` |
| `max_chars` | `len(text) <= max_chars` |

If a case defines **no** checks, it passes when the response is non-empty (`non_empty`).

A case **fails** if any check fails, or if the HTTP/client call raises (error recorded on the case).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All cases passed |
| `1` | One or more failed |

## Result JSON (`-o`)

```json
{
  "name": "smoke",
  "passed": 3,
  "failed": 0,
  "total": 3,
  "duration_s": 1.29,
  "cases": [
    {
      "id": "capital-france",
      "prompt": "…",
      "text": "Paris",
      "ok": true,
      "passed_checks": ["contains:'Paris'", "max_chars:200"],
      "failed_checks": [],
      "error": null,
      "stats": { "decode_rate": 17454.0, "…": "…" },
      "latency_s": 0.30
    }
  ]
}
```

## Examples in-repo

- `examples/smoke.json` — multi-case JSON suite
- `examples/smoke.jsonl` — JSONL smoke cases

## Agent / tool cases

Set `"agent": true` (suite or case) to run the tool loop. See [agent.md](agent.md).

| Field | Meaning |
|-------|---------|
| `workspace` | Sandbox dir (relative to the suite file) |
| `tools` | Optional allow-list of tool names |
| `max_turns` | Tool-loop cap |
| `min_tool_calls` | Require at least N tool invocations |
| `expect_file_contains` | Assert workspace file contents after the run |
| `allow_max_turns` | Do not fail only because the turn cap was hit |

## Tips

- Keep prompts short; prefill soft-limit is ~6064 tokens ([limits.md](limits.md)).
- Prefer `expect_contains` over exact equality — the model may add punctuation.
- Use `-s` / suite `system_prompt` to steer brief answers for easier checks.
- For coding evals, use a disposable `workspace` and `expect_file_contains`.
