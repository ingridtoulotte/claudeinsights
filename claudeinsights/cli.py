"""Command-line entry point.

    claudeinsights                 generate claudeinsights.html from ~/.claude
    claudeinsights --open          ...and open it in your browser
    claudeinsights report          print a summary in the terminal
    claudeinsights json -o out.json   dump the raw analytics payload
    claudeinsights selftest        run built-in sanity checks (no logs needed)
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from . import __version__
from .analyze import analyze
from .discover import find_session_files, resolve_root
from .parse import load_events
from .pricing import Pricing


def _common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--logs", metavar="PATH",
                    help="Claude Code projects dir (default: ~/.claude/projects)")
    ap.add_argument("--pricing", metavar="FILE",
                    help="JSON price overrides: {\"opus\":[15,75], ...} per 1M tokens")
    ap.add_argument("--top", type=int, default=10, help="leaderboard length (default 10)")


def _load(args):
    root = resolve_root(args.logs)
    files = find_session_files(root)
    pricing = Pricing.load(getattr(args, "pricing", None))
    events = load_events(files)
    stats = analyze(events, pricing, top_n=getattr(args, "top", 10))
    return root, files, stats


def cmd_dashboard(args) -> int:
    from .render import write_dashboard
    root, files, stats = _load(args)
    if not files:
        print(f"No .jsonl logs found under {root}", file=sys.stderr)
        print("Pass --logs PATH to point at your Claude Code projects directory.", file=sys.stderr)
        return 2
    out = Path(args.out or "claudeinsights.html")
    write_dashboard(stats, out, str(root), len(files))
    n = stats.n_sessions
    print(f"✓ Analyzed {n} sessions from {len(files)} log files.")
    print(f"✓ Dashboard written to {out.resolve()}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


def cmd_report(args) -> int:
    from .terminal import print_report
    root, files, stats = _load(args)
    if not files:
        print(f"No .jsonl logs found under {root}", file=sys.stderr)
        return 2
    print_report(stats, use_color=not args.no_color)
    return 0


def cmd_json(args) -> int:
    from .render import build_payload
    root, files, stats = _load(args)
    payload = build_payload(stats, str(root), len(files))
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"✓ Payload written to {Path(args.out).resolve()}")
    else:
        print(text)
    return 0


def cmd_selftest(args) -> int:
    from .selftest import run_selftest
    return run_selftest()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="claudeinsights",
        description="See how you actually use Claude. Local-first analytics for Claude Code.")
    ap.add_argument("--version", action="version", version=f"claudeinsights {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    d = sub.add_parser("dashboard", help="generate the HTML dashboard (default)")
    _common(d)
    d.add_argument("-o", "--out", metavar="FILE", help="output html (default claudeinsights.html)")
    d.add_argument("--open", action="store_true", help="open the dashboard when done")
    d.set_defaults(func=cmd_dashboard)

    r = sub.add_parser("report", help="print a terminal summary")
    _common(r)
    r.add_argument("--no-color", action="store_true")
    r.set_defaults(func=cmd_report)

    j = sub.add_parser("json", help="dump the analytics payload as JSON")
    _common(j)
    j.add_argument("-o", "--out", metavar="FILE")
    j.set_defaults(func=cmd_json)

    s = sub.add_parser("selftest", help="run built-in sanity checks")
    s.set_defaults(func=cmd_selftest)

    return ap


def _force_utf8() -> None:
    # Windows consoles default to cp1252 and choke on our box-drawing/emoji
    # output. Make stdout/stderr UTF-8 so the tool looks the same everywhere.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def main(argv=None) -> int:
    _force_utf8()
    ap = build_parser()
    args, _unknown = ap.parse_known_args(argv)
    if not getattr(args, "cmd", None):
        # default to dashboard with default flags
        ns = ap.parse_args(["dashboard"] + (argv or sys.argv[1:]))
        return ns.func(ns)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
