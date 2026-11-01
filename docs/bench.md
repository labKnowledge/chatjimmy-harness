# Benchmarking

`chatjimmy bench` runs the same prompt N times sequentially and summarizes wall latency plus HC1 stats from each response.

```bash
chatjimmy bench "Say hi in three words." -n 5
chatjimmy bench -n 10 --json
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `prompt` (arg) | `Write one short sentence about silicon.` | Prompt for every run |
| `--runs` / `-n` | `5` | Number of timed completions |
| `--model` / `-m` | `llama3.1-8B` | Model |
| `--system` / `-s` | `""` | System prompt |
| `--top-k` / `-k` | `8` | Top-k |
| `--json` | off | Machine-readable summary |

## Metrics table

Human output columns (min / p50 / mean / p95 / max):

| Metric | Source |
|--------|--------|
| `latency (s)` | Client wall time around `chat()` |
| `ttft (s)` | HC1 `stats.ttft` |
| `decode tok/s` | HC1 `stats.decode_rate` |
| `decode tokens` | HC1 `stats.decode_tokens` |

Also prints `ok=N/M` and total wall seconds for the whole bench.

## JSON shape (`--json`)

```json
{
  "prompt": "…",
  "runs": 5,
  "ok": 5,
  "errors": 0,
  "wall_s": 1.02,
  "latency_s": { "min": 0.3, "max": 0.4, "mean": 0.34, "p50": 0.31, "p95": 0.4 },
  "decode_rate_tok_s": { "…": "…" },
  "decode_tokens": { "…": "…" },
  "ttft_s": { "…": "…" }
}
```

Missing blocks are omitted when no successful samples reported that field.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All runs succeeded |
| `1` | At least one run errored |

## Notes

- Sequential only (concurrency is not implemented; field reserved as `concurrency: 1` internally).
- Decode rate is server-reported silicon throughput, not end-to-end tokens / wall latency.
- Short prompts finish fast; longer generations stress decode metrics more.
