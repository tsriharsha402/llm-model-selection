"""Summaries per candidate and the pre-registered decision rule."""

from __future__ import annotations

from dataclasses import dataclass, field

from model_selection.config import Candidate, Case, DecisionRule
from model_selection.grading import grade
from model_selection.pricing import cost_usd
from model_selection.runner import Record
from model_selection.stats import bootstrap_ci, paired_difference_ci, percentile


@dataclass
class Summary:
    candidate: Candidate
    cases: int
    pass_rate: float
    pass_rate_ci: tuple[float, float]
    keyword_recall: float
    citation_accuracy: float
    abstention_accuracy: float
    false_abstention_rate: float
    failure_rate: float
    latency_p50: float
    latency_p95: float
    mean_input_tokens: float
    mean_output_tokens: float
    cost_per_1k: float
    total_cost: float
    passes: list[float] = field(repr=False)  # per case, ordered by case id


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(
    candidate: Candidate, records: list[Record], cases: list[Case], rule: DecisionRule
) -> Summary:
    by_case = {r.case_id: r for r in records if r.candidate == candidate.name}
    missing = [case.id for case in cases if case.id not in by_case]
    if missing:
        raise ValueError(
            f"{candidate.name}: no results for {len(missing)} cases, e.g. {missing[:3]}"
        )

    ordered = sorted(cases, key=lambda c: c.id)
    grades = [grade(by_case[case.id], case) for case in ordered]
    recs = [by_case[case.id] for case in ordered]
    answer = [g for g in grades if g.expected_behavior == "answer"]
    abstain = [g for g in grades if g.expected_behavior == "abstain"]
    passes = [1.0 if g.passed else 0.0 for g in grades]
    costs = [cost_usd(r.model, r.input_tokens, r.output_tokens) for r in recs]
    ok_latencies = [r.latency_seconds for r in recs if r.error is None]
    return Summary(
        candidate=candidate,
        cases=len(grades),
        pass_rate=_mean(passes),
        pass_rate_ci=bootstrap_ci(passes, rule.bootstrap_resamples, rule.seed),
        keyword_recall=_mean([g.keyword_recall for g in answer]),
        citation_accuracy=_mean([1.0 if g.cited_expected_doc else 0.0 for g in answer]),
        abstention_accuracy=_mean([1.0 if g.abstained else 0.0 for g in abstain]),
        false_abstention_rate=_mean([1.0 if g.abstained else 0.0 for g in answer]),
        failure_rate=_mean([1.0 if g.failed else 0.0 for g in grades]),
        latency_p50=percentile(ok_latencies, 50),
        latency_p95=percentile(ok_latencies, 95),
        mean_input_tokens=_mean([float(r.input_tokens) for r in recs]),
        mean_output_tokens=_mean([float(r.output_tokens) for r in recs]),
        cost_per_1k=_mean(costs) * 1000,
        total_cost=sum(costs),
        passes=passes,
    )


@dataclass
class Verdict:
    eligible: bool
    reasons: list[str]
    gap_ci: tuple[float, float] | None = None  # leader pass rate minus this candidate's
    non_inferior: bool = False


@dataclass
class Recommendation:
    chosen: str | None
    leader: str | None
    verdicts: dict[str, Verdict]
    rationale: str


def decide(summaries: list[Summary], rule: DecisionRule) -> Recommendation:
    verdicts: dict[str, Verdict] = {}
    for s in summaries:
        reasons = []
        if s.abstention_accuracy < rule.min_abstention_accuracy:
            reasons.append(
                f"abstention accuracy {s.abstention_accuracy:.0%} < "
                f"{rule.min_abstention_accuracy:.0%}"
            )
        if s.citation_accuracy < rule.min_citation_accuracy:
            reasons.append(
                f"citation accuracy {s.citation_accuracy:.0%} < {rule.min_citation_accuracy:.0%}"
            )
        if s.failure_rate > rule.max_failure_rate:
            reasons.append(f"failure rate {s.failure_rate:.1%} > {rule.max_failure_rate:.1%}")
        if s.latency_p95 > rule.max_p95_latency_seconds:
            reasons.append(
                f"p95 latency {s.latency_p95:.1f}s > {rule.max_p95_latency_seconds:.1f}s"
            )
        verdicts[s.candidate.name] = Verdict(eligible=not reasons, reasons=reasons)

    eligible = [s for s in summaries if verdicts[s.candidate.name].eligible]
    if not eligible:
        return Recommendation(
            chosen=None,
            leader=None,
            verdicts=verdicts,
            rationale="No candidate passed the eligibility gates, so none can be recommended.",
        )

    leader = max(eligible, key=lambda s: (s.pass_rate, -s.cost_per_1k))
    for s in eligible:
        verdict = verdicts[s.candidate.name]
        if s is leader:
            verdict.gap_ci = (0.0, 0.0)
            verdict.non_inferior = True
            continue
        verdict.gap_ci = paired_difference_ci(
            leader.passes, s.passes, rule.bootstrap_resamples, rule.seed
        )
        verdict.non_inferior = verdict.gap_ci[1] <= rule.non_inferiority_margin

    candidates = [s for s in eligible if verdicts[s.candidate.name].non_inferior]
    chosen = min(candidates, key=lambda s: (s.cost_per_1k, s.latency_p95))
    margin = f"{rule.non_inferiority_margin * 100:.0f} percentage points"
    if chosen is leader:
        tied = [s for s in eligible if s.pass_rate == leader.pass_rate]
        if len(tied) > 1:
            rationale = (
                f"{leader.candidate.name} ties for the highest pass rate "
                f"({leader.pass_rate:.1%}) and is the cheapest of the {len(tied)} tied "
                f"candidates. No cheaper candidate was shown to be within {margin} of it."
            )
        else:
            rationale = (
                f"{leader.candidate.name} has the highest pass rate among eligible candidates, "
                f"and no cheaper candidate was shown to be within {margin} of it."
            )
    else:
        gap = verdicts[chosen.candidate.name].gap_ci
        assert gap is not None
        rationale = (
            f"{chosen.candidate.name} is the cheapest eligible candidate whose quality is "
            f"non-inferior to the leader, {leader.candidate.name}: the 95% interval for the "
            f"pass-rate gap is {gap[0]:+.1%} to {gap[1]:+.1%}, within the {margin} margin."
        )
    return Recommendation(
        chosen=chosen.candidate.name,
        leader=leader.candidate.name,
        verdicts=verdicts,
        rationale=rationale,
    )
