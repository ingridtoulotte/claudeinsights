"""Deterministic, auditable cost model.

Costs are computed *only* from public Anthropic list prices and the exact
token counts in your logs. Nothing is estimated, sampled, or fudged.

How a message is priced (USD):

    cost = input        * base_in
         + output       * base_out
         + cache_read   * base_in * 0.10     # cache hit
         + cache_5m     * base_in * 1.25     # 5-minute cache write
         + cache_1h     * base_in * 2.00     # 1-hour cache write

(rates are per-token = per-million price / 1_000_000)

Cache multipliers follow Anthropic's published prompt-caching pricing:
reads are 0.1x the base input rate, 5-minute writes 1.25x, 1-hour writes 2x.

Models we don't have a public price for (local/Ollama models, ``<synthetic>``
placeholder messages, future models we haven't tabulated) are reported as
**unpriced** — their tokens still count, but they contribute ``$0`` to spend
and the dashboard flags that the spend figure is a lower bound. We would
rather show an honest "unpriced" than fabricate a number.

You can override or extend the table with ``--pricing your_prices.json``.
"""

from __future__ import annotations

import json
from typing import Dict, Optional, Tuple

from .model import Usage

# Public Anthropic list prices, USD per 1,000,000 tokens (base input / output).
# Matched by substring against the model id, so this keeps working across
# point releases (claude-opus-4-8, claude-3-5-sonnet, us.anthropic.claude-...).
DEFAULT_PRICES: Dict[str, Tuple[float, float]] = {
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}

CACHE_READ_MULT = 0.10
CACHE_WRITE_5M_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.00

# Model ids that are never billed (no real API call happened).
UNBILLED = {"<synthetic>"}


class Pricing:
    """Holds a price table and prices :class:`Usage` against it."""

    def __init__(self, prices: Optional[Dict[str, Tuple[float, float]]] = None):
        self.prices = dict(DEFAULT_PRICES if prices is None else prices)

    @classmethod
    def load(cls, path: Optional[str]) -> "Pricing":
        if not path:
            return cls()
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        prices = {k: (float(v[0]), float(v[1])) for k, v in raw.items()}
        return cls(prices)

    def rates_for(self, model: Optional[str]) -> Optional[Tuple[float, float]]:
        """Return (input_per_token, output_per_token) or None if unpriced."""
        if not model or model in UNBILLED:
            return None
        m = model.lower()
        for key, (pin, pout) in self.prices.items():
            if key in m:
                return (pin / 1_000_000.0, pout / 1_000_000.0)
        return None

    def is_priced(self, model: Optional[str]) -> bool:
        return self.rates_for(model) is not None

    def cost_of(self, usage: Usage, model: Optional[str]) -> float:
        rates = self.rates_for(model)
        if rates is None:
            return 0.0
        base_in, base_out = rates
        return (
            usage.input * base_in
            + usage.output * base_out
            + usage.cache_read * base_in * CACHE_READ_MULT
            + usage.cache_write_5m * base_in * CACHE_WRITE_5M_MULT
            + usage.cache_write_1h * base_in * CACHE_WRITE_1H_MULT
        )

    def cache_savings(self, usage: Usage, model: Optional[str]) -> float:
        """Dollars saved by cache *hits* vs paying full input price for them.

        A cache read costs 0.10x the base input rate, so each cached token
        saves 0.90x the base input rate compared to sending it fresh.
        """
        rates = self.rates_for(model)
        if rates is None:
            return 0.0
        base_in, _ = rates
        return usage.cache_read * base_in * (1.0 - CACHE_READ_MULT)
