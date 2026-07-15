"""mast-lint CLI.  `mast-lint lint trace.json`"""
from __future__ import annotations

from pathlib import Path

import typer

from .judge import DEFAULT_MODEL, JudgeError, judge_trace
from .report import print_human, to_json
from .schema import Trace

app = typer.Typer(add_completion=False, help="Lint multi-agent LLM traces against MAST.")


@app.command()
def lint(
    trace_path: Path = typer.Argument(..., help="Path to a canonical trace JSON file"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Judge model id"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
):
    """Classify failures in a single trace with the LLM judge."""
    trace = Trace.model_validate_json(Path(trace_path).read_text(encoding="utf-8"))

    try:
        from .judge import AnthropicJudge

        judge = AnthropicJudge(model=model)
    except ImportError:
        raise typer.BadParameter(
            "The LLM judge needs the 'anthropic' package. Install it with: "
            "pip install 'mastlint[llm]'"
        ) from None
    except Exception as exc:  # noqa: BLE001 — surface auth/client setup failures cleanly
        raise typer.BadParameter(
            f"Could not initialize the judge client: {exc}. "
            "Set ANTHROPIC_API_KEY or run `ant auth login`."
        ) from None

    try:
        report = judge_trace(trace, judge)
    except JudgeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    if as_json:
        print(to_json(report), end="")
    else:
        print_human(report)


@app.command("eval")
def eval_cmd(
    dataset: Path = typer.Argument(..., help="Path to MAD_human_labelled_dataset.json"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Judge model id"),
    limit: int = typer.Option(0, "--limit", help="Only score the first N traces (0 = all)"),
    segmented_only: bool = typer.Option(
        False, "--segmented-only",
        help="Score only traces the adapter parsed into real spans (skip blob-only "
        "frameworks). Recommended: blob traces can't carry span-level evidence.",
    ),
    out: Path = typer.Option(
        None, "--out", help="Write the full EvalReport JSON here (the published κ artifact)"
    ),
    raw_out: Path = typer.Option(
        None, "--raw-out",
        help="Write raw per-trace findings (with confidence) here for offline re-scoring "
        "and `eval-sweep` — no need to re-run the paid judge.",
    ),
    confidence_threshold: float = typer.Option(
        0.0, "--confidence-threshold", min=0.0, max=1.0,
        help="Only count a mode as fired when a finding's confidence ≥ this (trades recall "
        "for precision).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of tables"),
):
    """Measure the judge's Cohen's κ against the MAST human gold labels (Step 4)."""
    from .adapters.mast import iter_labeled_traces
    from .evals import print_eval, run_judge, save_raw_results, score

    all_pairs = list(iter_labeled_traces(dataset))
    pairs = list(iter_labeled_traces(dataset, segmented_only=segmented_only))
    skipped = len(all_pairs) - len(pairs)
    if segmented_only and skipped:
        typer.echo(
            f"Scoring {len(pairs)} segmented trace(s); skipping {skipped} blob-only "
            f"trace(s) with no span-level evidence.",
            err=True,
        )
    if limit > 0:
        pairs = pairs[:limit]

    try:
        from .judge import AnthropicJudge

        judge = AnthropicJudge(model=model)
    except ImportError:
        raise typer.BadParameter(
            "The judge needs the 'anthropic' package: pip install 'mastlint[llm]'"
        ) from None
    except Exception as exc:  # noqa: BLE001
        raise typer.BadParameter(
            f"Could not initialize the judge client: {exc}. "
            "Set ANTHROPIC_API_KEY or run `ant auth login`."
        ) from None

    def _progress(i, trace):
        typer.echo(f"[{i + 1}/{len(pairs)}] judging {trace.trace_id} ({trace.framework})…",
                   err=True)

    try:
        results = run_judge(pairs, judge, on_trace=_progress)
    except JudgeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    if raw_out is not None:  # persist first — the paid pass is done, never lose it
        save_raw_results(results, raw_out)
        typer.echo(f"Wrote raw findings to {raw_out}", err=True)

    report = score(results, threshold=confidence_threshold)

    if out is not None:
        out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"Wrote κ report to {out}", err=True)

    if as_json:
        print(report.model_dump_json(indent=2))
    else:
        print_eval(report)


@app.command("eval-sweep")
def eval_sweep(
    raw_in: Path = typer.Argument(..., help="Raw findings JSON from `eval --raw-out`"),
    steps: int = typer.Option(11, "--steps", help="Number of τ points from 0.0 to 1.0"),
):
    """Re-score saved judge findings across confidence thresholds τ (offline, no API
    calls) to find the κ-maximizing cutoff."""
    from .evals import load_raw_results, print_sweep, sweep_thresholds

    results = load_raw_results(raw_in)
    thresholds = [i / (steps - 1) for i in range(steps)] if steps > 1 else [0.0]
    print_sweep(sweep_thresholds(results, thresholds))


@app.command()
def modes():
    """List the 14 MAST failure modes this linter checks for."""
    from .taxonomy import failure_modes

    for fm in failure_modes():
        typer.echo(f"{fm.id:8} {fm.name:32} [{fm.category}]")


if __name__ == "__main__":
    app()
