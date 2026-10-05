# Results: 2026-10-05-corrected

| Candidate | Pass rate (95% CI) | Keyword recall | Citation acc. | Abstention acc. | Failures | Latency p50 / p95 | Cost / 1K questions | Verdict |
|---|---|---|---|---|---|---|---|---|
| opus-5.5-medium | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 2.9s / 6.1s | $9.54 | Non-inferior, not cheapest |
| opus-5.5-low | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 2.6s / 3.7s | $9.02 | Non-inferior, not cheapest |
| sonnet-5.5-medium | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 1.9s / 4.9s | $4.27 | Non-inferior, not cheapest |
| sonnet-5.5-low | 100.0% (100%-100%) | 100.0% | 100.0% | 100.0% | 0.0% | 1.7s / 4.2s | $4.25 | **Recommended** |
| haiku-4.5 | 97.8% (93%-100%) | 97.1% | 100.0% | 100.0% | 0.0% | 0.8s / 1.1s | $1.38 | Below leader (gap +0% to +7%) |

sonnet-5.5-low ties for the highest pass rate (100.0%) and is the cheapest of the 4 tied candidates. No cheaper candidate was shown to be within 5 percentage points of it.
