"""Pre-run cost estimate, so the budget is approved before any money is spent."""

from __future__ import annotations

from dataclasses import dataclass

from model_selection.config import Candidate, Case
from model_selection.pricing import cost_usd
from model_selection.prompt import SYSTEM_PROMPT

# ~4 characters per token for English text, plus per-block framing overhead.
CHARS_PER_TOKEN = 4
TOKENS_PER_SEARCH_RESULT = 25
# Output includes extended thinking where enabled, so the range is deliberately wide.
OUTPUT_TOKENS_RANGE = (150, 1500)


@dataclass(frozen=True)
class Estimate:
    candidate: Candidate
    input_tokens_per_case: float
    low_usd: float
    high_usd: float


def input_tokens(case: Case) -> int:
    chars = len(SYSTEM_PROMPT) + len(case.question)
    chars += sum(len(s.text) + len(s.title) + len(s.section) for s in case.sources)
    return chars // CHARS_PER_TOKEN + TOKENS_PER_SEARCH_RESULT * len(case.sources)


def estimate(candidates: list[Candidate], cases: list[Case]) -> list[Estimate]:
    total_input = sum(input_tokens(case) for case in cases)
    low_out, high_out = OUTPUT_TOKENS_RANGE
    return [
        Estimate(
            candidate=c,
            input_tokens_per_case=total_input / len(cases),
            low_usd=cost_usd(c.model, total_input, low_out * len(cases)),
            high_usd=cost_usd(c.model, total_input, high_out * len(cases)),
        )
        for c in candidates
    ]


def render_estimate(estimates: list[Estimate], cases: int) -> str:
    lines = [
        f"Estimated cost of one full run ({cases} cases per candidate)",
        "",
        "| Candidate | Model | Input tokens / case | Estimated cost |",
        "|---|---|---|---|",
    ]
    for e in estimates:
        lines.append(
            f"| {e.candidate.name} | `{e.candidate.model}` | ~{e.input_tokens_per_case:,.0f} "
            f"| ${e.low_usd:.2f} - ${e.high_usd:.2f} |"
        )
    low = sum(e.low_usd for e in estimates)
    high = sum(e.high_usd for e in estimates)
    lines += [
        f"| **Total** | | | **${low:.2f} - ${high:.2f}** |",
        "",
        f"Assumes {OUTPUT_TOKENS_RANGE[0]}-{OUTPUT_TOKENS_RANGE[1]} output tokens per answer "
        "(including any extended thinking). Input tokens are estimated from text length.",
    ]
    return "\n".join(lines) + "\n"
