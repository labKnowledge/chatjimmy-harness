"""HTTP client for the chatjimmy.ai API.

Adapted from https://github.com/0xMH/chatjimmy-api (MIT) with incremental
streaming so the harness can print tokens as they arrive.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = "https://chatjimmy.ai"
DEFAULT_MODEL = "llama3.1-8B"

_STATS_OPEN = "<|stats|>"
_STATS_CLOSE = "<|/stats|>"
_STATS_RE = re.compile(r"<\|stats\|>([\s\S]+?)<\|/stats\|>$")


@dataclass
class Stats:
    created_at: float = 0.0
    done: bool = False
    done_reason: str = ""
    total_duration: float = 0.0
    ttft: float = 0.0
    prefill_tokens: int = 0
    prefill_rate: float = 0.0
    decode_tokens: int = 0
    decode_rate: float = 0.0
    total_tokens: int = 0
    total_time: float = 0.0
    roundtrip_time: float = 0.0
    topk: int = 0
    status: int = 0
    reason: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Stats:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class ChatResponse:
    text: str
    stats: Stats | None = None


@dataclass
class Model:
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = ""


@dataclass
class HealthStatus:
    status: str = ""
    nextjs: str = ""
    backend: str = ""
    backend_status: int = 0
    backend_details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    @property
    def healthy(self) -> bool:
        return self.status == "ok" and self.backend == "healthy"


@dataclass
class Message:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class Attachment:
    name: str
    size: int
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "size": self.size, "content": self.content}


def _parse_stats(raw: str) -> Stats | None:
    try:
        return Stats.from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


class ChatJimmy:
    """Client for the chatjimmy.ai API."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "chatjimmy-harness/0.3",
                "Content-Type": "application/json",
                "Accept": "text/plain, */*",
            }
        )

    def health(self) -> HealthStatus:
        r = self.session.get(f"{self.base_url}/api/health", timeout=self.timeout)
        r.raise_for_status()
        d = r.json()
        return HealthStatus(
            status=d.get("status", ""),
            nextjs=d.get("nextjs", ""),
            backend=d.get("backend", ""),
            backend_status=d.get("backendStatus", 0),
            backend_details=d.get("backendDetails", {}),
            timestamp=d.get("timestamp", ""),
        )

    def models(self) -> list[Model]:
        r = self.session.get(f"{self.base_url}/api/models", timeout=self.timeout)
        r.raise_for_status()
        data = r.json().get("data", [])
        return [
            Model(
                id=m["id"],
                object=m.get("object", "model"),
                created=m.get("created", 0),
                owned_by=m.get("owned_by", ""),
            )
            for m in data
        ]

    def chat(
        self,
        messages: list[dict[str, str] | Message],
        model: str = DEFAULT_MODEL,
        system_prompt: str = "",
        top_k: int = 8,
        attachment: Attachment | None = None,
    ) -> ChatResponse:
        full_text = ""
        stats = None
        for chunk_text, chunk_stats in self._chat_stream(
            messages, model, system_prompt, top_k, attachment
        ):
            full_text += chunk_text
            if chunk_stats is not None:
                stats = chunk_stats
        return ChatResponse(text=full_text, stats=stats)

    def chat_stream(
        self,
        messages: list[dict[str, str] | Message],
        model: str = DEFAULT_MODEL,
        system_prompt: str = "",
        top_k: int = 8,
        attachment: Attachment | None = None,
    ) -> Generator[str, None, ChatResponse]:
        full_text = ""
        stats = None
        for chunk_text, chunk_stats in self._chat_stream(
            messages, model, system_prompt, top_k, attachment
        ):
            if chunk_stats is not None:
                stats = chunk_stats
            if chunk_text:
                full_text += chunk_text
                yield chunk_text
        return ChatResponse(text=full_text, stats=stats)

    def ask(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        system_prompt: str = "",
        top_k: int = 8,
        attachment: Attachment | None = None,
    ) -> str:
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            system_prompt=system_prompt,
            top_k=top_k,
            attachment=attachment,
        ).text

    def _chat_stream(
        self,
        messages: list[dict[str, str] | Message],
        model: str,
        system_prompt: str,
        top_k: int,
        attachment: Attachment | None,
    ) -> Iterator[tuple[str, Stats | None]]:
        msg_dicts = [m.to_dict() if isinstance(m, Message) else m for m in messages]
        body = {
            "messages": msg_dicts,
            "chatOptions": {
                "selectedModel": model,
                "systemPrompt": system_prompt,
                "topK": top_k,
            },
            "attachment": attachment.to_dict() if attachment else None,
        }
        r = self.session.post(
            f"{self.base_url}/api/chat",
            json=body,
            stream=True,
            timeout=self.timeout,
        )
        r.raise_for_status()
        yield from _iter_chat_chunks(r.iter_content(chunk_size=256))


def _iter_chat_chunks(
    raw_chunks: Iterator[bytes],
) -> Iterator[tuple[str, Stats | None]]:
    """Yield (text, None) chunks, then a final ("", stats) when present.

    Holds back a small suffix so a partial `<|stats|>` tag never leaks into
    the visible text stream.
    """
    holdback = len(_STATS_OPEN) - 1
    visible = ""
    pending = ""

    for raw in raw_chunks:
        pending += raw.decode("utf-8", errors="replace")

        # Once the stats fence appears, stop emitting text and wait for close.
        if _STATS_OPEN in (visible + pending):
            combined = visible + pending
            pre, _, rest = combined.partition(_STATS_OPEN)
            if pre[len(visible) :]:
                yield pre[len(visible) :], None
            visible = pre
            pending = _STATS_OPEN + rest
            if _STATS_CLOSE in pending:
                stats_raw = pending[len(_STATS_OPEN) : pending.index(_STATS_CLOSE)]
                yield "", _parse_stats(stats_raw)
                return
            continue

        # Keep a short holdback in case the open tag is split across chunks.
        if len(pending) > holdback:
            emit, pending = pending[:-holdback], pending[-holdback:]
            visible += emit
            yield emit, None

    # Stream ended without a complete stats block — flush leftovers.
    remainder = pending
    match = _STATS_RE.search(visible + remainder)
    if match:
        extra = (visible + remainder)[len(visible) : match.start()]
        if extra:
            yield extra, None
        yield "", _parse_stats(match.group(1))
        return

    if remainder:
        yield remainder, None
    yield "", None
