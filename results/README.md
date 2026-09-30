# Results

Each benchmark run writes a folder here named by its run ID:

- `raw.jsonl`: one line per (candidate, question) with the answer, citations, token usage and latency
- `summary.md` / `summary.json`: metrics per candidate and the decision
- `quality_vs_cost.png`: pass rate with 95% intervals against cost per 1,000 questions

Commit the whole folder: raw results make every number in the memo auditable.
