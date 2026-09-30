"""USD per million tokens, Anthropic first-party API, September 2026.

Check https://www.anthropic.com/pricing before using these for a budget.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float


PRICES_PER_MTOK: dict[str, Price] = {
    "claude-opus-5-5": Price(input=4.00, output=20.00),
    "claude-sonnet-5-5": Price(input=2.00, output=10.00),
    "claude-haiku-4-5": Price(input=1.00, output=5.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICES_PER_MTOK[model]
    return (input_tokens * price.input + output_tokens * price.output) / 1_000_000
