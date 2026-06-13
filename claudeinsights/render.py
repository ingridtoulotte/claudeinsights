"""Serialize :class:`Stats` to a JSON payload and bake it into the dashboard.

The dashboard is a single self-contained ``.html`` file: the data is embedded
as a JSON blob and all charts are drawn by a small amount of vanilla JS with
hand-rolled SVG. No CDN, no fonts fetched over the wire, no tracking pixels —
open it offline, on a plane, forever.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .analyze import Stats
from .insights import build_insights
from .util import pct
from .wrapped import build_wrapped

ASSETS = Path(__file__).parent / "assets"
TEMPLATE = ASSETS / "template.html"


def _named_list(named: dict, total_tokens: int) -> List[dict]:
    out = []
    for name, agg in named.items():
        out.append({
            "name": name,
            "tokens": agg["tokens"],
            "input": agg.get("input", 0),
            "output": agg["output"],
            "cache_read": agg.get("cache_read", 0),
            "cost": agg["cost"],
            "sessions": agg["sessions"],
            "priced": agg.get("priced", True),
            "share": round(pct(agg["tokens"], total_tokens), 1),
        })
    return out


def build_payload(st: Stats, root: str, n_files: int) -> dict:
    total_tokens = st.usage.total
    tool_total = max(1, sum(st.by_tool.values()))

    daily = []
    for k in sorted(st.by_day.keys()):
        a = st.by_day[k]
        daily.append({
            "date": k, "tokens": a["tokens"], "input": a["input"],
            "output": a["output"], "cost": a["cost"], "sessions": a["sessions"],
        })

    return {
        "meta": {
            "version": __import__("claudeinsights").__version__,
            "generated_at": st.generated_at.strftime("%Y-%m-%d %H:%M"),
            "root": root,
            "n_files": n_files,
            "any_unpriced": st.any_unpriced,
            "unpriced_tokens": st.unpriced_tokens,
        },
        "totals": {
            "sessions": st.n_sessions,
            "prompts": st.n_prompts,
            "assistant_turns": st.n_assistant_turns,
            "tokens": {
                "input": st.usage.input,
                "output": st.usage.output,
                "cache_read": st.usage.cache_read,
                "cache_write": st.usage.cache_write_5m + st.usage.cache_write_1h,
                "total": total_tokens,
            },
            "cost": round(st.cost, 4),
            "cache_savings": round(st.cache_savings, 4),
            "web_search": st.web_search,
            "web_fetch": st.web_fetch,
            "active_days": st.active_days,
            "first_day": st.first_day.isoformat() if st.first_day else None,
            "last_day": st.last_day.isoformat() if st.last_day else None,
        },
        "by_project": _named_list(st.by_project, total_tokens),
        "by_model": _named_list(st.by_model, total_tokens),
        "by_tool": [
            {"name": n, "count": c, "share": round(pct(c, tool_total), 1),
             "is_mcp": n.startswith("mcp__")}
            for n, c in st.by_tool.items()
        ],
        "daily": daily,
        "by_hour": [st.by_hour.get(h, 0) for h in range(24)],
        "by_weekday": [st.by_weekday.get(d, 0) for d in range(7)],
        "leaderboards": {
            "longest": st.longest_sessions,
            "expensive": st.most_expensive,
            "output": st.highest_output,
            "context": st.biggest_context,
        },
        "insights": build_insights(st),
        "wrapped": build_wrapped(st),
    }


def render_html(payload: dict, template_path: Path = TEMPLATE) -> str:
    template = template_path.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Guard against a literal </script> inside any string closing our tag early.
    blob = blob.replace("</", "<\\/")
    return template.replace("/*__CLAUDEINSIGHTS_DATA__*/null", blob)


def write_dashboard(st: Stats, out_path: Path, root: str, n_files: int) -> Path:
    payload = build_payload(st, root, n_files)
    html = render_html(payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
