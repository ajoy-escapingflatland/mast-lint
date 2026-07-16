"""Step 4 — the credibility moat: measure the judge against human gold labels.

Roadmap Step 4 says "measure the judge's Cohen's κ vs. your labels." We don't need
to hand-label: the MAST human-labeled dataset already ships 3-annotator labels, which
the adapter turns into ``MASTGold`` (majority vote per mode). This module runs the
judge over those traces and scores agreement.

Two things kept deliberately honest:

* **Comparison is trace-level.** Human labels are "did mode M occur anywhere in this
  run" (not span-level), so we reduce each judge Report to the set of modes it fired
  and compare presence/absence per (trace, mode) cell. κ (not raw accuracy) is the
  headline because failures are sparse — most cells are true-negatives, and κ corrects
  for the resulting chance agreement.

* **Each trace is scored only on the modes its taxonomy version could label.** The
  dataset spans three taxonomy versions (see docs/mast_dataset.md); a v1 trace never
  had the chance to be labeled for, say, FM-1.4. Scoring the judge on a mode with no
  possible ground truth would be unfair, so the comparison universe for a trace is
  exactly ``gold.present`` keys. Judge findings for modes outside that universe are
  counted separately (``unscored_findings``) — surfaced, never silently dropped.

This module makes NO LLM calls itself; it takes a ``JudgeClient`` (or pre-computed
Reports) so it is fully unit-testable offline.
"""
from __future__ import annotations

import json
import random
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, Field

