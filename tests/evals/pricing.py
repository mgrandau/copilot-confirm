"""Per-model token pricing for cost estimates in eval reports.

Prices are USD per 1M tokens (input, output).

Sources used (approximate; update as providers change pricing):
- Anthropic: https://www.anthropic.com/pricing
- OpenAI:    https://openai.com/api/pricing
- Google:    https://ai.google.dev/pricing

These represent retail API rates. For Copilot/Plus subscriptions the marginal
cost may be 0 inside quota and pay-as-you-go after that — these numbers serve
as an upper-bound estimate suitable for relative comparison across runs.
"""

from __future__ import annotations

# (input_per_1M, output_per_1M) in USD
PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-opus-4.7":            (15.00, 75.00),
    "claude-sonnet-4.6":           (3.00, 15.00),
    "claude-haiku-4.5":            (1.00,  5.00),
    # OpenAI
    "gpt-5.4":                     (5.00, 15.00),
    "gpt-5-mini":                  (0.25,  2.00),
    # Google
    "gemini-3.1-pro-preview":      (1.25, 10.00),
    "gemini-3-flash-preview":      (0.10,  0.40),
}


def estimate_cost(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Return USD cost estimate for a single call, or None if unpriced."""
    if model not in PRICING:
        return None
    if input_tokens is None and output_tokens is None:
        return None
    in_rate, out_rate = PRICING[model]
    cost = 0.0
    if input_tokens:
        cost += (input_tokens / 1_000_000) * in_rate
    if output_tokens:
        cost += (output_tokens / 1_000_000) * out_rate
    return cost
