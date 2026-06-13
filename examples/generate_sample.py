#!/usr/bin/env python3
"""Generate a realistic, **synthetic** Claude Code log set for demos.

Why synthetic? Real ``~/.claude/projects`` logs contain private prompts, file
paths and project names — none of which belong in a public repo or a README
screenshot. This script fabricates believable-but-fake sessions with the exact
on-disk schema Claude Code uses, so the demo dashboard looks real while leaking
nothing. It's fully seeded, so re-running produces byte-identical logs.

    python examples/generate_sample.py
    python -m claudeinsights dashboard --logs examples/sample-logs -o examples/demo.html
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(20260613)

OUT = Path(__file__).parent / "sample-logs"

PROJECTS = [
    ("api-gateway",     "/home/dev/api-gateway",   0.34),
    ("web-dashboard",   "/home/dev/web-dashboard", 0.28),
    ("ml-pipeline",     "/home/dev/ml-pipeline",   0.22),
    ("infra",           "/home/dev/infra",         0.16),
]
MODELS = [("claude-opus-4-8", 0.30), ("claude-sonnet-4-6", 0.55),
          ("claude-haiku-4-5-20251001", 0.15)]
TOOLS = [("Read", 0.34), ("Edit", 0.17), ("Bash", 0.15), ("Grep", 0.10),
         ("Write", 0.08), ("Glob", 0.06), ("TodoWrite", 0.05),
         ("WebSearch", 0.02), ("mcp__github__create_pr", 0.015),
         ("mcp__postgres__query", 0.015)]
PROMPTS = [
    "fix the failing auth test", "add pagination to the users endpoint",
    "why is this query slow?", "refactor the retry logic",
    "write tests for the parser", "review this diff for bugs",
    "set up the CI workflow", "explain this stack trace",
]


def weighted(choices):
    r = random.random()
    acc = 0.0
    for name, w in choices:
        acc += w
        if r <= acc:
            return name
    return choices[-1][0]


def make_usage(model: str, big: bool):
    scale = 2.4 if "opus" in model else (1.0 if "sonnet" in model else 0.5)
    base_in = int(random.randint(40, 260) * scale)
    out = int(random.randint(120, 1400) * scale * (2.2 if big else 1.0))
    cache_read = int(random.randint(8000, 60000) * scale)
    cw5 = int(random.randint(1500, 14000) * scale)
    return {
        "input_tokens": base_in,
        "output_tokens": out,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cw5,
        "cache_creation": {"ephemeral_5m_input_tokens": cw5, "ephemeral_1h_input_tokens": 0},
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
    }


def main():
    if OUT.exists():
        for f in OUT.glob("*.jsonl"):
            f.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    start = datetime(2026, 5, 15, tzinfo=timezone.utc)
    sid_counter = 0
    files_written = 0

    for day in range(30):
        date = start + timedelta(days=day)
        # weekends are quieter
        is_weekend = date.weekday() >= 5
        n_sessions = random.randint(0, 2) if is_weekend else random.randint(1, 4)
        for _ in range(n_sessions):
            sid_counter += 1
            sid = f"{sid_counter:08d}-0000-4000-8000-{day:012d}"
            project = weighted([(p[0], p[2]) for p in PROJECTS])
            cwd = next(p[1] for p in PROJECTS if p[0] == project)
            model = weighted(MODELS)
            hour = random.choice([9, 10, 11, 13, 14, 15, 16, 17, 20, 21, 22])
            t = date.replace(hour=hour, minute=random.randint(0, 59))
            lines = []
            n_turns = random.randint(3, 22)
            for turn in range(n_turns):
                # user prompt occasionally
                if turn == 0 or random.random() < 0.25:
                    lines.append({
                        "type": "user", "sessionId": sid, "cwd": cwd,
                        "isSidechain": False, "gitBranch": "main",
                        "timestamp": t.isoformat().replace("+00:00", "Z"),
                        "message": {"role": "user",
                                    "content": [{"type": "text", "text": random.choice(PROMPTS)}]},
                    })
                    t += timedelta(seconds=random.randint(5, 40))
                # assistant turn, streamed across 1-3 lines sharing an id
                mid = f"msg_{sid_counter}_{turn}"
                usage = make_usage(model, big=(turn == n_turns - 1 and random.random() < 0.3))
                tools = []
                for _ in range(random.randint(0, 3)):
                    tools.append({"type": "tool_use", "name": weighted(TOOLS)})
                chunks = random.randint(1, 3)
                for ci in range(chunks):
                    u = dict(usage)
                    if ci < chunks - 1:  # partial streamed usage
                        u = dict(usage); u["output_tokens"] = int(usage["output_tokens"] * (ci + 1) / chunks)
                    lines.append({
                        "type": "assistant", "sessionId": sid, "cwd": cwd,
                        "isSidechain": False, "gitBranch": "main", "version": "2.0.0",
                        "timestamp": t.isoformat().replace("+00:00", "Z"),
                        "message": {"id": mid, "role": "assistant", "model": model,
                                    "content": tools, "usage": u},
                    })
                t += timedelta(seconds=random.randint(8, 180))

            path = OUT / f"{sid}.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
            files_written += 1

    print(f"Wrote {files_written} synthetic session logs to {OUT}")


if __name__ == "__main__":
    main()
