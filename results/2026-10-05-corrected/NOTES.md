# Run notes: 2026-10-05-corrected

These results **re-grade the recorded answers from the [2026-10-05 run](../2026-10-05/)**
against corrected dataset labels. No new API calls were made.

## What was wrong

`scripts/build_dataset.py` labeled a question "answer" when the right *document* was in the
retrieved context. It didn't check that the retrieved text contained the required facts.
For 5 questions (`oncall-02`, `incident-01`, `pto-01`, `hard-07`, `hard-08`), retrieval
returned the right document but the wrong section, so the answer wasn't in the context.

Every model correctly replied "I don't know" on those 5. The grader counted that as a
failure, which capped citation accuracy at 34/39 = 87.2% for all five candidates, below
the 90% gate. That identical ceiling across very different models is what exposed the bug.

## Why re-grading is valid

- The evaluation plan already defined "answer" cases as ones where "the retrieved context
  contains the answer". The code didn't implement that; the fix makes it match the plan.
- Only `expected_behavior` changed for those 5 questions. Every question and its retrieved
  context is identical, so the requests sent to the models would be byte-for-byte the same.
  Re-running would only add sampling noise and cost.
- **The decision rule was not changed.** Gates, margin and tie-breakers in
  `candidates.toml` are exactly as committed before the first run.
- A test now rejects any "answer" case whose required facts aren't in its context
  (`tests/test_config_and_prompt.py`). It fails on the old dataset (5 cases) and passes on
  the corrected one.

`raw.jsonl` in this folder is an unmodified copy of `../2026-10-05/raw.jsonl`.
