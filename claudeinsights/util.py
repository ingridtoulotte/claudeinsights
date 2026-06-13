"""Small formatting helpers shared by the terminal, insights and renderer."""

from __future__ import annotations


def human_int(n: float) -> str:
    """1234567 -> '1.23M'. Compact, human counts of tokens etc."""
    n = float(n)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div:
            v = n / div
            return f"{v:.2f}{unit}".rstrip("0").rstrip(".") + ("" if "." in f"{v:.2f}" else "")
    return str(int(n))


def human_money(x: float) -> str:
    if x == 0:
        return "$0.00"
    if abs(x) < 0.01:
        return f"${x:.4f}"
    if abs(x) < 1:
        return f"${x:.3f}"
    return f"${x:,.2f}"


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s" if s else f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def pct(part: float, whole: float) -> float:
    return (100.0 * part / whole) if whole else 0.0
