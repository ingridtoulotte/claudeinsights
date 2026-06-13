<div align="center">

# ◐ ClaudeInsights

### See how you actually use Claude.

**The local-first analytics dashboard for Claude Code.**
Turn your raw session logs into a beautiful, private, deterministic picture of your AI workflow — in one command.

[![CI](https://github.com/ingridtoulotte/claudeinsights/actions/workflows/ci.yml/badge.svg)](https://github.com/ingridtoulotte/claudeinsights/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Dependencies: zero](https://img.shields.io/badge/dependencies-0-brightgreen.svg)
![100% local](https://img.shields.io/badge/data-100%25%20local-orange.svg)
![No telemetry](https://img.shields.io/badge/telemetry-none-success.svg)

```bash
pipx install git+https://github.com/ingridtoulotte/claudeinsights
claudeinsights --open
```

<img src="docs/img/hero.png" alt="ClaudeInsights dashboard — KPI cards and insight feed" width="100%">

</div>

---

You spend real money and hundreds of hours in Claude Code. Yet your history is a
pile of opaque JSONL files. **ClaudeInsights reads those logs and answers the
questions you actually have** — where your tokens go, what you spend, which
projects dominate, which models earn their cost, and how your habits change over
time — without a single byte leaving your machine.

> **Before:** you have logs.&nbsp;&nbsp;&nbsp;**After:** you have visibility.

## ✨ What you get

- 💰 **Real cost** — exact spend by project, model, and day, using public Anthropic prices. Plus how much **prompt caching saved you**.
- 🔢 **Token analytics** — input / output / cache reads / cache writes, trends over time, efficiency.
- 📂 **Project & model breakdowns** — where your context and dollars actually go.
- 🛠️ **Tool usage** — Read / Edit / Bash / Grep / Write / MCP, ranked and trended.
- 📅 **Activity heatmap** — your GitHub-style calendar of coding intensity.
- 🏆 **Session leaderboards** — longest, most expensive, highest-output, biggest context.
- 💡 **Insight feed** — plain-English facts, each backed by a real number.
- 🎁 **Claude Wrapped** — a shareable, Spotify-Wrapped-style summary with your usage *persona*.

All rendered into **one self-contained HTML file**. No server, no build step, no CDN — open it offline, forever.

## 📸 The dashboard

<img src="docs/img/charts.png" alt="Activity heatmap and daily token trend" width="100%">

<img src="docs/img/breakdown.png" alt="Project, model and tool breakdowns" width="100%">

### 🎁 Claude Wrapped — built to screenshot

<img src="docs/img/wrapped.png" alt="Claude Wrapped summary card with usage persona" width="100%">

<sub>Screenshots are from the bundled <a href="examples/">synthetic demo dataset</a> — your real data never leaves your machine, and we never ship it here either.</sub>

## 🚀 Install

```bash
# recommended — isolated, always on PATH
pipx install git+https://github.com/ingridtoulotte/claudeinsights

# or plain pip
pip install git+https://github.com/ingridtoulotte/claudeinsights
```

Pure Python, **zero dependencies**, so installing from source is instant — there's
nothing to compile and nothing else to download. No API key. No account. No config.

## ⚡ Usage

```bash
# Build the dashboard from ~/.claude/projects and open it
claudeinsights --open

# Just generate the file
claudeinsights -o my-insights.html

# Quick summary in the terminal
claudeinsights report

# Raw analytics as JSON (pipe it anywhere)
claudeinsights json -o stats.json

# Analyze a specific log directory (e.g. the bundled demo)
claudeinsights --logs examples/sample-logs -o demo.html

# Bring your own prices (USD per 1M tokens)
claudeinsights --pricing my-prices.json
```

Try it on the included demo with **zero risk to your own data**:

```bash
git clone https://github.com/ingridtoulotte/claudeinsights
cd claudeinsights
python examples/generate_sample.py
python -m claudeinsights --logs examples/sample-logs --open
```

## 🔒 Trust is the product

Most "analytics tools" want your data. This one is built so it can't take it.

| Promise | How it's guaranteed |
|---|---|
| **100% local** | The package has *no network code at all*. `grep -r 'socket\|urllib\|http' claudeinsights/` returns nothing. |
| **Private** | It only reads your logs and writes the one file you name. Demo screenshots use synthetic data. |
| **Zero dependencies** | Pure Python standard library. Nothing to audit but us. |
| **Deterministic** | Same logs → identical output, byte for byte. Enforced by tests. |
| **Auditable** | Every metric's source field and formula is documented in [`docs/METRICS.md`](docs/METRICS.md). No black-box scoring. |
| **Honest costs** | Models with no public price are shown as **unpriced** ($0), never faked. |

We even handle the two things naive parsers get wrong:

- **Streaming duplicates** — assistant responses are logged across multiple lines sharing one `message.id`; we deduplicate so tokens aren't double-counted.
- **Resumed sessions** — a session id can span days, so we report **active time** (idle gaps > 30 min removed), not a misleading 100-hour wall clock.

→ Read exactly how each number is computed: **[docs/METRICS.md](docs/METRICS.md)**

## 🆚 How it compares

| | Raw logs | Claude `/cost` | Token CLIs | ClaudeInsights |
|---|:---:|:---:|:---:|:---:|
| Whole-history view | ❌ | ❌ | ⚠️ | ✅ |
| Cost by project / model | ❌ | ❌ | ⚠️ | ✅ |
| Cache-savings tracking | ❌ | ❌ | ❌ | ✅ |
| Tool & MCP analytics | ❌ | ❌ | ❌ | ✅ |
| Activity heatmap | ❌ | ❌ | ❌ | ✅ |
| Leaderboards | ❌ | ❌ | ❌ | ✅ |
| Shareable "Wrapped" | ❌ | ❌ | ❌ | ✅ |
| Visual dashboard | ❌ | ❌ | ❌ | ✅ |
| Local & private | ✅ | ✅ | ✅ | ✅ |
| Zero dependencies | — | — | ⚠️ | ✅ |

## 👤 Who it's for

- **Solo developers** curious where their tokens and dollars go.
- **Power users** optimizing model choice and context habits.
- **Open-source maintainers** who run Claude across many repos.
- **Anyone** who wants a Claude Wrapped to share.

## ❓ FAQ

**Does this send my data anywhere?**
No. There is no network code in the package. It reads `~/.claude/projects` and
writes one local file.

**Where does Claude Code store the logs?**
`~/.claude/projects/<project>/<session-id>.jsonl` on every platform. ClaudeInsights
finds them automatically (or pass `--logs PATH`).

**Are the cost numbers exact?**
They use public Anthropic list prices and your exact token counts (including the
correct cache multipliers). If you use a local/unpriced model, those tokens count
toward usage but $0 toward spend, and the dashboard says so. Override prices with
`--pricing`.

**Why Python with no dependencies?**
So `pip install` just works, anywhere, forever, with nothing to break or audit.

**Does it work on Windows / macOS / Linux?**
Yes — tested on all three in CI across Python 3.8–3.12.

**My session shows as very long / very short?**
Duration is *active* time (idle gaps > 30 min trimmed) because session ids resume
across days. See [docs/METRICS.md](docs/METRICS.md).

## 🛠️ Development

```bash
pip install pytest
python -m claudeinsights selftest   # invariant + smoke checks, no real data
pytest                              # full unit + integration suite
```

Architecture overview: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Product strategy & roadmap: [`docs/STRATEGY.md`](docs/STRATEGY.md).

## 📄 License

MIT © Ingrid Toulotte. See [LICENSE](LICENSE).

<div align="center">
<sub>Built for the Claude Code community. <b>See how you actually use Claude.</b></sub>
</div>
