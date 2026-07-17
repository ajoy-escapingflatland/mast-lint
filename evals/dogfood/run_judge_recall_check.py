"""Check whether a judge finding/miss on specific dogfood traces is a
systematic detection weakness or single-run stochastic noise.

The judge is known-stochastic (no seed, adaptive thinking -- see
step4-kappa-baseline memory / evals/adjudication_lever1.md). Runs the judge N
times against a small set of target traces and reports per-trace firing rates
across runs, reusing mastlint.evals.aggregate_runs the same way the original
Step 4 Lever-1 verification did (5 paid runs).

Usage:
    python evals/dogfood/run_judge_recall_check.py --runs 5 \
        --trace-ids rate-limiter,perf-optimization --out-prefix evals/dogfood/raw_recall_check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_judge import load_pairs  # noqa: E402

from mastlint.evals import (  # noqa: E402
    aggregate_runs,
    print_aggregate,
    run_judge,
    save_raw_results,
)
from mastlint.judge import DEFAULT_MODEL, AnthropicJudge  # noqa: E402

DEFAULT_TARGET_TRACE_IDS = "rate-limiter,perf-optimization"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--records", default="evals/dogfood/raw_ag2_records.json", type=Path
    )
    ap.add_argument("--gold", default="evals/dogfood/gold_labels.json", type=Path)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument(
        "--trace-ids", default=DEFAULT_TARGET_TRACE_IDS,
        help="Comma-separated raw dogfood task ids (matches TASKS[].id in run_ag2.py)",
    )
    ap.add_argument(
        "--out-prefix", default="evals/dogfood/raw_recall_check", type=Path
    )
    args = ap.parse_args()

    target_ids = {f"mad-{t.strip()}" for t in args.trace_ids.split(",") if t.strip()}
    all_pairs = load_pairs(args.records, args.gold)
    pairs = [(t, g) for t, g in all_pairs if g.trace_id in target_ids]
    assert len(pairs) == len(target_ids), (
        f"expected {len(target_ids)} target trace(s), got {len(pairs)}"
    )

    judge = AnthropicJudge(model=args.model)

    runs = []
    for run_i in range(args.runs):
        print(f"=== run {run_i + 1}/{args.runs} ===", file=sys.stderr)

        def _progress(i, trace, run_i=run_i):
            print(f"  [{i + 1}/{len(pairs)}] judging {trace.trace_id}…", file=sys.stderr)

        results = run_judge(pairs, judge, on_trace=_progress)
        runs.append(results)
        path = f"{args.out_prefix}.run{run_i + 1}.json"
        save_raw_results(results, path)
        print(f"  wrote {path}", file=sys.stderr)
        for report, gold in results:
            fired = sorted(f.failure_mode_id for f in report.findings)
            print(f"  {gold.trace_id}: fired={fired}", file=sys.stderr)

    print_aggregate(aggregate_runs(runs))


if __name__ == "__main__":
    main()
