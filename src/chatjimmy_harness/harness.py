"""Suite runner and benchmark helpers for ChatJimmy."""

from __future__ import annotations

import json
import shutil
import statistics
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chatjimmy_harness.client import ChatJimmy, ChatResponse, Stats


@dataclass
class CaseResult:
    id: str
    prompt: str
    text: str
    ok: bool
    passed_checks: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    error: str | None = None
    stats: dict[str, Any] | None = None
    latency_s: float = 0.0
    tool_calls: int = 0
    turns: int = 0
    agent: bool = False


@dataclass
class SuiteResult:
    name: str
    cases: list[CaseResult]
    started_at: float
    finished_at: float

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.ok)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if not c.ok)

    @property
    def total(self) -> int:
        return len(self.cases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "duration_s": self.finished_at - self.started_at,
            "cases": [asdict(c) for c in self.cases],
        }


@dataclass
class BenchSample:
    index: int
    latency_s: float
    text_len: int
    stats: dict[str, Any] | None
    error: str | None = None


@dataclass
class BenchResult:
    prompt: str
    concurrency: int
    samples: list[BenchSample]
    started_at: float
    finished_at: float

    def summary(self) -> dict[str, Any]:
        ok = [s for s in self.samples if s.error is None]
        latencies = [s.latency_s for s in ok]
        decode_rates = [
            s.stats["decode_rate"]
            for s in ok
            if s.stats and s.stats.get("decode_rate") is not None
        ]
        decode_tokens = [
            s.stats["decode_tokens"]
            for s in ok
            if s.stats and s.stats.get("decode_tokens") is not None
        ]
        ttfts = [
            s.stats["ttft"] for s in ok if s.stats and s.stats.get("ttft") is not None
        ]

        def _stats(vals: list[float]) -> dict[str, float] | None:
            if not vals:
                return None
            return {
                "min": min(vals),
                "max": max(vals),
                "mean": statistics.mean(vals),
                "p50": statistics.median(vals),
                "p95": _percentile(vals, 95),
            }

        return {
            "prompt": self.prompt,
            "runs": len(self.samples),
            "ok": len(ok),
            "errors": len(self.samples) - len(ok),
            "wall_s": self.finished_at - self.started_at,
            "latency_s": _stats(latencies),
            "decode_rate_tok_s": _stats(decode_rates),
            "decode_tokens": _stats([float(x) for x in decode_tokens]),
            "ttft_s": _stats(ttfts),
        }


def _percentile(vals: list[float], pct: float) -> float:
    if not vals:
        return 0.0
    ordered = sorted(vals)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _stats_dict(stats: Stats | None) -> dict[str, Any] | None:
    return asdict(stats) if stats else None


