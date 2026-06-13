import json
from pathlib import Path

import pytest


def line(**kw):
    return json.dumps(kw)


def assistant(sid, mid, model, ts, *, inp=100, out=200, cread=1000, cw5=200,
              tools=None, cwd="/home/dev/proj", sidechain=False):
    content = [{"type": "tool_use", "name": t} for t in (tools or [])]
    return line(type="assistant", sessionId=sid, cwd=cwd, isSidechain=sidechain,
                gitBranch="main", version="2.0.0", timestamp=ts,
                message={"id": mid, "role": "assistant", "model": model,
                         "content": content,
                         "usage": {"input_tokens": inp, "output_tokens": out,
                                   "cache_read_input_tokens": cread,
                                   "cache_creation": {"ephemeral_5m_input_tokens": cw5,
                                                      "ephemeral_1h_input_tokens": 0}}})


def user(sid, ts, text="do a thing", cwd="/home/dev/proj", sidechain=False):
    return line(type="user", sessionId=sid, cwd=cwd, isSidechain=sidechain,
                timestamp=ts, message={"role": "user",
                                       "content": [{"type": "text", "text": text}]})


def tool_result(sid, ts, cwd="/home/dev/proj"):
    return line(type="user", sessionId=sid, cwd=cwd, isSidechain=False, timestamp=ts,
                message={"role": "user", "content": [{"type": "tool_result", "content": "ok"}]})


@pytest.fixture
def logdir(tmp_path: Path):
    """A project dir with one session exercising the tricky cases."""
    proj = tmp_path / "proj"
    proj.mkdir()
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    lines = [
        user(sid, "2026-06-01T09:00:00Z"),
        # streamed assistant: same id 3x, only final (out=300) should count
        assistant(sid, "m1", "claude-opus-4-8", "2026-06-01T09:00:10Z", out=50, tools=["Read"]),
        assistant(sid, "m1", "claude-opus-4-8", "2026-06-01T09:00:11Z", out=150, tools=["Read"]),
        assistant(sid, "m1", "claude-opus-4-8", "2026-06-01T09:00:12Z", out=300, tools=["Read", "Edit"]),
        tool_result(sid, "2026-06-01T09:00:13Z"),
        assistant(sid, "m2", "claude-sonnet-4-6", "2026-06-01T09:05:00Z", out=100, tools=["Bash"]),
        # unpriced local model
        assistant(sid, "m3", "qwen3-local", "2026-06-01T09:06:00Z", inp=500, out=500, cread=0, cw5=0),
    ]
    (proj / f"{sid}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path
