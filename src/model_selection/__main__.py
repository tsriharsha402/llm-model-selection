"""Command line: estimate | run | report.

python -m model_selection estimate
python -m model_selection run --run-id 2026-10-01
python -m model_selection report --run-id 2026-10-01
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="model_selection")
    parser.add_argument("--config", type=Path, default=ROOT / "candidates.toml")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "grounded_qa.jsonl")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("estimate", help="Estimate the cost of a full run (no API calls)")

    run = sub.add_parser("run", help="Call every candidate on every case, then report")
    run.add_argument("--run-id", default=dt.date.today().isoformat())
    run.add_argument("--candidates", nargs="*", help="Subset of candidate names")
    run.add_argument("--limit", type=int, help="Only the first N cases (smoke test)")
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--yes", action="store_true", help="Skip the cost confirmation")

    report = sub.add_parser("report", help="Rebuild the report and memo from saved results")
    report.add_argument("--run-id", required=True)
    report.add_argument("--no-memo", action="store_true")

    args = parser.parse_args(argv)

    from model_selection.config import load_cases, load_config
    from model_selection.estimate import estimate, render_estimate

    candidates, rule = load_config(args.config)
    cases = load_cases(args.dataset)

    if args.command == "estimate":
        print(render_estimate(estimate(candidates, cases), len(cases)))
        return 0

    if args.command == "run":
        if args.candidates:
            unknown = set(args.candidates) - {c.name for c in candidates}
            if unknown:
                parser.error(f"Unknown candidates: {sorted(unknown)}")
            candidates = [c for c in candidates if c.name in args.candidates]
        if args.limit:
            cases = cases[: args.limit]
        print(render_estimate(estimate(candidates, cases), len(cases)))
        if not args.yes:
            try:
                answer = input("Proceed with this spend? [y/N] ")
            except EOFError:
                answer = ""
            if answer.strip().lower() != "y":
                print("Cancelled. Pass --yes to run non-interactively.")
                return 1

        import anthropic

        from model_selection.runner import run_benchmark

        client = anthropic.Anthropic(max_retries=4, timeout=120.0)
        run_dir = args.results_dir / args.run_id
        total = len(candidates) * len(cases)
        counter = {"n": 0}

        def progress(record) -> None:
            counter["n"] += 1
            status = "ERROR" if record.error else "ok"
            print(f"[{counter['n']}/{total}] {record.candidate} {record.case_id} {status}")

        run_benchmark(
            client, candidates, cases, run_dir / "raw.jsonl", args.workers, progress=progress
        )
        return _report(candidates, cases, rule, run_dir, ROOT / "memo" / "RECOMMENDATION.md")

    run_dir = args.results_dir / args.run_id
    memo = None if args.no_memo else ROOT / "memo" / "RECOMMENDATION.md"
    return _report(candidates, cases, rule, run_dir, memo)


def _report(candidates, cases, rule, run_dir: Path, memo: Path | None) -> int:
    from model_selection.decision import decide, summarize
    from model_selection.report import write_report
    from model_selection.runner import latest_records, load_records

    records = latest_records(load_records(run_dir / "raw.jsonl"))
    run_names = {r.candidate for r in records}
    ran = [c for c in candidates if c.name in run_names]
    ran_case_ids = {r.case_id for r in records}
    ran_cases = [case for case in cases if case.id in ran_case_ids]
    try:
        summaries = [summarize(c, records, ran_cases, rule) for c in ran]
    except ValueError as exc:
        print(f"Incomplete run, re-run to fill the gaps: {exc}", file=sys.stderr)
        return 1
    rec = decide(summaries, rule)
    write_report(summaries, rec, rule, run_dir, memo)
    print(f"Report written to {run_dir}. {rec.rationale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
