"""Claude Wrapped — the shareable, Spotify-Wrapped-style year (or all-time)
summary. Every headline number comes straight from :class:`Stats`.

The "persona" is a deterministic label derived from your actual behaviour
(when you work, how much you edit, which tools you lean on). It always ships
with the stat that earned it, so it's a nickname, not a black-box score.
"""

from __future__ import annotations

from typing import Optional

from .analyze import Stats
from .util import human_duration, human_int, human_money, pct


def _persona(st: Stats) -> dict:
    turns = max(1, st.n_assistant_turns)
    night = sum(st.by_hour.get(h, 0) for h in (22, 23, 0, 1, 2, 3, 4, 5))
    night_share = pct(night, turns)
    read_calls = st.by_tool.get("Read", 0)
    total_tools = max(1, sum(st.by_tool.values()))
    read_share = pct(read_calls, total_tools)
    total_edits = sum(s.edits for s in st.sessions)
    edits_per_session = total_edits / max(1, st.n_sessions)
    durs = [s.duration_seconds for s in st.sessions if s.duration_seconds > 0]
    avg_dur = sum(durs) / len(durs) if durs else 0.0

    if night_share >= 40:
        return {"title": "The Night Owl", "emoji": "🦉",
                "why": f"{night_share:.0f}% of your turns happened between 10pm and 6am."}
    if edits_per_session >= 8:
        return {"title": "The Builder", "emoji": "🔨",
                "why": f"You averaged {edits_per_session:.1f} file edits per session."}
    if read_share >= 35:
        return {"title": "The Explorer", "emoji": "🔍",
                "why": f"{read_share:.0f}% of your tool calls were Reads — you scout before you act."}
    if avg_dur >= 30 * 60:
        return {"title": "The Marathoner", "emoji": "🏃",
                "why": f"Your average session ran {human_duration(avg_dur)}."}
    return {"title": "The All-Rounder", "emoji": "🎛️",
            "why": "Balanced across reading, editing and running — no single mode dominates."}


def build_wrapped(st: Stats) -> dict:
    period = "all time"
    if st.first_day and st.last_day:
        period = (f"{st.first_day.isoformat()} → {st.last_day.isoformat()}"
                  if st.first_day != st.last_day else st.first_day.isoformat())

    top_projects = [
        {"name": n, "tokens": a["tokens"], "share": round(pct(a["tokens"], st.usage.total), 1)}
        for n, a in list(st.by_project.items())[:3]
    ]

    fav_model: Optional[str] = None
    model_turns = {m: a for m, a in st.by_model.items()}
    if model_turns:
        # favourite = most assistant turns; we track turns implicitly via sessions
        fav_model = max(st.by_model.items(),
                        key=lambda kv: kv[1]["tokens"])[0]

    biggest_day = None
    if st.by_day:
        bk, bv = max(st.by_day.items(), key=lambda kv: kv[1]["tokens"])
        biggest_day = {"date": bk, "tokens": bv["tokens"], "sessions": bv["sessions"]}

    longest = st.longest_sessions[0] if st.longest_sessions else None
    total_edits = sum(s.edits for s in st.sessions)

    return {
        "period": period,
        "persona": _persona(st),
        "sessions": st.n_sessions,
        "prompts": st.n_prompts,
        "tokens": st.usage.total,
        "tokens_h": human_int(st.usage.total),
        "output": st.usage.output,
        "output_h": human_int(st.usage.output),
        "cost": round(st.cost, 2),
        "cost_h": human_money(st.cost),
        "cache_savings_h": human_money(st.cache_savings),
        "active_days": st.active_days,
        "edits": total_edits,
        "tool_calls": sum(st.by_tool.values()),
        "top_projects": top_projects,
        "favorite_model": fav_model,
        "biggest_day": biggest_day,
        "longest_session": longest,
        "any_unpriced": st.any_unpriced,
    }
