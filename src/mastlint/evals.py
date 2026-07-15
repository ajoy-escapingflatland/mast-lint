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