def load_suite(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        cases = []
        for i, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            item = json.loads(line)
            if "id" not in item:
                item["id"] = f"case-{i}"
            if "prompt" not in item and "messages" not in item:
                raise ValueError(f"{path}:{i}: need prompt or messages")
            cases.append(item)
        return {"name": path.stem, "cases": cases}

    data = json.loads(text)
    if isinstance(data, list):
        return {"name": path.stem, "cases": data}
    if "cases" not in data:
        raise ValueError(f"{path}: suite JSON must include a 'cases' array")
    data.setdefault("name", path.stem)
    return data


def check_case(
    text: str,
    case: dict[str, Any],
    *,
    tool_calls: int = 0,
    workspace: Path | None = None,
) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []

    for needle in case.get("expect_contains") or []:
        label = f"contains:{needle!r}"
        (passed if needle.lower() in text.lower() else failed).append(label)

    for needle in case.get("expect_not_contains") or []:
        label = f"not_contains:{needle!r}"
        (passed if needle.lower() not in text.lower() else failed).append(label)

    min_chars = case.get("min_chars")
    if min_chars is not None:
        label = f"min_chars:{min_chars}"
        (passed if len(text) >= int(min_chars) else failed).append(label)

    max_chars = case.get("max_chars")
    if max_chars is not None:
        label = f"max_chars:{max_chars}"
        (passed if len(text) <= int(max_chars) else failed).append(label)

    min_tools = case.get("min_tool_calls")
    if min_tools is not None:
        label = f"min_tool_calls:{min_tools}"
        (passed if tool_calls >= int(min_tools) else failed).append(label)

    for rel in case.get("expect_file_contains") or []:
        # [{ "path": "a.py", "contains": "foo" }, ...] or ["path::needle"]
        if isinstance(rel, str) and "::" in rel:
            path_s, needle = rel.split("::", 1)
            spec = {"path": path_s, "contains": needle}
        elif isinstance(rel, dict):
            spec = rel
        else:
            failed.append(f"file_contains:bad_spec:{rel!r}")
            continue
        label = f"file_contains:{spec.get('path')!r}:{spec.get('contains')!r}"
        if workspace is None:
            failed.append(label)
            continue
        target = workspace / str(spec.get("path", ""))
        needle = str(spec.get("contains", ""))
        try:
            body = target.read_text(encoding="utf-8")
            (passed if needle in body else failed).append(label)
        except OSError:
            failed.append(label)

    # No assertions → pass if we got any non-empty response.
    if not passed and not failed:
        label = "non_empty"
        (passed if text.strip() else failed).append(label)

    return passed, failed


def _resolve_workspace(raw: str | Path | None, *, base: Path, override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    if raw is None or raw == "":
        return base.resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def run_suite(
    client: ChatJimmy,
    suite: dict[str, Any],
    *,
    model: str | None = None,
    top_k: int | None = None,
    system_prompt: str | None = None,
    workspace: Path | None = None,
    suite_dir: Path | None = None,
) -> SuiteResult:
    from chatjimmy_harness.agent import run_agent

    name = suite.get("name", "suite")
    default_system = system_prompt if system_prompt is not None else suite.get("system_prompt", "")
    default_model = model or suite.get("model", "llama3.1-8B")
    default_top_k = top_k if top_k is not None else int(suite.get("top_k", 8))
    base = (suite_dir or Path.cwd()).resolve()
    default_workspace = _resolve_workspace(
        suite.get("workspace"), base=base, override=workspace
    )
    suite_tools = suite.get("tools")
    suite_agent = bool(suite.get("agent", False))
    max_turns = int(suite.get("max_turns", 8))
    isolate = bool(suite.get("isolate", True))

    started = time.time()
    results: list[CaseResult] = []

    for i, case in enumerate(suite.get("cases") or [], start=1):
        case_id = str(case.get("id") or f"case-{i}")
        prompt = case.get("prompt")
        messages = case.get("messages")
        if messages is None:
            if prompt is None:
                results.append(
                    CaseResult(
                        id=case_id,
                        prompt="",
                        text="",
                        ok=False,
                        error="case needs prompt or messages",
                    )
                )
                continue
            messages = [{"role": "user", "content": prompt}]
            display_prompt = prompt
        else:
            display_prompt = prompt or json.dumps(messages)

        case_system = case.get("system_prompt", default_system)
        case_model = case.get("model", default_model)
        case_top_k = int(case.get("top_k", default_top_k))
        use_agent = bool(case.get("agent", suite_agent))
        case_tools = case.get("tools", suite_tools)
        case_ws = (
            _resolve_workspace(case.get("workspace"), base=base)
            if case.get("workspace")
            else default_workspace
        )
        case_max_turns = int(case.get("max_turns", max_turns))
        case_isolate = bool(case.get("isolate", isolate))

        t0 = time.time()
        try:
            if use_agent:
                if prompt is not None:
                    agent_prompt, agent_messages = prompt, None
                else:
                    agent_prompt, agent_messages = "", list(messages)
                work_ws = case_ws
                tmp_root: tempfile.TemporaryDirectory[str] | None = None
                if case_isolate:
                    tmp_root = tempfile.TemporaryDirectory(prefix="cjh-ws-")
                    work_ws = Path(tmp_root.name) / case_ws.name
                    shutil.copytree(case_ws, work_ws)
                try:
                    agent_result = run_agent(
                        client,
                        agent_prompt,
                        workspace=work_ws,
                        tools=case_tools,
                        system_prompt=case_system or "",
                        model=case_model,
                        top_k=case_top_k,
                        max_turns=case_max_turns,
                        messages=agent_messages,
                    )
                    latency = time.time() - t0
                    text = agent_result.text
                    passed, failed = check_case(
                        text,
                        case,
                        tool_calls=agent_result.tool_calls,
                        workspace=work_ws,
                    )
                    if agent_result.error and not case.get("allow_max_turns"):
                        failed.append(f"agent_error:{agent_result.error}")
                    results.append(
                        CaseResult(
                            id=case_id,
                            prompt=display_prompt,
                            text=text,
                            ok=not failed,
                            passed_checks=passed,
                            failed_checks=failed,
                            error=agent_result.error,
                            latency_s=latency,
                            tool_calls=agent_result.tool_calls,
                            turns=agent_result.turns,
                            agent=True,
                        )
                    )
                finally:
                    if tmp_root is not None:
                        tmp_root.cleanup()
            else:
                resp: ChatResponse = client.chat(
                    messages=messages,
                    model=case_model,
                    system_prompt=case_system or "",
                    top_k=case_top_k,
                )
                latency = time.time() - t0
                passed, failed = check_case(resp.text, case)
                results.append(
                    CaseResult(
                        id=case_id,
                        prompt=display_prompt,
                        text=resp.text,
                        ok=not failed,
                        passed_checks=passed,
                        failed_checks=failed,
                        stats=_stats_dict(resp.stats),
                        latency_s=latency,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - surface any API/network failure
            results.append(
                CaseResult(
                    id=case_id,
                    prompt=display_prompt,
                    text="",
                    ok=False,
                    error=str(exc),
                    latency_s=time.time() - t0,
                    agent=use_agent,
                )
            )

    return SuiteResult(
        name=name,
        cases=results,
        started_at=started,
        finished_at=time.time(),
    )


def run_bench(
    client: ChatJimmy,
    prompt: str,
    *,
    runs: int = 5,
    model: str = "llama3.1-8B",
    system_prompt: str = "",
    top_k: int = 8,
) -> BenchResult:
    started = time.time()
    samples: list[BenchSample] = []
    messages = [{"role": "user", "content": prompt}]

    for i in range(runs):
        t0 = time.time()
        try:
            resp = client.chat(
                messages=messages,
                model=model,
                system_prompt=system_prompt,
                top_k=top_k,
            )
            samples.append(
                BenchSample(
                    index=i,
                    latency_s=time.time() - t0,
                    text_len=len(resp.text),
                    stats=_stats_dict(resp.stats),
                )
            )
        except Exception as exc:  # noqa: BLE001
            samples.append(
                BenchSample(
                    index=i,
                    latency_s=time.time() - t0,
                    text_len=0,
                    stats=None,
                    error=str(exc),
                )
            )

    return BenchResult(
        prompt=prompt,
        concurrency=1,
        samples=samples,
        started_at=started,
        finished_at=time.time(),
    )
