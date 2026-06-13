"""Aggregate normalized events into the full analytics model.

Everything the dashboard, the terminal report, the insight feed and Claude
Wrapped need is computed here, once, deterministically. No randomness, no
sampling: feed the same logs in and you get byte-identical numbers out.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .model import EDIT_TOOLS, IDLE_GAP_SECONDS, Event, Session, Usage
from .pricing import Pricing


def _peak_context(usage: Usage) -> int:
    return usage.input + usage.cache_read + usage.cache_write_5m + usage.cache_write_1h


def _active_seconds(timestamps: list) -> float:
    """Sum the time between consecutive events, ignoring idle gaps.

    A Claude Code session id can be resumed days later, so first→last wall
    clock wildly overstates working time. We instead sum the deltas between
    sorted consecutive events, counting a gap only if it's under the idle
    threshold (otherwise we assume you stepped away).
    """
    if len(timestamps) < 2:
        return 0.0
    ts = sorted(timestamps)
    total = 0.0
    for a, b in zip(ts, ts[1:]):
        gap = (b - a).total_seconds()
        if 0 < gap <= IDLE_GAP_SECONDS:
            total += gap
    return total


@dataclass
class Stats:
    generated_at: datetime
    pricing: Pricing
    sessions: List[Session] = field(default_factory=list)

    # Totals
    n_sessions: int = 0
    n_prompts: int = 0
    n_assistant_turns: int = 0
    usage: Usage = field(default_factory=Usage)
    cost: float = 0.0
    cache_savings: float = 0.0
    unpriced_tokens: int = 0
    web_search: int = 0
    web_fetch: int = 0

    first_day: Optional[date] = None
    last_day: Optional[date] = None
    active_days: int = 0

    # Breakdowns: name -> dict of aggregates
    by_project: Dict[str, dict] = field(default_factory=dict)
    by_model: Dict[str, dict] = field(default_factory=dict)
    by_tool: Dict[str, int] = field(default_factory=dict)
    by_day: Dict[str, dict] = field(default_factory=dict)  # "YYYY-MM-DD" -> agg
    by_hour: Dict[int, int] = field(default_factory=dict)  # local hour -> turns
    by_weekday: Dict[int, int] = field(default_factory=dict)  # 0=Mon

    # Leaderboards: list of small dicts
    longest_sessions: List[dict] = field(default_factory=list)
    most_expensive: List[dict] = field(default_factory=list)
    highest_output: List[dict] = field(default_factory=list)
    biggest_context: List[dict] = field(default_factory=list)

    @property
    def any_unpriced(self) -> bool:
        return self.unpriced_tokens > 0


def _short_id(sid: str) -> str:
    return sid[:8] if sid else "?"


def _session_card(s: Session) -> dict:
    return {
        "id": _short_id(s.id),
        "project": s.project,
        "model": s.primary_model or "unknown",
        "date": s.start.date().isoformat() if s.start else None,
        "duration_min": round(s.duration_seconds / 60.0, 1),
        "tokens": s.usage.total,
        "output": s.usage.output,
        "cost": round(s.cost, 4),
        "priced": s.priced,
        "peak_context": s.peak_context,
        "edits": s.edits,
        "prompts": s.prompts,
    }


def analyze(events: List[Event], pricing: Pricing, top_n: int = 10) -> Stats:
    st = Stats(generated_at=datetime.now(), pricing=pricing)

    sessions: Dict[str, Session] = {}
    project_mode: Dict[str, Counter] = defaultdict(Counter)
    ts_by_session: Dict[str, list] = defaultdict(list)

    proj_agg: Dict[str, dict] = defaultdict(lambda: _empty_agg())
    model_agg: Dict[str, dict] = defaultdict(lambda: _empty_agg())
    day_agg: Dict[str, dict] = defaultdict(lambda: _empty_agg())
    tool_counter: Counter = Counter()
    hour_counter: Counter = Counter()
    weekday_counter: Counter = Counter()

    for ev in events:
        s = sessions.get(ev.session_id)
        if s is None:
            s = Session(id=ev.session_id, project=ev.project, cwd=ev.cwd)
            sessions[ev.session_id] = s
        project_mode[ev.session_id][ev.project] += 1
        if ev.git_branch and not s.git_branch:
            s.git_branch = ev.git_branch

        ts = ev.timestamp
        if ts:
            ts_by_session[ev.session_id].append(ts)
            if s.start is None or ts < s.start:
                s.start = ts
            if s.end is None or ts > s.end:
                s.end = ts

        if ev.role == "user":
            if ev.is_prompt:
                s.prompts += 1
                st.n_prompts += 1
            continue

        # ---- assistant event ----
        s.assistant_turns += 1
        st.n_assistant_turns += 1
        s.usage = s.usage + ev.usage
        st.usage = st.usage + ev.usage
        st.web_search += ev.web_search
        st.web_fetch += ev.web_fetch

        model = ev.model or "unknown"
        s.models[model] = s.models.get(model, 0) + 1
        priced = pricing.is_priced(ev.model)
        cost = pricing.cost_of(ev.usage, ev.model)
        savings = pricing.cache_savings(ev.usage, ev.model)
        s.cost += cost
        st.cost += cost
        st.cache_savings += savings
        if not priced:
            s.priced = False
            st.unpriced_tokens += ev.usage.total

        pc = _peak_context(ev.usage)
        if pc > s.peak_context:
            s.peak_context = pc

        for t in ev.tools:
            s.tools[t] = s.tools.get(t, 0) + 1
            tool_counter[t] += 1
            if t in EDIT_TOOLS:
                s.edits += 1

        # breakdowns
        _add_usage(proj_agg[ev.project], ev.usage, cost)
        _add_usage(model_agg[model], ev.usage, cost)
        if ts:
            local = ts.astimezone()  # render trends in the user's local time
            day_key = local.date().isoformat()
            _add_usage(day_agg[day_key], ev.usage, cost)
            day_agg[day_key]["sessions"].add(ev.session_id)
            hour_counter[local.hour] += 1
            weekday_counter[local.weekday()] += 1

    # finalize session project (mode), active duration, per-project counts
    for sid, s in sessions.items():
        if project_mode[sid]:
            s.project = project_mode[sid].most_common(1)[0][0]
        s.active_seconds = _active_seconds(ts_by_session[sid])
        proj_agg[s.project]["sessions"].add(sid)

    st.sessions = list(sessions.values())
    st.n_sessions = len(sessions)

    # day range / active days
    day_keys = sorted(day_agg.keys())
    if day_keys:
        st.first_day = date.fromisoformat(day_keys[0])
        st.last_day = date.fromisoformat(day_keys[-1])
        st.active_days = len(day_keys)

    st.by_project = _finalize_named(proj_agg)
    st.by_model = _finalize_named(model_agg, pricing=pricing)
    st.by_tool = dict(tool_counter.most_common())
    st.by_day = {k: _finalize_agg(v) for k, v in day_agg.items()}
    st.by_hour = {h: hour_counter.get(h, 0) for h in range(24)}
    st.by_weekday = {d: weekday_counter.get(d, 0) for d in range(7)}

    # leaderboards
    cards = [(_session_card(s), s) for s in sessions.values()]
    st.longest_sessions = _top(cards, key=lambda c: c[1].duration_seconds, n=top_n,
                               guard=lambda c: c[1].duration_seconds > 0 and c[1].assistant_turns > 0)
    st.most_expensive = _top(cards, key=lambda c: c[1].cost, n=top_n,
                             guard=lambda c: c[1].cost > 0)
    st.highest_output = _top(cards, key=lambda c: c[1].usage.output, n=top_n,
                             guard=lambda c: c[1].usage.output > 0)
    st.biggest_context = _top(cards, key=lambda c: c[1].peak_context, n=top_n,
                              guard=lambda c: c[1].peak_context > 0)

    return st


def _empty_agg() -> dict:
    return {
        "input": 0, "output": 0, "cache_read": 0,
        "cache_write_5m": 0, "cache_write_1h": 0,
        "cost": 0.0, "sessions": set(),
    }


def _add_usage(agg: dict, u: Usage, cost: float) -> None:
    agg["input"] += u.input
    agg["output"] += u.output
    agg["cache_read"] += u.cache_read
    agg["cache_write_5m"] += u.cache_write_5m
    agg["cache_write_1h"] += u.cache_write_1h
    agg["cost"] += cost


def _finalize_agg(agg: dict) -> dict:
    total = (agg["input"] + agg["output"] + agg["cache_read"]
             + agg["cache_write_5m"] + agg["cache_write_1h"])
    out = {
        "input": agg["input"], "output": agg["output"],
        "cache_read": agg["cache_read"],
        "cache_write": agg["cache_write_5m"] + agg["cache_write_1h"],
        "tokens": total, "cost": round(agg["cost"], 4),
        "sessions": len(agg["sessions"]),
    }
    return out


def _finalize_named(aggs: Dict[str, dict], pricing: Optional[Pricing] = None) -> Dict[str, dict]:
    out = {}
    for name, agg in aggs.items():
        d = _finalize_agg(agg)
        if pricing is not None:
            d["priced"] = pricing.is_priced(name)
        out[name] = d
    # sort by tokens desc for stable, meaningful ordering
    return dict(sorted(out.items(), key=lambda kv: kv[1]["tokens"], reverse=True))


def _top(cards, key, n, guard):
    filtered = [c for c in cards if guard(c)]
    filtered.sort(key=key, reverse=True)
    return [c[0] for c in filtered[:n]]
