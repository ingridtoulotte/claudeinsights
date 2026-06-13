from datetime import timezone

from claudeinsights.discover import find_session_files
from claudeinsights.parse import (load_events, parse_file, parse_timestamp,
                                   project_label, _is_human_prompt, _usage_from)


def test_parse_timestamp_variants():
    assert parse_timestamp("2026-06-01T09:00:00Z").tzinfo == timezone.utc
    assert parse_timestamp("2026-06-01T09:00:00.123Z").hour == 9
    assert parse_timestamp("2026-06-01T09:00:00+02:00").astimezone(timezone.utc).hour == 7
    assert parse_timestamp(None) is None
    assert parse_timestamp("not a date") is None


def test_project_label():
    assert project_label("/home/dev/api-gateway", "slug") == "api-gateway"
    assert project_label("C:\\Users\\me\\proj", "slug") == "proj"
    assert project_label("C:\\", "slug") == "C:"  # drive root collapses to "C:"
    assert project_label(None, "slug") == "slug"


def test_usage_cache_breakdown():
    u = _usage_from({"input_tokens": 10, "output_tokens": 20,
                     "cache_read_input_tokens": 30,
                     "cache_creation": {"ephemeral_5m_input_tokens": 5,
                                        "ephemeral_1h_input_tokens": 7}})
    assert (u.input, u.output, u.cache_read) == (10, 20, 30)
    assert (u.cache_write_5m, u.cache_write_1h) == (5, 7)


def test_usage_rolled_up_cache_falls_back_to_5m():
    u = _usage_from({"cache_creation_input_tokens": 42})
    assert u.cache_write_5m == 42 and u.cache_write_1h == 0


def test_human_prompt_detection():
    assert _is_human_prompt("hello") is True
    assert _is_human_prompt([{"type": "text", "text": "hi"}]) is True
    assert _is_human_prompt([{"type": "tool_result", "content": "x"}]) is False
    assert _is_human_prompt("") is False


def test_streaming_dedup(logdir):
    files = find_session_files(logdir)
    events = load_events(files)
    asst = [e for e in events if e.role == "assistant"]
    # m1 appeared 3x streamed -> one event with final out=300 and unioned tools
    m1 = [e for e in asst if e.message_id == "m1"]
    assert len(m1) == 1
    assert m1[0].usage.output == 300
    assert set(m1[0].tools) == {"Read", "Edit"}


def test_prompt_vs_tool_result(logdir):
    events = load_events(find_session_files(logdir))
    prompts = [e for e in events if e.role == "user" and e.is_prompt]
    assert len(prompts) == 1  # the tool_result line is not a prompt
