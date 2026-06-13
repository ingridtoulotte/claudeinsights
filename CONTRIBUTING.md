# Contributing to ClaudeInsights

Thanks for considering a contribution! This project stays small on purpose, so a
few principles keep it healthy.

## Principles (please don't break these)

1. **Zero runtime dependencies.** Standard library only. A PR that adds a
   dependency will be asked to remove it.
2. **Local & private.** No network calls, no telemetry, ever. The package must
   never read or write anything beyond the logs and the output file the user names.
3. **No fabricated metrics.** Every number must trace to a log field and a
   documented formula in `docs/METRICS.md`. No black-box scoring.
4. **Deterministic.** Same logs in → identical output out.

## Getting started

```bash
git clone https://github.com/ingridtoulotte/claudeinsights
cd claudeinsights
pip install -e .
pip install pytest

python examples/generate_sample.py          # synthetic demo logs
python -m claudeinsights --logs examples/sample-logs --open

python -m claudeinsights selftest            # invariant checks
pytest                                       # full suite
```

## Before opening a PR

- `pytest` and `python -m claudeinsights selftest` both pass.
- New metrics are documented in `docs/METRICS.md`.
- New parsing behaviour has a test (ideally against a fixture in `tests/`).
- Screenshots, if updated, are regenerated from the **synthetic** demo dataset —
  never from real `~/.claude` logs.

## Good first issues

- New data-backed insights (with the supporting number).
- Additional chart types in `assets/template.html` (hand-rolled SVG, no libs).
- `--since` / `--until` / `--project` filters.
- Pricing table updates as new models ship.

By contributing you agree your work is licensed under the project's MIT license.
