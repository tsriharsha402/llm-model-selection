# Evaluation plan

Written and committed **before** any results exist, so the criteria can't be bent to fit
the answer we hoped for.

## Decision to make

Which Claude configuration should
[production-rag-service](https://github.com/tsriharsha402/production-rag-service) use to
answer employee questions? Today it runs `claude-opus-5-5` at `effort=medium`
([ADR 0004](https://github.com/tsriharsha402/production-rag-service/blob/main/docs/decisions/0004-grounding-citations-and-model-choice.md)).
The question is whether a cheaper or faster configuration delivers the same quality.

## Candidates

| Name | Model | Effort | Why it is in the comparison |
|---|---|---|---|
| opus-5.5-medium | `claude-opus-5-5` | medium | Current production default (baseline) |
| opus-5.5-low | `claude-opus-5-5` | low | Same model, less thinking: cheaper and faster |
| sonnet-5.5-medium | `claude-sonnet-5-5` | medium | Half the per-token price of Opus |
| sonnet-5.5-low | `claude-sonnet-5-5` | low | Cheapest Sonnet configuration |
| haiku-4.5 | `claude-haiku-4-5` | n/a | Lowest price and latency; tests whether the task needs a large model |

## Test set

45 questions from production-rag-service's evaluation set, each frozen with the chunks
production retrieval returns for it ([`data/grounded_qa.jsonl`](../data/grounded_qa.jsonl),
built by [`scripts/build_dataset.py`](../scripts/build_dataset.py)). Every candidate sees
identical context, so differences come from generation alone.

- **39 "answer" cases:** the retrieved context contains the answer.
- **6 "abstain" cases:** the context does not contain the answer (5 questions the
  handbook doesn't cover, 1 where retrieval missed the right document). The correct
  response is the fixed "I don't know" sentence.

## Grading

Deterministic, so scores are reproducible and cost nothing to compute:

- **Answer cases pass** when the answer contains every required fact, cites the expected
  document, and does not abstain.
- **Abstain cases pass** when the response starts with the abstention sentence.
- **Refusals and API errors fail** (after the SDK's automatic retries). The server-side
  refusal fallback is disabled so each model is measured on its own.

## Decision rule

Configured in [`candidates.toml`](../candidates.toml) and applied by code
([`decision.py`](../src/model_selection/decision.py)):

1. **Eligibility gates.** A candidate is excluded if any of these fail:
   - abstention accuracy below 80% (it makes things up when it should say "I don't know")
   - citation accuracy below 90% (users can't verify its answers)
   - refusal + error rate above 2%
   - p95 latency above 10 seconds
2. **Quality leader.** Among eligible candidates, the one with the highest pass rate.
3. **Non-inferiority.** A candidate is as good as the leader if the upper bound of the
   paired 95% bootstrap interval for (leader pass rate − candidate pass rate) is at most
   5 percentage points.
4. **Recommendation.** The cheapest non-inferior candidate per 1,000 questions; ties
   go to lower p95 latency.

## Known limitations, accepted up front

- With 45 questions, intervals are wide (roughly ±10 points), so non-inferiority is hard
  to establish. If the rule keeps the more expensive model for that reason, the next step
  is a larger test set, not a looser rule.
- One task on a short, clean corpus. The result does not transfer to other workloads.
- Keyword grading can fail a correct paraphrase. A sample of failures is reviewed by hand
  before the recommendation is accepted.

## Changing this plan

Any change to the rule goes in its own commit, with the reason, before a new run.
Never in the same commit as results.
