# Metrics reference — where every number comes from

ClaudeInsights has one rule: **no number appears that you can't trace back to
your own logs.** No estimates, no sampling, no black-box "AI score". This page
documents the source field and formula behind every metric, so you can audit
any figure on the dashboard.

All data is read from the JSONL session files Claude Code writes to
`~/.claude/projects/<project>/<session-id>.jsonl`. One JSON object per line.

---

## Source fields we read

| Field (per line) | Used for |
|---|---|
| `type` (`assistant` / `user`) | classifying turns; everything else is ignored |
| `message.id` | **deduplicating streamed assistant messages** |
| `message.model` | model attribution & pricing |
| `message.usage.input_tokens` | input tokens |
| `message.usage.output_tokens` | output tokens |
| `message.usage.cache_read_input_tokens` | cache hits |
| `message.usage.cache_creation.ephemeral_5m_input_tokens` | 5-minute cache writes |
| `message.usage.cache_creation.ephemeral_1h_input_tokens` | 1-hour cache writes |
| `message.usage.server_tool_use.web_search_requests` / `web_fetch_requests` | server tool counts |
| `message.content[].type == "tool_use"` → `.name` | tool usage |
| `cwd` | project name (last path segment) |
| `timestamp` | trends, heatmap, active duration |
| `sessionId` | grouping into sessions |
| `isSidechain` | excluding subagent prompts from the human-prompt count |

Lines that aren't `assistant`/`user` turns (snapshots, summaries, meta records)
are skipped, not guessed at.

---

## The two correctness traps (and how we handle them)

### 1. Streaming duplicates
A single assistant response is written to the log on **several lines that share
the same `message.id`** as it streams in. Only the final line carries complete
token usage. Naively summing every line **double- or triple-counts tokens**.

> We deduplicate by `message.id`, keeping the line with the largest total usage
> and the union of its `tool_use` blocks. Verified by `selftest` and
> `tests/test_parse.py::test_streaming_dedup`.

### 2. Resumed sessions inflate duration
A `sessionId` can be resumed hours or days later, so first-event→last-event wall
clock can read "101 hours" for a session you worked on across a week.

> **Session duration = active time:** we sort a session's events and sum the
> gaps between consecutive ones, counting a gap only if it's ≤ 30 minutes
> (`IDLE_GAP_SECONDS`). Longer gaps are treated as "you stepped away". The raw
> wall-clock span is kept separately as `span_seconds`.

---

## Cost model

Cost is computed per assistant message and summed. Rates are **public Anthropic
list prices**, USD per 1,000,000 tokens:

| Model (matched by substring) | Input | Output |
|---|---|---|
| `opus` | $15.00 | $75.00 |
| `sonnet` | $3.00 | $15.00 |
| `haiku` | $1.00 | $5.00 |

Cache multipliers applied to the **base input rate** (Anthropic prompt-caching pricing):

| Token kind | Multiplier |
|---|---|
| cache **read** (hit) | ×0.10 |
| 5-minute cache **write** | ×1.25 |
| 1-hour cache **write** | ×2.00 |

```
message_cost =
      input_tokens         × input_rate
    + output_tokens        × output_rate
    + cache_read_tokens    × input_rate × 0.10
    + cache_write_5m_tokens× input_rate × 1.25
    + cache_write_1h_tokens× input_rate × 2.00
```

**Unpriced models.** Local models (Ollama, etc.), the `<synthetic>` placeholder,
and any model we don't have a public price for contribute **$0** to spend. Their
tokens still count toward usage, and the dashboard shows a banner noting the
spend figure is a lower bound. We never invent a price.

You can override or extend the table with `--pricing prices.json`
(`{"opus":[15,75], "my-model":[2,8]}`, per 1M tokens).

**Cache savings** = `cache_read_tokens × input_rate × 0.90` — the difference
between the discounted cache-read price (0.10×) and paying full input price.

---

## Derived metrics

| Metric | Definition |
|---|---|
| **Sessions** | distinct `sessionId` values |
| **Prompts** | `user` lines containing a text block, excluding tool results and sidechains |
| **Assistant turns** | deduplicated assistant messages |
| **Tokens (total)** | input + output + cache read + cache writes |
| **Cache reads % of context** | `cache_read / (cache_read + input)` |
| **Active days** | distinct local-date days with ≥1 assistant turn |
| **Peak context** | max(`input + cache_read + cache_writes`) over a session's messages |
| **Edits** | count of `Write` / `Edit` / `MultiEdit` / `NotebookEdit` tool calls |
| **Project** | most common `cwd` last-segment among a session's events |
| **Heatmap intensity** | daily token totals, bucketed into 5 quantile levels |
| **By hour / weekday** | assistant turns grouped by **local** time of `timestamp` |

## Leaderboards

| Board | Sort key |
|---|---|
| Longest | active duration (idle-trimmed) |
| Most expensive | message cost (priced models only) |
| Most output | output tokens |
| Biggest context | peak context tokens |

## Insight feed

Every insight is a sentence containing the figure it's based on, emitted only
when the data supports it (e.g. week-over-week deltas require ≥14 days of span).
See `claudeinsights/insights.py` — there is no hidden scoring.

## Claude Wrapped persona

A deterministic label from your behaviour, **always shown with its supporting
stat**: Night Owl (≥40% of turns 10pm–6am), Builder (≥8 edits/session),
Explorer (≥35% of tool calls are Reads), Marathoner (avg active session ≥30 min),
else All-Rounder. It's a nickname with evidence, not a score.

---

## Reproducibility

Parsing and analysis are pure and deterministic: the same logs always produce
identical numbers (`tests/test_analyze.py::test_determinism`,
`selftest` "analytics payload is deterministic"). Nothing is read from the
network; nothing is written anywhere except the single HTML/JSON file you ask for.
