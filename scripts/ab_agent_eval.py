#!/usr/bin/env python3
"""A/B live eval: legacy agent loop vs current harness config.

Usage (from repo root, with PYTHONPATH set by caller):
  python scripts/ab_agent_eval.py --label current --trials 3 --out /tmp/cj-ab/current.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "examples" / "agent_tools.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=20.0, help="Seconds between trials")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Import after PYTHONPATH is set by the shell wrapper.
    from chatjimmy_harness.client import ChatJimmy
    from chatjimmy_harness.harness import load_suite, run_suite

    client = ChatJimmy(timeout=90)
    suite = load_suite(SUITE)
    trials = []
    t0 = time.time()
    for i in range(1, args.trials + 1):
        if i > 1 and args.sleep > 0:
            print(f"[{args.label}] sleeping {args.sleep:.0f}s before trial {i}…", flush=True)
            time.sleep(args.sleep)
        # Light 429 backoff: up to 3 suite attempts
        result = None
        for attempt in range(1, 4):
            started = time.time()
            result = run_suite(client, suite, suite_dir=SUITE.parent)
            hit_429 = any(
                (c.error or "").startswith("429")
                or any(str(f).startswith("agent_error:429") for f in c.failed_checks)
                for c in result.cases
            )
            if not hit_429:
                break
            wait = 30 * attempt
            print(f"[{args.label}] 429 on trial {i} attempt {attempt}; sleep {wait}s", flush=True)
            time.sleep(wait)
        assert result is not None
        trial = {
            "trial": i,
            "label": args.label,
            "passed": result.passed,
            "failed": result.failed,
            "total": result.total,
            "duration_s": time.time() - started,
            "cases": [
                {
                    "id": c.id,
                    "ok": c.ok,
                    "tool_calls": c.tool_calls,
                    "turns": c.turns,
                    "latency_s": c.latency_s,
                    "passed_checks": c.passed_checks,
                    "failed_checks": c.failed_checks,
                    "error": c.error,
                    "text_preview": (c.text or "")[:240],
                }
                for c in result.cases
            ],
        }
        trials.append(trial)
        print(
            f"[{args.label}] trial {i}/{args.trials}: "
            f"{result.passed}/{result.total} in {trial['duration_s']:.1f}s",
            flush=True,
        )
        for c in trial["cases"]:
            mark = "PASS" if c["ok"] else "FAIL"
            print(
                f"  {mark} {c['id']} tools={c['tool_calls']} turns={c['turns']} "
                f"fail={c['failed_checks'] or '-'} err={c['error'] or '-'}",
                flush=True,
            )

    case_ids = [c["id"] for c in trials[0]["cases"]] if trials else []
    by_case = {}
    for cid in case_ids:
        oks = [t["cases"][i]["ok"] for t in trials for i, c in enumerate(t["cases"]) if c["id"] == cid]
        # simpler:
        oks = []
        for t in trials:
            for c in t["cases"]:
                if c["id"] == cid:
                    oks.append(c["ok"])
        by_case[cid] = {
            "pass_rate": sum(oks) / len(oks) if oks else 0.0,
            "passes": sum(oks),
            "trials": len(oks),
        }

    summary = {
        "label": args.label,
        "suite": str(SUITE),
        "trials": args.trials,
        "wall_s": time.time() - t0,
        "suite_pass_rate": (
            sum(1 for t in trials if t["failed"] == 0) / len(trials) if trials else 0.0
        ),
        "case_pass_rate": by_case,
        "mean_tools": {
            cid: (
                sum(
                    c["tool_calls"]
                    for t in trials
                    for c in t["cases"]
                    if c["id"] == cid
                )
                / max(1, sum(1 for t in trials for c in t["cases"] if c["id"] == cid))
            )
            for cid in case_ids
        },
        "runs": trials,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"label": args.label, "suite_pass_rate": summary["suite_pass_rate"], "case_pass_rate": by_case}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
