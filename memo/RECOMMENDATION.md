# Model recommendation: production-rag-service

**Date:** 2026-10-05  
**Evidence:** benchmark run `2026-10-05-corrected`, 45 questions per candidate  
**Decision rule:** pre-registered in [`candidates.toml`](../candidates.toml), see [evaluation plan](../docs/evaluation-plan.md)  
**Run notes:** [read before using these results](../results/2026-10-05-corrected/NOTES.md)

## Recommendation

Run production on **`claude-sonnet-5-5`**, effort `low`.

Compared with today's configuration (opus-5.5-medium):

- **Quality:** pass rate 100.0% vs. 100.0% (+0.0 points)
- **Cost:** $4.25 vs. $9.54 per 1,000 questions (-56%)
- **Latency:** median 1.7s vs. 2.9s (-1.2s)

**Why:** sonnet-5.5-low ties for the highest pass rate (100.0%) and is the cheapest of the 4 tied candidates. No cheaper candidate was shown to be within 5 percentage points of it.

## Options compared

| Candidate | Pass rate (95% CI) | Keyword recall | Citation acc. | Abstention acc. | Failures | Latency p50 / p95 | Cost / 1K questions | Verdict |
|---|---|---|---|---|---|---|---|---|
| opus-5.5-medium | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 2.9s / 6.1s | $9.54 | Non-inferior, not cheapest |
| opus-5.5-low | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 2.6s / 3.7s | $9.02 | Non-inferior, not cheapest |
| sonnet-5.5-medium | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 1.9s / 4.9s | $4.27 | Non-inferior, not cheapest |
| sonnet-5.5-low | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 1.7s / 4.2s | $4.25 | **Recommended** |
| haiku-4.5 | 97.8% (93%-100%) | 97.1% | 100.0% | 100.0% | 0.0% | 0.8s / 1.1s | $1.38 | Below leader (gap +0% to +7%) |

![Pass rate vs. cost](../results/2026-10-05-corrected/quality_vs_cost.png)

## Risks and mitigations

- **Ceiling effect.** At least one candidate passed every question, so its bootstrap interval collapses to 100%-100%. That overstates certainty: with zero failures in 45 questions, the true failure rate could still be up to about 7% (rule of three). Candidates tied at 100% are separated only by cost, so add harder questions before trusting the ordering among them.
- **Small sample.** 45 questions give wide intervals; differences of a few points are not distinguishable. Mitigation: grow the evaluation set with real, anonymized user questions and re-run before any further downgrade.
- **One task, one corpus.** Results apply to grounded Q&A over short policy documents. Longer documents or multi-step questions need their own run.
- **Keyword grading is strict and narrow.** It can fail a correct paraphrase and cannot judge tone or completeness. Mitigation: add an LLM-graded rubric and spot-check a sample of answers by hand.
- **Model updates.** Re-run this benchmark on every model, prompt or retrieval change; the CI quality gate in production-rag-service catches retrieval regressions only.

## Next steps

1. Change `LLM_MODEL` / `LLM_EFFORT` in production-rag-service behind a feature flag.
2. Roll out to 10% of traffic for one week and compare abstention rate, user feedback and cost per answer against the control group.
3. Roll back automatically if the abstention rate or error rate rises by more than the pre-agreed thresholds.
