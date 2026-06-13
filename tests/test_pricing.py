from claudeinsights.model import Usage
from claudeinsights.pricing import Pricing


def test_base_rates_per_million():
    pr = Pricing()
    u = Usage(input=1_000_000, output=1_000_000)
    assert abs(pr.cost_of(u, "claude-opus-4-8") - 90.0) < 1e-9      # 15 + 75
    assert abs(pr.cost_of(u, "claude-sonnet-4-6") - 18.0) < 1e-9    # 3 + 15
    assert abs(pr.cost_of(u, "claude-haiku-4-5") - 6.0) < 1e-9      # 1 + 5


def test_substring_matching_is_version_agnostic():
    pr = Pricing()
    u = Usage(output=1_000_000)
    assert abs(pr.cost_of(u, "us.anthropic.claude-3-5-sonnet-20241022") - 15.0) < 1e-9
    assert abs(pr.cost_of(u, "claude-opus-4-8-20260101") - 75.0) < 1e-9


def test_cache_multipliers():
    pr = Pricing()
    # opus base input = $15/1M = 1.5e-5 per token
    assert abs(pr.cost_of(Usage(cache_read=1_000_000), "claude-opus-4-8") - 1.5) < 1e-9
    assert abs(pr.cost_of(Usage(cache_write_5m=1_000_000), "claude-opus-4-8") - 18.75) < 1e-9
    assert abs(pr.cost_of(Usage(cache_write_1h=1_000_000), "claude-opus-4-8") - 30.0) < 1e-9


def test_unpriced_models_are_zero_not_guessed():
    pr = Pricing()
    assert pr.cost_of(Usage(input=10_000, output=10_000), "qwen3-local") == 0.0
    assert pr.cost_of(Usage(input=10_000), "<synthetic>") == 0.0
    assert pr.is_priced("claude-opus-4-8") is True
    assert pr.is_priced("llama3") is False
    assert pr.is_priced(None) is False


def test_cache_savings():
    pr = Pricing()
    # 1M cached opus reads cost 1.5 but would have cost 15 fresh -> saved 13.5
    assert abs(pr.cache_savings(Usage(cache_read=1_000_000), "claude-opus-4-8") - 13.5) < 1e-9
    assert pr.cache_savings(Usage(cache_read=1_000_000), "qwen") == 0.0


def test_pricing_override(tmp_path):
    import json
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"opus": [99, 0]}))
    pr = Pricing.load(str(f))
    assert abs(pr.cost_of(Usage(input=1_000_000), "claude-opus-4-8") - 99.0) < 1e-9
    assert pr.cost_of(Usage(output=1_000_000), "claude-opus-4-8") == 0.0
