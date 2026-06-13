"""The Insight Feed — interesting facts, every one backed by a real number.

Rule: an insight is only emitted when the data actually supports it, and the
sentence always contains the figure it is based on. No vibes, no black-box
"AI score", nothing you can't trace back to ``docs/METRICS.md``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

from .analyze import Stats
from .util import human_int, human_money, pct


def _week_tokens(st: Stats, start: date, end: date) -> int:
    total = 0
    for k, agg in st.by_day.items():
        d = date.fromisoformat(k)
        if start <= d <= end:
            total += agg["tokens"]
    return total


def build_insights(st: Stats) -> List[dict]:
    out: List[dict] = []

    def add(icon: str, text: str) -> None:
        out.append({"icon": icon, "text": text})

    total_tokens = st.usage.total

    # 1. Dominant project
    if st.by_project and total_tokens:
        name, agg = next(iter(st.by_project.items()))
        share = pct(agg["tokens"], total_tokens)
        if share >= 1:
            add("📂", f"**{name}** consumed {share:.0f}% of all tokens "
                      f"({human_int(agg['tokens'])} across {agg['sessions']} sessions).")

    # 2. Busiest day
    if st.by_day:
        bk, bv = max(st.by_day.items(), key=lambda kv: kv[1]["tokens"])
        add("🔥", f"Your busiest day was **{bk}** — {human_int(bv['tokens'])} tokens "
                  f"over {bv['sessions']} session(s).")

    # 3. Top model by spend
    spendy = [(m, a) for m, a in st.by_model.items() if a["cost"] > 0]
    if spendy:
        m, a = max(spendy, key=lambda kv: kv[1]["cost"])
        share = pct(a["cost"], st.cost)
        add("💰", f"Most of your spend went to **{m}**: {human_money(a['cost'])} "
                  f"({share:.0f}% of {human_money(st.cost)}).")

    # 4. Cache savings
    if st.cache_savings >= 0.01:
        add("⚡", f"Prompt caching saved you about **{human_money(st.cache_savings)}** "
                  f"— {human_int(st.usage.cache_read)} tokens served from cache instead "
                  f"of being re-sent at full price.")

    # 5. Cache read share of context
    if st.usage.input + st.usage.cache_read > 0:
        ratio = pct(st.usage.cache_read, st.usage.input + st.usage.cache_read)
        if ratio >= 5:
            add("♻️", f"{ratio:.0f}% of the context fed to Claude came from cache "
                      f"rather than fresh input — that's the cache doing its job.")

    # 6. Most-used tool
    if st.by_tool:
        tname, tcount = next(iter(st.by_tool.items()))
        add("🛠️", f"Your most-used tool is **{tname}** with {human_int(tcount)} calls.")

    # 7. MCP usage
    mcp_calls = sum(c for t, c in st.by_tool.items() if t.startswith("mcp__"))
    if mcp_calls:
        add("🔌", f"You made {human_int(mcp_calls)} MCP tool calls "
                  f"across {sum(1 for t in st.by_tool if t.startswith('mcp__'))} MCP tool(s).")

    # 8. Week over week (needs two full weeks of span)
    if st.last_day and st.first_day and (st.last_day - st.first_day).days >= 13:
        this_end = st.last_day
        this_start = this_end - timedelta(days=6)
        last_end = this_start - timedelta(days=1)
        last_start = last_end - timedelta(days=6)
        this_w = _week_tokens(st, this_start, this_end)
        last_w = _week_tokens(st, last_start, last_end)
        if last_w > 0 and this_w > 0:
            delta = pct(this_w - last_w, last_w)
            arrow = "down" if delta < 0 else "up"
            add("📈", f"Last 7 days vs the week before: token use is **{arrow} "
                      f"{abs(delta):.0f}%** ({human_int(this_w)} vs {human_int(last_w)}).")

    # 9. Biggest single context window
    if st.biggest_context:
        top = st.biggest_context[0]
        add("🧠", f"Your largest single context window hit "
                  f"**{human_int(top['peak_context'])} tokens** "
                  f"in session `{top['id']}` ({top['project']}).")

    # 10. Edits produced
    total_edits = sum(s.edits for s in st.sessions)
    if total_edits and st.n_sessions:
        add("✏️", f"You triggered {human_int(total_edits)} file edits/writes "
                  f"— about {total_edits / st.n_sessions:.1f} per session.")

    return out
