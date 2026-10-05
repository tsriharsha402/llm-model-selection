import json

from conftest import FakeClient, make_case

from model_selection.__main__ import main
from model_selection.config import Candidate, DecisionRule
from model_selection.decision import decide, summarize
from model_selection.report import render_memo, write_report
from model_selection.runner import run_benchmark
from model_selection.stats import bootstrap_ci, paired_difference_ci

BIG = Candidate("big", "claude-opus-5-5", "medium")
SMALL = Candidate("small", "claude-haiku-4-5")


def _cases(n_answer=30, n_abstain=6):
    return [make_case(f"a{i:02d}") for i in range(n_answer)] + [
        make_case(f"z{i:02d}", "abstain") for i in range(n_abstain)
    ]


def _summaries(tmp_path, client, rule):
    cases = _cases()
    records = run_benchmark(client, [BIG, SMALL], cases, tmp_path / "raw.jsonl", workers=4)
    return [summarize(c, records, cases, rule) for c in (BIG, SMALL)]


def test_bootstrap_is_seeded_and_brackets_the_mean():
    values = [1.0] * 80 + [0.0] * 20
    lo, hi = bootstrap_ci(values, resamples=500, seed=1)
    assert lo < 0.8 < hi
    assert (lo, hi) == bootstrap_ci(values, resamples=500, seed=1)
    assert paired_difference_ci([1.0] * 10, [1.0] * 10) == (0.0, 0.0)


def test_cheaper_equal_quality_candidate_is_recommended(tmp_path, rule):
    summaries = _summaries(tmp_path, FakeClient(), rule)
    rec = decide(summaries, rule)
    assert rec.leader == "small"  # tie on quality, so the cheaper one leads
    assert rec.chosen == "small"
    assert rec.verdicts["small"].non_inferior
    assert "ties for the highest pass rate" in rec.rationale


def test_worse_candidate_is_not_recommended(tmp_path, rule):
    summaries = _summaries(tmp_path, FakeClient(bad_models={"claude-haiku-4-5"}), rule)
    rec = decide(summaries, rule)
    assert rec.chosen == "big"
    assert not rec.verdicts["small"].eligible  # fails the abstention and citation gates


def test_no_eligible_candidate(tmp_path):
    strict = DecisionRule(bootstrap_resamples=200, max_p95_latency_seconds=-1)
    summaries = _summaries(tmp_path, FakeClient(), strict)
    rec = decide(summaries, strict)
    assert rec.chosen is None
    assert "No candidate" in rec.rationale


def test_report_and_memo(tmp_path, rule):
    summaries = _summaries(tmp_path, FakeClient(), rule)
    rec = decide(summaries, rule)
    run_dir = tmp_path / "results" / "test-run"
    memo = tmp_path / "memo" / "RECOMMENDATION.md"
    run_dir.mkdir(parents=True)
    (run_dir / "NOTES.md").write_text("Data correction.")
    write_report(summaries, rec, rule, run_dir, memo)
    assert (run_dir / "quality_vs_cost.png").stat().st_size > 10_000
    assert json.loads((run_dir / "summary.json").read_text())["chosen"] == "small"
    text = memo.read_text()
    assert "Run production on **`claude-haiku-4-5`**" in text
    assert "Compared with today's configuration (big)" in text
    assert "../results/test-run/quality_vs_cost.png" in text
    assert "Ceiling effect" in text  # every fake answer passes
    assert "../results/test-run/NOTES.md" in text


def test_memo_when_nothing_is_eligible(tmp_path, rule):
    summaries = _summaries(tmp_path, FakeClient(), rule)
    rec = decide(summaries, DecisionRule(max_p95_latency_seconds=-1))
    assert "No candidate passed" in render_memo(summaries, rec, rule, "r", "c.png")


def test_cli_estimate_and_report(tmp_path, monkeypatch, capsys, config, cases):
    monkeypatch.chdir(tmp_path.parent)
    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    args = [
        "--config",
        str(root / "candidates.toml"),
        "--dataset",
        str(root / "data" / "grounded_qa.jsonl"),
    ]
    assert main([*args, "estimate"]) == 0
    assert "Total" in capsys.readouterr().out

    candidates, _ = config
    run_dir = tmp_path / "results" / "r1"
    run_benchmark(FakeClient(), candidates[:2], cases[:5], run_dir / "raw.jsonl")
    code = main(
        [*args, "--results-dir", str(tmp_path / "results"), "report", "--run-id", "r1", "--no-memo"]
    )
    assert code == 0
    assert (run_dir / "summary.md").exists()
