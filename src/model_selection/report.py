"""Results table, quality-vs-cost chart and the recommendation memo."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from model_selection.config import DecisionRule  # noqa: E402
from model_selection.decision import Recommendation, Summary  # noqa: E402

# Validated categorical slots (blue, orange, aqua): all pairs pass CVD separation.
# Aqua is under 3:1 contrast on the light surface, so every point is directly labeled.
MODEL_COLORS = {
    "claude-opus-5-5": "#2a78d6",
    "claude-sonnet-5-5": "#eb6834",
    "claude-haiku-4-5": "#1baf7a",
}
EFFORT_MARKERS = {"medium": "o", "low": "s", None: "D"}
# Medium-effort points are drawn larger and underneath, so a low-effort point at almost the
# same cost and quality stays visible inside it instead of hiding it.
EFFORT_SIZES = {"medium": 150, "low": 70, None: 90}
EFFORT_ZORDER = {"medium": 3, "low": 4, None: 4}
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"


def results_table(summaries: list[Summary], rec: Recommendation) -> str:
    lines = [
        "| Candidate | Pass rate (95% CI) | Keyword recall | Citation acc. | Abstention acc. "
        "| Failures | Latency p50 / p95 | Cost / 1K questions | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in sorted(summaries, key=lambda s: -s.pass_rate):
        verdict = rec.verdicts[s.candidate.name]
        if s.candidate.name == rec.chosen:
            label = "**Recommended**"
        elif not verdict.eligible:
            label = "Ineligible: " + "; ".join(verdict.reasons)
        elif verdict.non_inferior:
            label = "Non-inferior, not cheapest"
        else:
            assert verdict.gap_ci is not None
            label = f"Below leader (gap {verdict.gap_ci[0]:+.0%} to {verdict.gap_ci[1]:+.0%})"
        lo, hi = s.pass_rate_ci
        lines.append(
            f"| {s.candidate.name} | {s.pass_rate:.1%} ({lo:.0%}-{hi:.0%}) "
            f"| {s.keyword_recall:.1%} | {s.citation_accuracy:.1%} | {s.abstention_accuracy:.1%} "
            f"| {s.failure_rate:.1%} | {s.latency_p50:.1f}s / {s.latency_p95:.1f}s "
            f"| ${s.cost_per_1k:.2f} | {label} |"
        )
    return "\n".join(lines) + "\n"


def plot_quality_vs_cost(summaries: list[Summary], rec: Recommendation, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for s in summaries:
        color = MODEL_COLORS.get(s.candidate.model, TEXT_SECONDARY)
        lo, hi = s.pass_rate_ci
        y = s.pass_rate * 100
        ax.errorbar(
            s.cost_per_1k,
            y,
            yerr=[[y - lo * 100], [hi * 100 - y]],
            fmt="none",
            ecolor=color,
            elinewidth=1.5,
            capsize=4,
            zorder=2,
        )
        ax.scatter(
            s.cost_per_1k,
            y,
            s=EFFORT_SIZES.get(s.candidate.effort, 90),
            marker=EFFORT_MARKERS.get(s.candidate.effort, "o"),
            color=color,
            edgecolors=SURFACE,
            linewidths=2,
            zorder=EFFORT_ZORDER.get(s.candidate.effort, 4),
        )

    # Labels sit above or below the error bar, alternating along the cost axis so
    # neighboring candidates never collide.
    for i, s in enumerate(sorted(summaries, key=lambda s: s.cost_per_1k)):
        lo, hi = s.pass_rate_ci
        chosen = s.candidate.name == rec.chosen
        above = i % 2 == 0
        label = s.candidate.name + ("\n(recommended)" if chosen else "")
        ax.annotate(
            label,
            (s.cost_per_1k, (hi if above else lo) * 100),
            xytext=(0, 6 if above else -6),
            textcoords="offset points",
            ha="center",
            va="bottom" if above else "top",
            fontsize=9,
            color=TEXT_PRIMARY,
            fontweight="bold" if chosen else "normal",
        )

    for model, color in MODEL_COLORS.items():
        if any(s.candidate.model == model for s in summaries):
            ax.scatter([], [], color=color, s=60, label=model)
    for effort, marker in EFFORT_MARKERS.items():
        if any(s.candidate.effort == effort for s in summaries):
            name = f"effort: {effort}" if effort else "no effort setting"
            ax.scatter([], [], color=TEXT_SECONDARY, marker=marker, s=50, label=name)
    ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="lower right")

    ax.set_title(
        "Pass rate vs. cost per 1,000 questions",
        loc="left",
        fontsize=12,
        color=TEXT_PRIMARY,
    )
    ax.set_xlabel("Cost per 1,000 questions (USD)", color=TEXT_SECONDARY, fontsize=10)
    ax.set_ylabel("Pass rate (%) with 95% CI", color=TEXT_SECONDARY, fontsize=10)
    ax.set_ylim(0, 115)
    ax.set_yticks(range(0, 101, 20))
    ax.set_xlim(0, max(s.cost_per_1k for s in summaries) * 1.15 if summaries else 1)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def render_memo(
    summaries: list[Summary],
    rec: Recommendation,
    rule: DecisionRule,
    run_id: str,
    chart_path: str,
    date: dt.date | None = None,
    notes: bool = False,
) -> str:
    date = date or dt.date.today()
    by_name = {s.candidate.name: s for s in summaries}
    chosen = by_name.get(rec.chosen) if rec.chosen else None
    baseline = by_name.get(rule.baseline)
    n = summaries[0].cases if summaries else 0

    lines = [
        "# Model recommendation: production-rag-service",
        "",
        f"**Date:** {date.isoformat()}  ",
        f"**Evidence:** benchmark run `{run_id}`, {n} questions per candidate  ",
        "**Decision rule:** pre-registered in [`candidates.toml`](../candidates.toml), "
        "see [evaluation plan](../docs/evaluation-plan.md)  ",
        *(
            [f"**Run notes:** [read before using these results](../results/{run_id}/NOTES.md)"]
            if notes
            else []
        ),
        "",
        "## Recommendation",
        "",
    ]
    if chosen is None:
        lines += [rec.rationale, ""]
    else:
        effort = f", effort `{chosen.candidate.effort}`" if chosen.candidate.effort else ""
        lines += [f"Run production on **`{chosen.candidate.model}`**{effort}.", ""]
        if baseline and baseline is not chosen:
            quality = (chosen.pass_rate - baseline.pass_rate) * 100
            cost = (chosen.cost_per_1k / baseline.cost_per_1k - 1) * 100
            latency = chosen.latency_p50 - baseline.latency_p50
            lines += [
                f"Compared with today's configuration ({baseline.candidate.name}):",
                "",
                f"- **Quality:** pass rate {chosen.pass_rate:.1%} vs. {baseline.pass_rate:.1%} "
                f"({quality:+.1f} points)",
                f"- **Cost:** ${chosen.cost_per_1k:.2f} vs. ${baseline.cost_per_1k:.2f} per "
                f"1,000 questions ({cost:+.0f}%)",
                f"- **Latency:** median {chosen.latency_p50:.1f}s vs. "
                f"{baseline.latency_p50:.1f}s ({latency:+.1f}s)",
                "",
            ]
        elif baseline is chosen:
            lines += ["This is the configuration production already runs: no change.", ""]
        lines += [f"**Why:** {rec.rationale}", ""]

    if any(s.pass_rate == 1.0 for s in summaries):
        ceiling = (
            f"- **Ceiling effect.** At least one candidate passed every question, so its "
            f"bootstrap interval collapses to 100%-100%. That overstates certainty: with zero "
            f"failures in {n} questions, the true failure rate could still be up to about "
            f"{3 / n:.0%} (rule of three). Candidates tied at 100% are separated only by cost, "
            "so add harder questions before trusting the ordering among them."
        )
    else:
        ceiling = None

    lines += [
        "## Options compared",
        "",
        results_table(summaries, rec),
        f"![Pass rate vs. cost]({chart_path})",
        "",
        "## Risks and mitigations",
        "",
        *([ceiling] if ceiling else []),
        f"- **Small sample.** {n} questions give wide intervals; differences of a few points "
        "are not distinguishable. Mitigation: grow the evaluation set with real, anonymized "
        "user questions and re-run before any further downgrade.",
        "- **One task, one corpus.** Results apply to grounded Q&A over short policy "
        "documents. Longer documents or multi-step questions need their own run.",
        "- **Keyword grading is strict and narrow.** It can fail a correct paraphrase and "
        "cannot judge tone or completeness. Mitigation: add an LLM-graded rubric and spot-check "
        "a sample of answers by hand.",
        "- **Model updates.** Re-run this benchmark on every model, prompt or retrieval "
        "change; the CI quality gate in production-rag-service catches retrieval regressions "
        "only.",
        "",
        "## Next steps",
        "",
        "1. Change `LLM_MODEL` / `LLM_EFFORT` in production-rag-service behind a feature flag.",
        "2. Roll out to 10% of traffic for one week and compare abstention rate, user feedback "
        "and cost per answer against the control group.",
        "3. Roll back automatically if the abstention rate or error rate rises by more than "
        "the pre-agreed thresholds.",
    ]
    return "\n".join(lines) + "\n"


def write_report(
    summaries: list[Summary],
    rec: Recommendation,
    rule: DecisionRule,
    run_dir: Path,
    memo_path: Path | None,
) -> None:
    import json

    run_dir.mkdir(parents=True, exist_ok=True)
    chart = run_dir / "quality_vs_cost.png"
    plot_quality_vs_cost(summaries, rec, chart)
    (run_dir / "summary.md").write_text(
        f"# Results: {run_dir.name}\n\n{results_table(summaries, rec)}\n{rec.rationale}\n"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "chosen": rec.chosen,
                "leader": rec.leader,
                "rationale": rec.rationale,
                "candidates": [
                    {
                        "name": s.candidate.name,
                        "model": s.candidate.model,
                        "effort": s.candidate.effort,
                        "pass_rate": s.pass_rate,
                        "pass_rate_ci": s.pass_rate_ci,
                        "keyword_recall": s.keyword_recall,
                        "citation_accuracy": s.citation_accuracy,
                        "abstention_accuracy": s.abstention_accuracy,
                        "false_abstention_rate": s.false_abstention_rate,
                        "failure_rate": s.failure_rate,
                        "latency_p50": s.latency_p50,
                        "latency_p95": s.latency_p95,
                        "cost_per_1k": s.cost_per_1k,
                        "total_cost": s.total_cost,
                        "eligible": rec.verdicts[s.candidate.name].eligible,
                        "reasons": rec.verdicts[s.candidate.name].reasons,
                    }
                    for s in summaries
                ],
            },
            indent=2,
        )
        + "\n"
    )
    if memo_path is not None:
        memo_path.parent.mkdir(parents=True, exist_ok=True)
        relative_chart = Path("..") / chart.relative_to(memo_path.parent.parent)
        memo_path.write_text(
            render_memo(
                summaries,
                rec,
                rule,
                run_dir.name,
                relative_chart.as_posix(),
                notes=(run_dir / "NOTES.md").exists(),
            )
        )
