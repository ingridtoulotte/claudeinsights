"""Pretty terminal summary — `claudeinsights report`.

ANSI colours, degrades to plain text when output isn't a TTY or --no-color is
passed. No dependencies (no colorama): modern Windows Terminal, macOS and
Linux terminals all understand these escapes.
"""

from __future__ import annotations

import sys

from .analyze import Stats
from .insights import build_insights
from .util import human_int, human_money, human_duration, pct


class C:
    def __init__(self, on: bool):
        self.on = on

    def _w(self, code, s):
        return f"\033[{code}m{s}\033[0m" if self.on else s

    def b(self, s): return self._w("1", s)
    def dim(self, s): return self._w("2", s)
    def acc(self, s): return self._w("38;5;215", s)   # warm orange
    def teal(self, s): return self._w("38;5;80", s)
    def good(self, s): return self._w("38;5;114", s)
    def warn(self, s): return self._w("38;5;221", s)


def _bar(frac: float, width: int = 22) -> str:
    filled = int(round(frac * width))
    return "█" * filled + "·" * (width - filled)


def print_report(st: Stats, use_color: bool = True, stream=None) -> None:
    stream = stream or sys.stdout
    color = use_color and getattr(stream, "isatty", lambda: False)()
    c = C(color)
    p = lambda s="": print(s, file=stream)

    tk = st.usage
    period = "all time"
    if st.first_day and st.last_day:
        period = f"{st.first_day} → {st.last_day}"

    p()
    p(c.acc("  ◐ ClaudeInsights") + c.dim("  — See how you actually use Claude."))
    p(c.dim(f"  {period}  ·  {st.n_sessions} sessions  ·  {st.active_days} active days"))
    p()

    rows = [
        ("Total spend", c.good(human_money(st.cost))
            + (c.dim(f"  (cache saved {human_money(st.cache_savings)})") if st.cache_savings > 0.01 else "")),
        ("Tokens", c.b(human_int(tk.total)) + c.dim(f"  in {human_int(tk.input)} · out {human_int(tk.output)} · cache-read {human_int(tk.cache_read)}")),
        ("Prompts", c.b(human_int(st.n_prompts)) + c.dim(f"  ·  {human_int(st.n_assistant_turns)} assistant turns")),
        ("Tool calls", c.b(human_int(sum(st.by_tool.values())))),
    ]
    for label, val in rows:
        p(f"  {label:<14} {val}")

    if st.any_unpriced:
        p()
        p("  " + c.warn(f"⚠ {human_int(st.unpriced_tokens)} tokens from unpriced models — spend is a lower bound."))

    def top_block(title, items, namer, valuer, total):
        p()
        p("  " + c.b(title))
        if not items:
            p(c.dim("    (none)")); return
        mx = max(1, max(valuer(i) for i in items))
        for it in items[:6]:
            v = valuer(it)
            p(f"    {c.teal(_bar(v / mx))}  {namer(it):<26.26} {c.dim(human_int(v))}"
              + c.dim(f"  {pct(v, total):.0f}%"))

    proj = list(st.by_project.items())
    top_block("Projects (by tokens)", proj, lambda kv: kv[0], lambda kv: kv[1]["tokens"], tk.total or 1)
    mods = list(st.by_model.items())
    top_block("Models (by tokens)", mods, lambda kv: kv[0], lambda kv: kv[1]["tokens"], tk.total or 1)
    tools = list(st.by_tool.items())
    top_block("Tools (by calls)", tools, lambda kv: kv[0], lambda kv: kv[1], sum(st.by_tool.values()) or 1)

    if st.longest_sessions:
        p()
        p("  " + c.b("Longest sessions"))
        for i, s in enumerate(st.longest_sessions[:5], 1):
            p(f"    {c.dim(str(i)+'.')} {human_duration(s['duration_min']*60):>8}  "
              f"{s['project']:<24.24} {c.dim(s['date'] or '')}")

    insights = build_insights(st)
    if insights:
        p()
        p("  " + c.b("Insights"))
        for i in insights[:6]:
            clean = i["text"].replace("**", "").replace("`", "")
            p(f"    {i['icon']}  {clean}")
    p()
