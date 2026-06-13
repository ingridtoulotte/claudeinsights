"""Turn raw Claude Code JSONL into clean :class:`Event` records.

The two things that make this non-trivial, both confirmed against real logs:

1. **Streaming duplicates.** A single assistant message id can appear on
   several consecutive lines as the response streams in. Only the final line
   carries the complete usage. Summing every line double-counts tokens, so we
   deduplicate by ``message.id`` and keep the line with the largest usage.

2. **Schema drift.** Lines come in many shapes (prompts, tool results, file
   attachments, snapshots, summaries, synthetic placeholders). We pick out the
   assistant/user turns we understand and ignore the rest rather than guess.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .discover import iter_lines
from .model import Event, Usage


def parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp into an aware UTC datetime, tolerantly."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Fall back to the common fixed format without fractional seconds.
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def project_label(cwd: Optional[str], fallback_slug: str) -> str:
    """Human-friendly project name derived from the session's working dir."""
    if cwd:
        norm = cwd.replace("\\", "/").rstrip("/")
        tail = norm.rsplit("/", 1)[-1]
        return tail if tail else cwd  # e.g. "C:" -> keep full "C:\"
    return fallback_slug


def _usage_from(raw: dict) -> Usage:
    cc = raw.get("cache_creation") or {}
    write_5m = int(cc.get("ephemeral_5m_input_tokens", 0) or 0)
    write_1h = int(cc.get("ephemeral_1h_input_tokens", 0) or 0)
    if not write_5m and not write_1h:
        # Older logs only have the rolled-up figure; treat as 5-minute writes.
        write_5m = int(raw.get("cache_creation_input_tokens", 0) or 0)
    return Usage(
        input=int(raw.get("input_tokens", 0) or 0),
        output=int(raw.get("output_tokens", 0) or 0),
        cache_read=int(raw.get("cache_read_input_tokens", 0) or 0),
        cache_write_5m=write_5m,
        cache_write_1h=write_1h,
    )


def _tools_and_web(content, usage_raw: dict):
    tools: List[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = block.get("name")
                if name:
                    tools.append(name)
    stu = usage_raw.get("server_tool_use") or {}
    web_search = int(stu.get("web_search_requests", 0) or 0)
    web_fetch = int(stu.get("web_fetch_requests", 0) or 0)
    return tools, web_search, web_fetch


def _is_human_prompt(content) -> bool:
    """True when a user line is an actual typed prompt, not a tool result."""
    if isinstance(content, str):
        return content.strip() != ""
    if isinstance(content, list):
        has_text = any(
            isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
            for b in content
        )
        return has_text
    return False


def parse_file(path: Path) -> List[Event]:
    fallback_slug = path.parent.name
    assistant: Dict[str, Event] = {}
    assistant_totals: Dict[str, int] = {}
    others: List[Event] = []
    anon_counter = 0

    for line in iter_lines(path):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue

        rtype = obj.get("type")
        if rtype not in ("assistant", "user"):
            continue  # snapshots, summaries, meta lines, etc.

        msg = obj.get("message") or {}
        cwd = obj.get("cwd")
        ev = Event(
            session_id=obj.get("sessionId") or fallback_slug,
            project=project_label(cwd, fallback_slug),
            cwd=cwd or "",
            timestamp=parse_timestamp(obj.get("timestamp")),
            role=rtype,
            is_sidechain=bool(obj.get("isSidechain")),
            git_branch=obj.get("gitBranch"),
            version=obj.get("version"),
        )

        if rtype == "assistant":
            usage_raw = msg.get("usage") or {}
            ev.model = msg.get("model")
            ev.usage = _usage_from(usage_raw)
            ev.tools, ev.web_search, ev.web_fetch = _tools_and_web(
                msg.get("content"), usage_raw
            )
            ev.message_id = msg.get("id")

            if ev.message_id:
                prev = assistant.get(ev.message_id)
                if prev is None:
                    assistant[ev.message_id] = ev
                    assistant_totals[ev.message_id] = ev.usage.total
                else:
                    # Merge streamed chunks: keep richest usage, union tools.
                    merged_tools = list(dict.fromkeys(prev.tools + ev.tools))
                    if ev.usage.total >= assistant_totals[ev.message_id]:
                        ev.tools = merged_tools
                        assistant[ev.message_id] = ev
                        assistant_totals[ev.message_id] = ev.usage.total
                    else:
                        prev.tools = merged_tools
            else:
                anon_counter += 1
                assistant[f"__anon_{anon_counter}"] = ev
        else:  # user
            ev.is_prompt = _is_human_prompt(msg.get("content")) and not ev.is_sidechain
            others.append(ev)

    return list(assistant.values()) + others


def load_events(files: List[Path]) -> List[Event]:
    events: List[Event] = []
    for path in files:
        events.extend(parse_file(path))
    return events
