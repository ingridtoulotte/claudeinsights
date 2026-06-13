"""ClaudeInsights — local-first analytics for Claude Code.

Turns the raw JSONL session logs that Claude Code writes to
``~/.claude/projects`` into a beautiful, self-contained analytics dashboard.

Everything runs on your machine. No network calls, no telemetry, no cloud.
Every number is computed deterministically from your own logs and is fully
auditable (see ``docs/METRICS.md``).
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
