"""Normalized data model.

Raw Claude Code JSONL is messy: streaming duplicates, synthetic messages,
mixed schemas across CLI versions. Everything in this module is the *clean*
shape the rest of the codebase works with. Parsing lives in ``parse.py``;
this file only defines the records and a couple of pure helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Usage:
    """Token counts for a single assistant message.

    Mirrors the fields Claude Code records in ``message.usage``. We split
    cache writes into 5-minute and 1-hour buckets because Anthropic prices
    them differently (1.25x vs 2x the base input rate).
    """

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0

    @property
    def total(self) -> int:
        return (
            self.input
            + self.output
            + self.cache_read
            + self.cache_write_5m
            + self.cache_write_1h
        )

    @property
    def billable_input(self) -> int:
        """Tokens that count as 'context fed to the model' this message."""
        return self.input + self.cache_read + self.cache_write_5m + self.cache_write_1h

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input=self.input + other.input,
            output=self.output + other.output,
            cache_read=self.cache_read + other.cache_read,
            cache_write_5m=self.cache_write_5m + other.cache_write_5m,
            cache_write_1h=self.cache_write_1h + other.cache_write_1h,
        )

    def as_dict(self) -> Dict[str, int]:
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write_5m": self.cache_write_5m,
            "cache_write_1h": self.cache_write_1h,
        }


@dataclass
class Event:
    """One normalized log line we care about (an assistant or user turn)."""

    session_id: str
    project: str
    cwd: str
    timestamp: Optional[datetime]
    role: str  # "assistant" | "user"
    model: Optional[str] = None
    usage: Usage = field(default_factory=Usage)
    message_id: Optional[str] = None
    is_sidechain: bool = False
    is_prompt: bool = False  # a real human prompt (not a tool result)
    tools: List[str] = field(default_factory=list)
    web_search: int = 0
    web_fetch: int = 0
    git_branch: Optional[str] = None
    version: Optional[str] = None


@dataclass
class Session:
    """All events for one Claude Code session id, aggregated."""

    id: str
    project: str
    cwd: str = ""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    models: Dict[str, int] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    cost: float = 0.0
    priced: bool = True  # False if any model in the session is unpriced
    prompts: int = 0
    assistant_turns: int = 0
    tools: Dict[str, int] = field(default_factory=dict)
    edits: int = 0  # Write + Edit + NotebookEdit calls
    peak_context: int = 0  # max (input + cache_read + cache_write) on one msg
    git_branch: Optional[str] = None
    active_seconds: float = 0.0  # see analyze; excludes idle gaps

    @property
    def span_seconds(self) -> float:
        """Wall-clock first→last event. Includes idle time (sessions resume)."""
        if self.start and self.end:
            return max(0.0, (self.end - self.start).total_seconds())
        return 0.0

    @property
    def duration_seconds(self) -> float:
        """Active working time (idle gaps removed). The number we report."""
        return self.active_seconds

    @property
    def primary_model(self) -> Optional[str]:
        if not self.models:
            return None
        return max(self.models.items(), key=lambda kv: kv[1])[0]


# Tools we count as "produced a change to the codebase".
EDIT_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}

# Gap (seconds) between consecutive events above which we treat the session as
# idle/paused rather than actively working. 30 minutes is a common dev-tool
# default for "active time" and keeps resumed sessions from inflating duration.
IDLE_GAP_SECONDS = 30 * 60
