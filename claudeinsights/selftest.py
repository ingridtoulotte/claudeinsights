"""Built-in sanity checks — `claudeinsights selftest`.

Runs the whole pipeline (parse → analyze → price → render) against a tiny
synthetic log and asserts the invariants that matter most: streaming
deduplication, deterministic cost, unpriced-model handling, and that the
dashboard actually renders with the data embedded. No real logs required, so
this doubles as a smoke test in CI.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from .analyze import analyze
from .parse import load_events, parse_file
from .pricing import Pricing
from .render import build_payload, render_html
from .model import Usage

# A synthetic session: one assistant message that "streams" across 3 lines
# sharing an id (only the last/full usage must count), one local-model turn
# (unpriced), one user prompt, and a tool call.
_SID = "11111111-2222-3333-4444-555555555555"


def _line(**kw):
    return json.dumps(kw)


def _make_log() -> str:
    base = {"sessionId": _SID, "cwd": "/home/dev/myproj", "isSidechain": False}
    lines = []
    # user prompt
    lines.append(_line(type="user", timestamp="2026-06-01T10:00:00Z",
                       message={"content": [{"type": "text", "text": "build me a thing"}]}, **base))
    # streamed assistant message, same id, growing usage; final = the truth
    for out in (10, 50, 120):
        lines.append(_line(type="assistant", timestamp="2026-06-01T10:00:05Z",
                           message={"id": "msg_A", "model": "claude-opus-4-8",
                                    "content": [{"type": "tool_use", "name": "Edit"}],
                                    "usage": {"input_tokens": 100, "output_tokens": out,
                                              "cache_read_input_tokens": 1000,
                                              "cache_creation": {"ephemeral_5m_input_tokens": 200,
                                                                 "ephemeral_1h_input_tokens": 0}}}, **base))
    # an unpriced local model turn
    lines.append(_line(type="assistant", timestamp="2026-06-01T10:01:00Z",
                       message={"id": "msg_B", "model": "qwen3.5-local",
                                "content": [{"type": "tool_use", "name": "Read"}],
                                "usage": {"input_tokens": 500, "output_tokens": 500}}, **base))
    return "\n".join(lines) + "\n"


def _check(cond: bool, label: str, fails: list) -> None:
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        fails.append(label)


def run_selftest() -> int:
    fails: list = []
    print("ClaudeInsights selftest\n")

    # ---- pricing unit checks ----
    pr = Pricing()
    u = Usage(input=1_000_000, output=1_000_000)
    _check(abs(pr.cost_of(u, "claude-opus-4-8") - (15 + 75)) < 1e-9,
           "opus base price = $15 in + $75 out per 1M", fails)
    _check(abs(pr.cost_of(u, "claude-sonnet-4-6") - (3 + 15)) < 1e-9,
           "sonnet base price = $3 in + $15 out per 1M", fails)
    cache = Usage(cache_read=1_000_000)
    _check(abs(pr.cost_of(cache, "claude-opus-4-8") - 1.5) < 1e-9,
           "opus cache read = 0.10x input ($1.50/1M)", fails)
    _check(pr.cost_of(Usage(input=1000), "qwen3.5-local") == 0.0,
           "unknown model is unpriced ($0)", fails)
    _check(pr.cost_of(Usage(input=1000), "<synthetic>") == 0.0,
           "synthetic model is unbilled", fails)

    # ---- parse + analyze on synthetic log ----
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "myproj"
        proj.mkdir()
        (proj / f"{_SID}.jsonl").write_text(_make_log(), encoding="utf-8")
        events = load_events([proj / f"{_SID}.jsonl"])
        st = analyze(events, pr)

        # streaming dedup: opus output counted ONCE at final 120, not 10+50+120
        _check(st.usage.output == 120 + 500, "streaming dupes deduped (output=620 not 680)", fails)
        _check(st.usage.input == 100 + 500, "input tokens summed once per message", fails)
        _check(st.usage.cache_read == 1000, "cache read counted once", fails)
        _check(st.n_prompts == 1, "one human prompt detected", fails)
        _check(st.n_assistant_turns == 2, "two assistant turns (deduped)", fails)
        _check(st.n_sessions == 1, "one session", fails)
        _check(st.by_tool.get("Edit") == 1 and st.by_tool.get("Read") == 1, "tools counted", fails)
        _check(st.unpriced_tokens == 1000, "unpriced tokens tracked (qwen 500+500)", fails)

        # cost: only opus priced. input100*15e-6 + out120*75e-6 + cacheRead1000*1.5e-6 + write200*18.75e-6
        expect = 100 * 15e-6 + 120 * 75e-6 + 1000 * 1.5e-6 + 200 * 15e-6 * 1.25
        _check(abs(st.cost - expect) < 1e-9, f"deterministic cost = ${expect:.6f}", fails)

        _check(st.by_project.get("myproj") is not None, "project derived from cwd", fails)
        _check(st.active_days == 1, "active days = 1", fails)

        # determinism: same input → identical payload
        p1 = build_payload(st, td, 1)
        st2 = analyze(load_events([proj / f"{_SID}.jsonl"]), pr)
        p2 = build_payload(st2, td, 1)
        p1.pop("meta"); p2.pop("meta")  # generated_at differs
        _check(json.dumps(p1, sort_keys=True) == json.dumps(p2, sort_keys=True),
               "analytics payload is deterministic", fails)

        # render: data embedded, placeholder gone, no premature </script>
        html = render_html(build_payload(st, td, 1))
        _check("/*__CLAUDEINSIGHTS_DATA__*/null" not in html, "data placeholder replaced", fails)
        _check('"sessions":1' in html.replace(" ", ""), "session count embedded in html", fails)
        _check("</script>" in html and html.count("</script>") == 1, "exactly one closing script tag", fails)

    print()
    if fails:
        print(f"FAILED: {len(fails)} check(s) failed.")
        return 1
    print("ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run_selftest())
