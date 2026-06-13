"""Find Claude Code log files on disk, cross-platform.

Claude Code stores one JSONL file per session under
``~/.claude/projects/<project-slug>/<session-id>.jsonl``. The location is the
same on Windows, macOS and Linux; only the home directory differs, which
``Path.home()`` already handles for us.

You can point at a different root with ``--logs PATH`` (handy for testing
against the fixtures in this repo, or analyzing a colleague's exported logs).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, List, Optional


def default_root() -> Path:
    """The standard Claude Code projects directory for the current user."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(env) if env else Path.home() / ".claude"
    return base / "projects"


def resolve_root(custom: Optional[str]) -> Path:
    return Path(custom).expanduser() if custom else default_root()


def find_session_files(root: Path) -> List[Path]:
    """All *.jsonl session files under ``root``, sorted for determinism."""
    if not root.exists():
        return []
    if root.is_file():  # allow pointing directly at a single .jsonl
        return [root]
    return sorted(root.rglob("*.jsonl"))


def iter_lines(path: Path) -> Iterator[str]:
    """Yield raw lines from a JSONL file, tolerant of encoding quirks."""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield line
