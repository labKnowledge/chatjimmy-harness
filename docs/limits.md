# Limits and caveats

chatjimmy.ai is a **public unofficial demo** of Taalas HC1 inference. Behavior can change or the service can go offline without notice.

## Auth and rate limits

- **No authentication** required.
- No hard rate limit observed by the upstream wrapper authors (burst tests reported). Be polite anyway; this is a shared demo.

## Token / context limits

| Limit | Behavior |
|-------|----------|
| Prefill (input) ~**6064** tokens | Over-limit often returns **HTTP 200 with empty body** and no error |
| Output | No hard cap; model stops on EOS (~1200–2400 tokens typical) |

Keep suite prompts and attachments small. Empty responses usually mean context overflow or a transient backend blip — check `chatjimmy health` and shorten input.

## Models

Currently a single model is listed:

- `llama3.1-8B` — owned by `Taalas Inc.`

## Stats trailer

Inference metrics appear only when the response includes a complete `<|stats|>…<|/stats|>` block. If the connection drops mid-stream, you may get text with `stats=None`.

Reported `decode_rate` is **silicon throughput**, not `decode_tokens / wall_latency`.

## Network

- Default timeout is **60s** (`--timeout` / `CHATJIMMY_TIMEOUT`).
- Attachments are sent as JSON string content; large binary files are a poor fit.

## Legal / ToS

This harness is unofficial. Review Taalas / chatjimmy.ai terms before production or heavy automated use. See also upstream disclaimer: [0xMH/chatjimmy-api](https://github.com/0xMH/chatjimmy-api).