from .adapters.mast import MASTGold
from .judge import JudgeClient, judge_trace
from .schema import Report, Trace


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def cohen_kappa(tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Cohen's κ for two binary raters (judge vs. human) over a confusion matrix.

    Returns ``None`` when there are no cells. When one class is absent for both raters
    (chance agreement is total), κ is degenerate: 1.0 if they agree everywhere, else
    0.0 — the standard convention.
    """
    n = tp + fp + fn + tn
    if n == 0:
        return None
    po = (tp + tn) / n
    judge_yes, human_yes = (tp + fp) / n, (tp + fn) / n
    judge_no, human_no = (fn + tn) / n, (fp + tn) / n
    pe = judge_yes * human_yes + judge_no * human_no
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


class Score(BaseModel):
    """Confusion counts + derived metrics for one slice (a mode, a version, or overall).

    Judge is scored against the human majority as ground truth: precision/recall are
    the judge's; κ is symmetric agreement between judge and humans.
    """

    label: str
    n: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    kappa: float | None = None

    @classmethod
    def from_counts(cls, label: str, tp: int, fp: int, fn: int, tn: int) -> Score:
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision and recall
            else (0.0 if (precision is not None and recall is not None) else None)
        )
        return cls(
            label=label, n=tp + fp + fn + tn, tp=tp, fp=fp, fn=fn, tn=tn,
            precision=precision, recall=recall, f1=f1,
            kappa=cohen_kappa(tp, fp, fn, tn),
        )


class TraceResult(BaseModel):
    trace_id: str
    mas_name: str
    taxonomy_version: str
    human_fired: list[str]
    judge_fired: list[str]
    unscored_judge_modes: list[str] = Field(
        default_factory=list,
        description="Modes the judge fired that this trace's taxonomy could not label",
    )


class EvalReport(BaseModel):
    """The published artifact: how much to trust the judge."""

    n_traces: int
    overall: Score
    per_mode: list[Score]
    by_version: dict[str, Score]
    unscored_findings: int = Field(
        description="Total judge findings on modes outside a trace's labelable universe"
    )
    per_trace: list[TraceResult]
    threshold: float = Field(
        0.0, description="Min finding confidence for a mode to count as fired in this score"
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def _confusion(rows: Iterable[tuple[bool, bool]]) -> tuple[int, int, int, int]:
    """Count (human, judge) pairs into (tp, fp, fn, tn)."""
    tp = fp = fn = tn = 0
    for human, judge in rows:
        if human and judge:
            tp += 1
        elif judge and not human:
            fp += 1
        elif human and not judge:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def modes_fired_at(report: Report, threshold: float) -> set[str]:
    """Modes the judge fired, keeping only findings whose confidence clears ``threshold``.
    At ``threshold <= 0`` every finding counts (identical to ``report.modes_fired``)."""
    return {f.failure_mode_id for f in report.findings if f.confidence >= threshold}


def score(results: list[tuple[Report, MASTGold]], *, threshold: float = 0.0) -> EvalReport:
    """Score a batch of (judge Report, human gold) pairs into an EvalReport.

    ``threshold`` gates which judge findings count as "fired" by confidence — raising it
    trades recall for precision, so a κ-vs-τ sweep can be run offline on saved results."""
    # (mode, human, judge) cells, restricted per-trace to the labelable universe.
    cells: list[tuple[str, bool, bool]] = []
    version_cells: dict[str, list[tuple[bool, bool]]] = {}
    per_trace: list[TraceResult] = []
    unscored_total = 0

    for report, gold in results:
        fired = modes_fired_at(report, threshold)
        universe = set(gold.present)
        unscored = sorted(fired - universe)
        unscored_total += len(unscored)
        for mode in universe:
            pair = (gold.present[mode], mode in fired)
            cells.append((mode, *pair))
            version_cells.setdefault(gold.taxonomy_version, []).append(pair)
        per_trace.append(
            TraceResult(
                trace_id=gold.trace_id,
                mas_name=gold.mas_name,
                taxonomy_version=gold.taxonomy_version,
                human_fired=gold.fired,
                judge_fired=sorted(fired & universe),
                unscored_judge_modes=unscored,
            )
        )

    overall = Score.from_counts("overall", *_confusion((h, j) for _, h, j in cells))

    per_mode: list[Score] = []
    for mode in sorted({m for m, _, _ in cells}):
        rows = [(h, j) for m, h, j in cells if m == mode]
        per_mode.append(Score.from_counts(mode, *_confusion(rows)))

    by_version = {
        ver: Score.from_counts(ver, *_confusion(rows))
        for ver, rows in sorted(version_cells.items())
    }

    return EvalReport(
        n_traces=len(results),
        overall=overall,
        per_mode=per_mode,
        by_version=by_version,
        unscored_findings=unscored_total,
        per_trace=per_trace,
        threshold=threshold,
    )


def run_judge(
    pairs: Iterable[tuple[Trace, MASTGold]],
    client: JudgeClient,
    *,
    on_trace=None,
) -> list[tuple[Report, MASTGold]]:
    """Run the judge over each trace, returning the RAW (Report, gold) pairs — the
    expensive, API-calling step. Kept separate from ``score`` so the paid pass runs once
    and every downstream analysis (thresholding, sweeps) is a pure re-score of the saved
    findings. ``on_trace(i, trace)`` is an optional progress callback."""
    results: list[tuple[Report, MASTGold]] = []
    for i, (trace, gold) in enumerate(pairs):
        if on_trace is not None:
            on_trace(i, trace)
        results.append((judge_trace(trace, client), gold))
    return results


def evaluate(
    pairs: Iterable[tuple[Trace, MASTGold]],
    client: JudgeClient,
    *,
    threshold: float = 0.0,
    on_trace=None,
) -> EvalReport:
    """Convenience: judge every trace and score in one call (``run_judge`` + ``score``)."""
    return score(run_judge(pairs, client, on_trace=on_trace), threshold=threshold)


# --------------------------------------------------------------------------- #
# Raw-results persistence + offline threshold sweep
# --------------------------------------------------------------------------- #
class JudgedTrace(BaseModel):
    """One trace's raw judge Report paired with its human gold — the unit we persist so
    confidence sweeps and error inspection never need another (paid) judge call."""

    report: Report
    gold: MASTGold


def save_raw_results(results: list[tuple[Report, MASTGold]], path: str | Path) -> None:
    """Persist raw (Report, gold) pairs — including every finding's confidence — as JSON."""
    payload = [JudgedTrace(report=r, gold=g).model_dump() for r, g in results]
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_raw_results(path: str | Path) -> list[tuple[Report, MASTGold]]:
    """Reload raw (Report, gold) pairs saved by ``save_raw_results``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(JudgedTrace.model_validate(d).report, JudgedTrace.model_validate(d).gold)
            for d in data]


def sweep_thresholds(
    results: list[tuple[Report, MASTGold]], thresholds: Iterable[float]
) -> list[EvalReport]:
    """Re-score the same raw results at each threshold — a κ-vs-τ curve, zero API calls."""
    return [score(results, threshold=t) for t in thresholds]


# --------------------------------------------------------------------------- #
# Bootstrap confidence intervals — a point-estimate κ/P/R/F1 says nothing about
# how much to trust it on a handful of traces; the CI does. Required before
# publishing any number per evals/held_out.md and the design doc's success criteria.
# --------------------------------------------------------------------------- #
class CI(BaseModel):
    """One metric's point estimate plus percentile bootstrap bounds."""

    point: float | None
    lo: float | None
    hi: float | None


class ScoreCI(BaseModel):
    """Precision/recall/F1/kappa for one slice (overall or a mode), each with a CI."""

    label: str
    n: int
    precision: CI
    recall: CI
    f1: CI
    kappa: CI


class BootstrapReport(BaseModel):
    """Trace-level percentile bootstrap CIs over an EvalReport's overall + per-mode scores."""

    n_traces: int
    n_resamples: int
    ci_level: float
    seed: int
    overall: ScoreCI
    per_mode: list[ScoreCI]


def _percentile_ci(values: list[float], point_val: float | None, ci_level: float) -> CI:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return CI(point=point_val, lo=None, hi=None)
    alpha = (1 - ci_level) / 2
    lo_idx = max(0, min(len(vals) - 1, round(alpha * (len(vals) - 1))))
    hi_idx = max(0, min(len(vals) - 1, round((1 - alpha) * (len(vals) - 1))))
    return CI(point=point_val, lo=vals[lo_idx], hi=vals[hi_idx])


def bootstrap_scores(
    results: list[tuple[Report, MASTGold]],
    *,
    threshold: float = 0.0,
    n_resamples: int = 2000,
    ci_level: float = 0.95,
    seed: int = 0,
) -> BootstrapReport:
    """Trace-level nonparametric (percentile) bootstrap CI for overall + per-mode
    precision/recall/F1/kappa.

    Resamples TRACES with replacement, never individual (mode, human, judge) cells —
    cells from the same trace share judge stochasticity and trace-level context, so
    resampling at the cell level would understate variance and produce falsely narrow
    intervals. Each of ``n_resamples`` draws re-runs ``score()`` on the resampled trace
    list; bounds are the empirical ``ci_level`` percentiles of the resulting metric
    distribution (Efron's percentile bootstrap). Deterministic given ``seed`` — the CI
    recomputes from a persisted raw-results file with zero LLM calls, same as every
    other offline eval command here.

    With few traces per label (a mode with n<5 in `EvalReport.per_mode`), the interval
    will be wide. Report it as-is — a wide interval is the honest signal that the point
    estimate isn't trustworthy yet, not a bug to narrow by resampling harder.
    """
    if not results:
        raise ValueError("bootstrap_scores needs at least one result")
    rng = random.Random(seed)
    n = len(results)

    point = score(results, threshold=threshold)
    replicates = [
        score([results[rng.randrange(n)] for _ in range(n)], threshold=threshold)
        for _ in range(n_resamples)
    ]

    def _score_ci(point_score: Score, rep_scores: list[Score | None]) -> ScoreCI:
        present = [s for s in rep_scores if s is not None]
        return ScoreCI(
            label=point_score.label,
            n=point_score.n,
            precision=_percentile_ci([s.precision for s in present], point_score.precision, ci_level),
            recall=_percentile_ci([s.recall for s in present], point_score.recall, ci_level),
            f1=_percentile_ci([s.f1 for s in present], point_score.f1, ci_level),
            kappa=_percentile_ci([s.kappa for s in present], point_score.kappa, ci_level),
        )

    overall_ci = _score_ci(point.overall, [r.overall for r in replicates])

    per_mode_ci = []
    for mode_score in point.per_mode:
        rep_for_mode = [
            next((s for s in rep.per_mode if s.label == mode_score.label), None)
            for rep in replicates
        ]
        per_mode_ci.append(_score_ci(mode_score, rep_for_mode))

    return BootstrapReport(
        n_traces=n, n_resamples=n_resamples, ci_level=ci_level, seed=seed,
        overall=overall_ci, per_mode=per_mode_ci,
    )


def print_bootstrap(report: BootstrapReport) -> None:
    """Terminal summary of a bootstrap CI report."""
    lvl = f"{report.ci_level:.0%}"

    def _fmt_ci(ci: CI) -> str:
        if ci.lo is None or ci.hi is None:
            return _fmt(ci.point)
        return f"{_fmt(ci.point)} [{_fmt(ci.lo)}, {_fmt(ci.hi)}]"

    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        o = report.overall
        print(
            f"\nBootstrap {lvl} CI over {report.n_traces} trace(s), "
            f"{report.n_resamples} resamples, seed={report.seed}"
        )
        print(f"  overall: κ={_fmt_ci(o.kappa)}  P={_fmt_ci(o.precision)}  R={_fmt_ci(o.recall)}")
        for s in report.per_mode:
            print(f"  {s.label} (n={s.n}): κ={_fmt_ci(s.kappa)}  P={_fmt_ci(s.precision)}  "
                  f"R={_fmt_ci(s.recall)}")
        return

    console = Console()
    console.print(
        f"\n[bold]Bootstrap {lvl} CI[/bold] over {report.n_traces} trace(s) "
        f"({report.n_resamples} resamples, seed={report.seed})"
    )
    tab = Table(title="Point estimate [CI lo, CI hi]", show_lines=False)
    for col in ("Mode", "n", "κ", "Precision", "Recall", "F1"):
        tab.add_column(col)
    tab.add_row("overall", str(report.overall.n), _fmt_ci(report.overall.kappa),
                _fmt_ci(report.overall.precision), _fmt_ci(report.overall.recall),
                _fmt_ci(report.overall.f1))
    for s in report.per_mode:
        tab.add_row(s.label, str(s.n), _fmt_ci(s.kappa), _fmt_ci(s.precision),
                    _fmt_ci(s.recall), _fmt_ci(s.f1))
    console.print(tab)


# --------------------------------------------------------------------------- #
# Multi-run aggregation — the judge is stochastic (adaptive thinking, no seed),
# so a single run's κ is one draw. Run N times and report the distribution.
# --------------------------------------------------------------------------- #
class AggregateReport(BaseModel):
    """κ across N judge runs on the same traces, plus which cells drive the variance."""

    n_runs: int
    per_run_kappa: list[float | None]
    mean_kappa: float | None
    std_kappa: float | None
    min_kappa: float | None
    max_kappa: float | None
    mean_precision: float | None
    mean_recall: float | None
    unstable_cells: list[str] = Field(
        default_factory=list,
        description="'trace_id/FM-id (k/N)' cells the judge fired in some but not all runs "
        "— the source of the run-to-run κ swing.",
    )


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _std(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return 0.0 if xs else None
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def aggregate_runs(
    runs: list[list[tuple[Report, MASTGold]]], *, threshold: float = 0.0
) -> AggregateReport:
    """Score each of N judge runs and summarise the κ distribution.

    Every run must cover the same traces (same gold). ``unstable_cells`` lists the
    (trace, mode) cells whose fired-status is not unanimous across runs — those, not the
    stable ones, are what make κ wobble between runs."""
    if not runs:
        raise ValueError("aggregate_runs needs at least one run")
    reports = [score(r, threshold=threshold) for r in runs]
    kappas = [r.overall.kappa for r in reports]
    precisions = [r.overall.precision for r in reports if r.overall.precision is not None]
    recalls = [r.overall.recall for r in reports if r.overall.recall is not None]
    valid_k = [k for k in kappas if k is not None]

    # Count, per (trace, mode) within each trace's labelable universe, how many runs fired.
    fire_counts: dict[tuple[str, str], int] = {}
    for run in runs:
        for report, gold in run:
            fired = modes_fired_at(report, threshold)
            for mode in gold.present:
                fire_counts.setdefault((gold.trace_id, mode), 0)
                if mode in fired:
                    fire_counts[(gold.trace_id, mode)] += 1
    n = len(runs)
    unstable = sorted(
        f"{tid}/{mode} ({c}/{n})"
        for (tid, mode), c in fire_counts.items()
        if 0 < c < n
    )

    return AggregateReport(
        n_runs=n,
        per_run_kappa=kappas,
        mean_kappa=_mean(valid_k),
        std_kappa=_std(valid_k),
        min_kappa=min(valid_k) if valid_k else None,
        max_kappa=max(valid_k) if valid_k else None,
        mean_precision=_mean(precisions),
        mean_recall=_mean(recalls),
        unstable_cells=unstable,
    )


def print_aggregate(agg: AggregateReport) -> None:
    """Terminal summary of a multi-run aggregate."""
    ks = "  ".join(_fmt(k) for k in agg.per_run_kappa)
    print(
        f"\nκ over {agg.n_runs} run(s): mean {_fmt(agg.mean_kappa)} "
        f"± {_fmt(agg.std_kappa)}  (min {_fmt(agg.min_kappa)}, max {_fmt(agg.max_kappa)})\n"
        f"  per-run κ: {ks}\n"
        f"  mean precision {_fmt(agg.mean_precision)}, recall {_fmt(agg.mean_recall)} "
        f"(paper human κ = 0.88)"
    )
    if agg.unstable_cells:
        print(
            f"  {len(agg.unstable_cells)} unstable cell(s) (fired in some runs, not all) "
            f"— the κ-swing source:"
        )
        for cell in agg.unstable_cells:
            print(f"    {cell}")


# --------------------------------------------------------------------------- #
# Baseline-vs-new diff — after a taxonomy edit, only the CHANGED (trace, mode)
# cells need re-adjudication. This finds them and says if the change helped.
# --------------------------------------------------------------------------- #
class CellChange(BaseModel):
    """One (trace, mode) cell whose judge fired-status changed between two runs."""

    trace_id: str
    mode: str
    gold: bool
    baseline_fired: bool
    new_fired: bool
    verdict: str = Field(
        description="toward_gold | away_from_gold — did the change move the judge "
        "closer to or further from the human label?"
    )


def diff_runs(
    baseline: list[tuple[Report, MASTGold]],
    new: list[tuple[Report, MASTGold]],
    *,
    threshold: float = 0.0,
) -> list[CellChange]:
    """List the (trace, mode) cells whose judge fired-status flipped between ``baseline``
    and ``new``, tagged toward/away from the human gold. Only these cells need
    re-adjudication after a taxonomy edit — the unchanged ones keep their prior verdict.

    Cells are compared within each trace's labelable universe (``gold.present``). Traces
    absent from either run, or modes outside the universe, are skipped."""
    base_fired = {
        g.trace_id: (modes_fired_at(r, threshold), g) for r, g in baseline
    }
    changes: list[CellChange] = []
    for report, gold in new:
        if gold.trace_id not in base_fired:
            continue
        old_fired, _ = base_fired[gold.trace_id]
        new_fired = modes_fired_at(report, threshold)
        for mode, present in gold.present.items():
            was, now = mode in old_fired, mode in new_fired
            if was == now:
                continue
            # 'now' agrees with gold => toward; else away.
            verdict = "toward_gold" if now == present else "away_from_gold"
            changes.append(
                CellChange(
                    trace_id=gold.trace_id, mode=mode, gold=present,
                    baseline_fired=was, new_fired=now, verdict=verdict,
                )
            )
    return sorted(changes, key=lambda c: (c.trace_id, c.mode))


def print_diff(changes: list[CellChange]) -> None:
    """Terminal summary of a baseline-vs-new cell diff."""
    if not changes:
        print("No cells changed fired-status between the two runs.")
        return
    toward = sum(c.verdict == "toward_gold" for c in changes)
    away = len(changes) - toward
    print(
        f"\n{len(changes)} changed cell(s): {toward} toward gold, {away} away from gold "
        f"(re-adjudicate these; the rest keep their prior verdict)\n"
    )
    for c in changes:
        arrow = "fired" if c.new_fired else "silent"
        was = "fired" if c.baseline_fired else "silent"
        flag = "✓" if c.verdict == "toward_gold" else "✗"
        print(
            f"  {flag} {c.trace_id}/{c.mode}: {was}→{arrow}  "
            f"(gold={'present' if c.gold else 'absent'}, {c.verdict})"
        )


def print_sweep(reports: list[EvalReport]) -> None:
    """Terminal table of overall κ / precision / recall across confidence thresholds."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        for r in reports:
            o = r.overall
            print(f"τ={r.threshold:.2f}  κ={_fmt(o.kappa)}  P={_fmt(o.precision)}  "
                  f"R={_fmt(o.recall)}")
        return
    console = Console()
    tab = Table(title="κ vs. confidence threshold τ")
    for col in ("τ", "κ", "Prec", "Rec", "TP", "FP", "FN"):
        tab.add_column(col)
    for r in reports:
        o = r.overall
        tab.add_row(f"{r.threshold:.2f}", _fmt(o.kappa), _fmt(o.precision),
                    _fmt(o.recall), str(o.tp), str(o.fp), str(o.fn))
    console.print(tab)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt(x: float | None) -> str:
    return f"{x:.2f}" if x is not None else "—"


def print_eval(report: EvalReport) -> None:
    """Terminal summary of an EvalReport."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _print_plain(report)
        return

    console = Console()
    o = report.overall
    console.print(
        f"\n[bold]Judge vs. human agreement[/bold] over {report.n_traces} trace(s) — "
        f"[bold]κ = {_fmt(o.kappa)}[/bold]  "
        f"(precision {_fmt(o.precision)}, recall {_fmt(o.recall)}, n={o.n} cells; "
        f"confidence τ={report.threshold:.2f}; paper human κ = 0.88)"
    )
    if report.unscored_findings:
        console.print(
            f"[yellow]{report.unscored_findings} judge finding(s) on modes outside a "
            f"trace's labelable taxonomy version — excluded from scoring.[/yellow]"
        )

    ver = Table(title="By taxonomy version", show_lines=False)
    for col in ("Version", "κ", "Prec", "Rec", "n"):
        ver.add_column(col)
    for s in report.by_version.values():
        ver.add_row(s.label, _fmt(s.kappa), _fmt(s.precision), _fmt(s.recall), str(s.n))
    console.print(ver)

    tab = Table(title="Per mode", show_lines=False)
    for col in ("Mode", "κ", "Prec", "Rec", "F1", "TP", "FP", "FN", "TN"):
        tab.add_column(col)
    for s in report.per_mode:
        tab.add_row(s.label, _fmt(s.kappa), _fmt(s.precision), _fmt(s.recall),
                    _fmt(s.f1), str(s.tp), str(s.fp), str(s.fn), str(s.tn))
    console.print(tab)


def _print_plain(report: EvalReport) -> None:
    o = report.overall
    print(f"Judge vs. human κ = {_fmt(o.kappa)} over {report.n_traces} traces "
          f"(prec {_fmt(o.precision)}, rec {_fmt(o.recall)}, n={o.n}; paper human κ=0.88)")
    for s in report.per_mode:
        print(f"  {s.label}: κ={_fmt(s.kappa)} P={_fmt(s.precision)} R={_fmt(s.recall)} "
              f"tp={s.tp} fp={s.fp} fn={s.fn} tn={s.tn}")
