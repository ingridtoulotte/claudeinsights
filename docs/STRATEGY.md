# Product strategy & landscape

> This document is the "why" behind ClaudeInsights — positioning, market gap,
> competitive analysis, and roadmap. The "what" and "how" live in the README,
> `METRICS.md`, and the code.

## Positioning

**ClaudeInsights — "See how you actually use Claude."**

The local-first analytics dashboard for Claude Code. It turns the JSONL session
logs Claude Code already writes into a beautiful, private, deterministic picture
of your AI workflow: where tokens go, what you spend, which projects dominate,
which models earn their cost, and how your habits change over time.

One-line elevator: *GitHub Insights + a cost tracker + Spotify Wrapped, for your
Claude Code history — running entirely on your machine.*

## The problem

Heavy Claude Code users accumulate hundreds of sessions and the equivalent of
real money in tokens, but the logs are opaque JSONL. Today you cannot easily
answer: *Where are my tokens going? Which project is expensive? Which model is
worth it? Am I getting more efficient? Is the cache actually helping?* You have
logs. You don't have visibility.

## Market gap

| Category | Examples | Gap ClaudeInsights fills |
|---|---|---|
| Raw logs | `~/.claude/projects/*.jsonl` | unreadable; no aggregation |
| Built-in `/cost`, `/context` | Claude Code | per-session only, no history, not visual, not shareable |
| Token/cost counters | small CLIs, `ccusage`-style tools | numbers only, no projects/tools/heatmap/insights, rarely shareable |
| Cloud AI dashboards | provider consoles | require sending data to a service; per-key not per-workflow; not Claude-Code-aware |
| APM/observability | Datadog et al. | built for prod telemetry, not a developer's personal AI history; heavy |

The gap: a **visual, shareable, local-first, Claude-Code-native** analytics layer
that needs zero setup and never phones home. That's the wedge.

## Why this can spread

1. **Wow on first run.** One command → a dashboard you want to screenshot.
2. **Claude Wrapped.** Inherently shareable; the persona card is built for social.
3. **Trust as a feature.** "100% local, zero deps, every number auditable" is a
   message developers actively repost.
4. **Zero friction.** No account, no server, no API key, no `node_modules`.
5. **Ecosystem timing.** The Claude Code tooling ecosystem is young; being the
   default analytics layer early compounds.

## Competitive differentiation (the moat)

- **Local + zero-dependency** beats anything cloud or heavy-stack on trust & setup.
- **Correctness most tools get wrong:** streaming-duplicate dedup and idle-trimmed
  session duration. Naive parsers over-count tokens and report 100-hour sessions.
- **Honest cost:** unpriced models are shown as unpriced, not faked.
- **Breadth + beauty:** projects, models, tools, MCP, heatmap, leaderboards,
  insights, and Wrapped in one self-contained file — not just a token total.

## MVP (shipped in v0.1)

Dashboard + terminal report + JSON export covering: KPIs, insight feed, activity
heatmap, daily trend, project/model/tool breakdowns, hour/weekday rhythm,
leaderboards, and Claude Wrapped. Tests + selftest + CI. This is already useful
on its own — no account, no follow-up install.

## Roadmap

**v0.2 — slice & compare**
- `--since` / `--until` / `--project` filters
- week-over-week and month-over-month comparison view
- export Wrapped as a standalone shareable PNG/card

**v0.3 — watch & report**
- `claudeinsights watch` to live-refresh while you work
- `claudeinsights weekly` → auto-generated Markdown digest (great for a cron)
- diff two periods ("this month vs last")

**v0.4 — ecosystem**
- pluggable metric/insight modules
- team mode: point at multiple exported log sets, aggregate anonymously
- optional `--anonymize` to scrub project names for sharing

**Long term — the standard layer**
- the thing every serious Claude Code user installs first
- a stable JSON schema other tools build on
- opt-in, fully local benchmarking of "efficiency over time"

## Non-goals

No telemetry. No cloud requirement. No fabricated or "AI-vibes" metrics. No heavy
front-end framework. We keep the install one command and the trust story intact.
