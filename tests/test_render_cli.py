import json
from pathlib import Path

from claudeinsights.analyze import analyze
from claudeinsights.cli import main
from claudeinsights.discover import find_session_files
from claudeinsights.parse import load_events
from claudeinsights.pricing import Pricing
from claudeinsights.render import build_payload, render_html
from claudeinsights.insights import build_insights
from claudeinsights.wrapped import build_wrapped


def _stats(logdir):
    return analyze(load_events(find_session_files(logdir)), Pricing())


def test_payload_shape(logdir):
    st = _stats(logdir)
    p = build_payload(st, str(logdir), 1)
    for key in ("meta", "totals", "by_project", "by_model", "by_tool",
                "daily", "by_hour", "by_weekday", "leaderboards", "insights", "wrapped"):
        assert key in p
    assert len(p["by_hour"]) == 24 and len(p["by_weekday"]) == 7
    assert p["meta"]["any_unpriced"] is True
    # payload must be JSON serializable
    json.dumps(p)


def test_render_embeds_data_and_one_script(logdir):
    st = _stats(logdir)
    html = render_html(build_payload(st, str(logdir), 1))
    assert "/*__CLAUDEINSIGHTS_DATA__*/null" not in html
    assert html.count("</script>") == 1
    assert "ClaudeInsights" in html


def test_render_escapes_script_close():
    # a project literally named "</script>" must not break out of the tag
    from claudeinsights.model import Usage
    st = analyze([], Pricing())
    payload = build_payload(st, "</script><h1>xss", 1)
    html = render_html(payload)
    # the only real closing tag is the template's own; the injected one is escaped
    assert html.count("</script>") == 1
    assert "</script><h1>" not in html        # breakout sequence neutralized
    assert "<\\/script>" in html               # injected close was escaped


def test_insights_and_wrapped_are_data_backed(logdir):
    st = _stats(logdir)
    ins = build_insights(st)
    assert all("text" in i and "icon" in i for i in ins)
    w = build_wrapped(st)
    assert w["sessions"] == 1
    assert "persona" in w and "title" in w["persona"] and "why" in w["persona"]


def test_cli_dashboard_end_to_end(logdir, tmp_path, capsys):
    out = tmp_path / "out.html"
    rc = main(["dashboard", "--logs", str(logdir), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert "ClaudeInsights" in out.read_text(encoding="utf-8")


def test_cli_report_and_json(logdir, tmp_path):
    assert main(["report", "--no-color", "--logs", str(logdir)]) == 0
    jf = tmp_path / "p.json"
    assert main(["json", "--logs", str(logdir), "-o", str(jf)]) == 0
    json.loads(jf.read_text(encoding="utf-8"))


def test_cli_missing_logs_returns_2(tmp_path):
    empty = tmp_path / "nope"
    assert main(["dashboard", "--logs", str(empty)]) == 2


def test_selftest_passes():
    from claudeinsights.selftest import run_selftest
    assert run_selftest() == 0
