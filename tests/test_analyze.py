import json

from claudeinsights.analyze import analyze
from claudeinsights.discover import find_session_files
from claudeinsights.parse import load_events
from claudeinsights.pricing import Pricing


def _stats(logdir):
    return analyze(load_events(find_session_files(logdir)), Pricing())


def test_totals(logdir):
    st = _stats(logdir)
    assert st.n_sessions == 1
    assert st.n_prompts == 1
    assert st.n_assistant_turns == 3  # m1 (deduped), m2, m3
    # output: 300 (m1 final) + 100 (m2) + 500 (m3) = 900
    assert st.usage.output == 900
    # input: 100 + 100 + 500 = 700
    assert st.usage.input == 700


def test_unpriced_tracking(logdir):
    st = _stats(logdir)
    # qwen turn: input 500 + output 500 = 1000 unpriced tokens
    assert st.unpriced_tokens == 1000
    assert st.any_unpriced is True


def test_cost_only_priced_models(logdir):
    st = _stats(logdir)
    pr = Pricing()
    # opus m1: in100*15e-6 + out300*75e-6 + cread1000*1.5e-6 + cw5 200*15e-6*1.25
    opus = 100*15e-6 + 300*75e-6 + 1000*1.5e-6 + 200*15e-6*1.25
    # sonnet m2: in100*3e-6 + out100*15e-6 + cread1000*0.3e-6 + cw5 200*3e-6*1.25
    sonnet = 100*3e-6 + 100*15e-6 + 1000*0.3e-6 + 200*3e-6*1.25
    assert abs(st.cost - (opus + sonnet)) < 1e-9  # qwen contributes 0


def test_breakdowns(logdir):
    st = _stats(logdir)
    assert "proj" in st.by_project
    assert set(st.by_model) == {"claude-opus-4-8", "claude-sonnet-4-6", "qwen3-local"}
    assert st.by_tool["Read"] == 1 and st.by_tool["Edit"] == 1 and st.by_tool["Bash"] == 1
    assert st.by_model["qwen3-local"]["priced"] is False


def test_active_duration_ignores_idle(tmp_path):
    # two events 10 hours apart -> idle gap, active time should be ~0
    proj = tmp_path / "p"; proj.mkdir()
    sid = "s1"
    lines = [
        json.dumps({"type": "assistant", "sessionId": sid, "cwd": "/x",
                    "timestamp": "2026-06-01T09:00:00Z",
                    "message": {"id": "a", "model": "claude-opus-4-8",
                                "usage": {"input_tokens": 1, "output_tokens": 1}}}),
        json.dumps({"type": "assistant", "sessionId": sid, "cwd": "/x",
                    "timestamp": "2026-06-01T19:00:00Z",
                    "message": {"id": "b", "model": "claude-opus-4-8",
                                "usage": {"input_tokens": 1, "output_tokens": 1}}}),
    ]
    (proj / "s1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    st = analyze(load_events(find_session_files(tmp_path)), Pricing())
    s = st.sessions[0]
    assert s.span_seconds == 10 * 3600        # wall clock is 10h
    assert s.active_seconds == 0.0            # but gap > idle threshold -> 0 active


def test_determinism(logdir):
    a = _stats(logdir)
    b = _stats(logdir)
    assert a.usage.total == b.usage.total
    assert abs(a.cost - b.cost) < 1e-12
    assert a.by_tool == b.by_tool
