"""Run mast-lint's judge against the Step 5 dogfood traces and score against
`gold_labels.json`.

Deliberately NOT `mast-lint eval`: that command's scoring path goes through
`adapters/mast.py::gold_labels()`, which reads a MAD record's `annotations`
field. Dogfood records have no `annotations` (there was no 3-annotator panel
here) — running the existing command as-is would silently score zero cells,
not fail loudly. This script builds `MASTGold` objects directly from the
single-annotator `gold_labels.json` written in the blind-labeling pass
instead, and reuses everything else (`to_trace`, `judge_trace`, `score`,
`bootstrap_scores`) unchanged.

Usage:
    python evals/dogfood/run_judge.py \
        --raw-out evals/dogfood/raw_judge_results.json \
        --out evals/dogfood/judge_report.json

Requires ANTHROPIC_API_KEY. One judge call per trace (8 calls, model
claude-opus-4-8 by default — same as the rest of Step 4).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from mastlint.adapters.mast import MASTGold, to_trace  # noqa: E402
from mastlint.evals import (  # noqa: E402
    bootstrap_scores,
    print_bootstrap,
    print_eval,
    run_judge,
    save_raw_results,
    score,
)
from mastlint.judge import DEFAULT_MODEL, AnthropicJudge  # noqa: E402
from mastlint.schema import Trace  # noqa: E402

ALL_MODES = [
    "FM-1.1", "FM-1.2", "FM-1.3", "FM-1.4", "FM-1.5",
    "FM-2.1", "FM-2.2", "FM-2.3", "FM-2.4", "FM-2.5", "FM-2.6",
    "FM-3.1", "FM-3.2", "FM-3.3",
]


def load_pairs(records_path: Path, gold_path: Path) -> list[tuple[Trace, MASTGold]]:
    records = json.loads(records_path.read_text(encoding="utf-8"))
    gold_data = json.loads(gold_path.read_text(encoding="utf-8"))["labels"]

    pairs: list[tuple[Trace, MASTGold]] = []
    for record in records:
        trace = to_trace(record)
        raw_id = record["trace_id"]
        present_modes = set(gold_data[raw_id]["present"])
        gold = MASTGold(
            trace_id=trace.trace_id,
            mas_name=record["mas_name"],
            benchmark=record["benchmark_name"],
            round=record["round"],
            taxonomy_version="final",
            n_annotators=1,
            present={m: (m in present_modes) for m in ALL_MODES},
            votes={m: [m in present_modes] for m in ALL_MODES},
            unmapped={},
        )
        pairs.append((trace, gold))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--records", default="evals/dogfood/raw_ag2_records.json", type=Path
    )
    ap.add_argument("--gold", default="evals/dogfood/gold_labels.json", type=Path)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--raw-out", default="evals/dogfood/raw_judge_results.json", type=Path)
    ap.add_argument("--out", default="evals/dogfood/judge_report.json", type=Path)
    args = ap.parse_args()

    pairs = load_pairs(args.records, args.gold)
    judge = AnthropicJudge(model=args.model)

    def _progress(i, trace):
        print(f"[{i + 1}/{len(pairs)}] judging {trace.trace_id} ({trace.framework})…",
              file=sys.stderr)

    results = run_judge(pairs, judge, on_trace=_progress)
    save_raw_results(results, args.raw_out)
    print(f"Wrote raw judge results to {args.raw_out}", file=sys.stderr)

    report = score(results)
    args.out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote score report to {args.out}", file=sys.stderr)
    print_eval(report)

    if len(results) >= 2:
        print_bootstrap(bootstrap_scores(results, n_resamples=2000, seed=0))
    else:
        print("\n(skipping bootstrap CI: need >=2 traces)", file=sys.stderr)


if __name__ == "__main__":
    main()
