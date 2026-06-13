# Architecture

ClaudeInsights is a small, boring, deliberately dependency-free Python package.
Boring is a feature: it means it installs in one command, runs anywhere Python
runs, and you can read the whole thing in an afternoon.

```
                ~/.claude/projects/**/*.jsonl   (your logs, read-only)
                              │
        discover.py  ─────────┤  find files, stream lines
                              │
        parse.py     ─────────┤  JSONL → Event[]  (dedup streamed msgs,
                              │                     classify prompts/tools)
                              │
        analyze.py   ─────────┤  Event[] → Stats   (sessions, breakdowns,
                              │                      heatmap, leaderboards)
                              │
        pricing.py   ─────────┤  deterministic $ from public rates
                              │
   ┌──────────────────────────┼───────────────────────────┐
   │                          │                            │
 insights.py              wrapped.py                    render.py
 (data-backed feed)    (shareable summary)          Stats → JSON payload
                                                          │
                                                    assets/template.html
                                                    (self-contained dashboard)
                                                          │
                                              claudeinsights.html  +  terminal.py
```

## Data flow, module by module

- **`discover.py`** — locates `~/.claude/projects` (honours `CLAUDE_CONFIG_DIR`),
  enumerates `*.jsonl`, streams lines. `--logs PATH` overrides the root.
- **`model.py`** — the clean dataclasses (`Usage`, `Event`, `Session`) everything
  else speaks in. Raw JSON never escapes the parser.
- **`parse.py`** — the only file that touches raw JSON shapes. Handles streaming
  dedup, schema drift, timestamp parsing, prompt vs tool-result classification.
- **`pricing.py`** — substring-matched price table + the exact cost formula.
  Unknown models are unpriced, never guessed.
- **`analyze.py`** — single pass over events producing the whole `Stats` object:
  totals, per-project / per-model / per-tool / per-day breakdowns, hour & weekday
  histograms, active-duration, and the four leaderboards.
- **`insights.py` / `wrapped.py`** — pure functions over `Stats`.
- **`render.py`** — serializes `Stats` to a JSON payload and bakes it into
  `assets/template.html` by replacing a single placeholder. All charts are
  hand-rolled SVG/CSS in vanilla JS — no Chart.js, no D3, no CDN.
- **`terminal.py`** — the `report` command's ANSI summary.
- **`cli.py`** — argparse front door; forces UTF-8 stdout on Windows.

## Design decisions

**Zero runtime dependencies.** Pure standard library. No supply chain, no
version conflicts, no `node_modules`. `pip install claudeinsights` and you're done.

**Single self-contained HTML output.** The dashboard embeds its own data and
draws its own charts. No server, no build step, no external requests when you
open it. Email it, commit it, open it on a plane in 2030 — it still works.

**Local-first & private by construction.** The tool only ever *reads* your logs
and *writes* the one output file you name. There is no network code in the
package at all — grep for `socket`, `urllib`, `http`; you won't find them.

**Deterministic.** No randomness, no wall-clock-dependent logic except the
"generated at" stamp. Same logs in → identical analytics out (enforced by tests).

**Cross-platform.** Pathlib everywhere, UTF-8 forced on Windows consoles, local
timezone used for human-facing trends. CI runs the suite on Linux, macOS and
Windows across Python 3.8–3.12.

## Testing

- `python -m claudeinsights selftest` — end-to-end smoke + invariant checks on a
  synthetic log, no real data needed (also runs in CI).
- `pytest` — unit + integration tests (pricing math, streaming dedup, active
  duration, payload shape, `</script>` injection safety, CLI exit codes,
  determinism).
- `examples/generate_sample.py` — reproducible synthetic dataset used for the
  demo dashboard and the README screenshots (so no private data is ever shipped).
