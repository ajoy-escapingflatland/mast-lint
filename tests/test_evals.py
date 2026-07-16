"""Tests for the Step-4 κ eval harness (offline — fake judge, no API)."""
from pathlib import Path

from mastlint import evals
from mastlint.adapters import mast
from mastlint.schema import Finding, Report

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mad_human_sample.json"


# --------------------------------------------------------------------------- #
# Cohen's kappa math
# --------------------------------------------------------------------------- #
def test_kappa_perfect_agreement():
    # judge and human agree on every cell (some positive, some negative)
    assert evals.cohen_kappa(tp=5, fp=0, fn=0, tn=5) == 1.0


def test_kappa_all_negative_is_degenerate_one():
    # nobody ever fires the mode -> total chance agreement -> convention 1.0
    assert evals.cohen_kappa(tp=0, fp=0, fn=0, tn=10) == 1.0


def test_kappa_total_disagreement_is_negative():
    k = evals.cohen_kappa(tp=0, fp=5, fn=5, tn=0)
    assert k == -1.0


def test_kappa_hand_computed():
    # tp=2 fp=1 fn=1 tn=6, n=10.  po=0.8
    # judge_yes=0.3 human_yes=0.3 -> 0.09 ; judge_no=0.7 human_no=0.7 -> 0.49 ; pe=0.58
    # kappa = (0.8-0.58)/(1-0.58) = 0.22/0.42 = 0.5238...
    k = evals.cohen_kappa(tp=2, fp=1, fn=1, tn=6)
    assert abs(k - 0.5238095) < 1e-6


def test_kappa_empty_is_none():
    assert evals.cohen_kappa(0, 0, 0, 0) is None


# --------------------------------------------------------------------------- #
# Score derivation
# --------------------------------------------------------------------------- #
def test_score_precision_recall_f1():
    s = evals.Score.from_counts("FM-1.1", tp=3, fp=1, fn=1, tn=5)
    assert s.precision == 0.75
    assert s.recall == 0.75
    assert abs(s.f1 - 0.75) < 1e-9
    assert s.n == 10


# --------------------------------------------------------------------------- #
# Scoring: taxonomy-universe restriction + confusion + aggregation
# --------------------------------------------------------------------------- #
def _report(trace_id: str, modes: list[str]) -> Report:
    findings = [
        Finding(failure_mode_id=m, failure_mode_name="x", category="FC1",
                span_ids=["s1"], rationale="r", confidence=0.9)
        for m in modes
    ]
    return Report(trace_id=trace_id, findings=findings, modes_fired=sorted(set(modes)))


def test_score_confusion_within_universe():
    gold = mast.MASTGold(
        trace_id="t1", mas_name="AG2", benchmark="B", round="Round 1",
        taxonomy_version="v1", n_annotators=3,
        present={"FM-1.5": True, "FM-2.5": True, "FM-1.1": False},
    )
    # judge fires FM-1.5 (TP), misses FM-2.5 (FN), fires FM-1.1 (FP).
    report = _report("t1", ["FM-1.5", "FM-1.1"])
    ev = evals.score([(report, gold)])
    o = ev.overall
    assert (o.tp, o.fp, o.fn, o.tn) == (1, 1, 1, 0)


def test_judge_mode_outside_universe_is_unscored_not_fp():
    gold = mast.MASTGold(
        trace_id="t1", mas_name="AG2", benchmark="B", round="Round 1",
        taxonomy_version="v1", n_annotators=3,
        present={"FM-1.5": True},  # only FM-1.5 was labelable in this trace
    )
    # judge fires FM-1.5 (TP) AND FM-1.4 (not in this taxonomy version -> unscored)
    report = _report("t1", ["FM-1.5", "FM-1.4"])
    ev = evals.score([(report, gold)])
    assert ev.overall.tp == 1
    assert ev.overall.fp == 0, "a mode with no possible ground truth must not count as FP"
    assert ev.unscored_findings == 1
    assert ev.per_trace[0].unscored_judge_modes == ["FM-1.4"]


def test_by_version_split():
    g1 = mast.MASTGold(trace_id="t1", mas_name="AG2", benchmark="B", round="Round 1",
                       taxonomy_version="v1", n_annotators=3, present={"FM-1.5": True})
    g2 = mast.MASTGold(trace_id="t2", mas_name="AG2", benchmark="B",
                       round="Generlazability", taxonomy_version="final", n_annotators=3,
                       present={"FM-1.5": False})
    ev = evals.score([(_report("t1", ["FM-1.5"]), g1),
                      (_report("t2", ["FM-1.5"]), g2)])
    assert set(ev.by_version) == {"v1", "final"}
    assert ev.by_version["v1"].tp == 1          # correct fire
    assert ev.by_version["final"].fp == 1       # spurious fire


# --------------------------------------------------------------------------- #
# End-to-end
# --------------------------------------------------------------------------- #
def test_perfect_judge_scores_kappa_one_over_fixture():
    """If the judge fires exactly the human-fired modes on every real fixture trace,
    agreement is total: κ = 1.0, no FP/FN."""
    pairs = list(mast.iter_labeled_traces(FIXTURE))
    assert pairs, "fixture should yield labeled traces"
    results = [(_report(g.trace_id, g.fired), g) for _, g in pairs]
    ev = evals.score(results)
    assert ev.n_traces == len(pairs)
    assert ev.overall.fp == 0 and ev.overall.fn == 0
    assert ev.overall.kappa == 1.0


def test_evaluate_drives_the_judge_and_returns_report():
    """Exercise the evaluate() path (judge_trace per trace) with a trivial fake judge
    that always returns no findings — proves the harness runs offline end-to-end."""
    pairs = list(mast.iter_labeled_traces(FIXTURE))
    calls = []

    class SilentJudge:
        def complete(self, system, user, *, json_schema=None):
            calls.append(1)
            return '{"findings": []}'

    ev = evals.evaluate(pairs, SilentJudge())
    assert ev.n_traces == len(pairs)
    assert len(calls) == len(pairs), "judge should be called once per trace"
    # No findings -> every human-positive cell is a false negative, none are FP.
    assert ev.overall.fp == 0
    assert isinstance(ev.overall.kappa, (float, type(None)))


# --------------------------------------------------------------------------- #
# Confidence threshold + raw persistence + sweep
# --------------------------------------------------------------------------- #
def _report_conf(trace_id: str, mode_conf: dict[str, float]) -> Report:
    findings = [
        Finding(failure_mode_id=m, failure_mode_name="x", category="FC1",
                span_ids=["s1"], rationale="r", confidence=c)
        for m, c in mode_conf.items()
    ]
    return Report(trace_id=trace_id, findings=findings,
                  modes_fired=sorted(mode_conf))


def test_confidence_threshold_gates_fired_modes():
    """A low-confidence spurious finding is dropped at a higher τ, turning an FP into a
    true negative and lifting agreement."""
    gold = mast.MASTGold(
        trace_id="t1", mas_name="AG2", benchmark="B", round="Round 1",
        taxonomy_version="v1", n_annotators=3,
        present={"FM-1.5": True, "FM-1.1": False},
    )
    # judge: FM-1.5 confident (TP), FM-1.1 weak (spurious)
    report = _report_conf("t1", {"FM-1.5": 0.9, "FM-1.1": 0.3})
    lo = evals.score([(report, gold)], threshold=0.0)
    hi = evals.score([(report, gold)], threshold=0.5)
    assert (lo.overall.tp, lo.overall.fp) == (1, 1)
    assert (hi.overall.tp, hi.overall.fp) == (1, 0)  # weak FM-1.1 no longer counts
    assert hi.threshold == 0.5


def test_raw_results_roundtrip_preserves_confidence(tmp_path):
    gold = mast.MASTGold(
        trace_id="t1", mas_name="AG2", benchmark="B", round="Round 1",
        taxonomy_version="v1", n_annotators=3, present={"FM-1.5": True},
    )
    results = [(_report_conf("t1", {"FM-1.5": 0.42}), gold)]
    path = tmp_path / "raw.json"
    evals.save_raw_results(results, path)
    loaded = evals.load_raw_results(path)
    assert loaded[0][0].findings[0].confidence == 0.42
    assert loaded[0][1].trace_id == "t1"
    # Re-scoring the reloaded results matches scoring the originals.
    assert evals.score(loaded).overall.model_dump() == evals.score(results).overall.model_dump()


def test_sweep_thresholds_returns_one_report_per_tau():
    gold = mast.MASTGold(
        trace_id="t1", mas_name="AG2", benchmark="B", round="Round 1",
        taxonomy_version="v1", n_annotators=3, present={"FM-1.5": True, "FM-1.1": False},
    )
    results = [(_report_conf("t1", {"FM-1.5": 0.9, "FM-1.1": 0.3}), gold)]
    reports = evals.sweep_thresholds(results, [0.0, 0.5, 1.0])
    assert [r.threshold for r in reports] == [0.0, 0.5, 1.0]
    # FP present at τ=0, gone at τ=0.5.
    assert reports[0].overall.fp == 1
    assert reports[1].overall.fp == 0


# --------------------------------------------------------------------------- #
# Multi-run aggregation
# --------------------------------------------------------------------------- #
def _gold(trace_id: str, present: dict[str, bool]) -> mast.MASTGold:
    return mast.MASTGold(
        trace_id=trace_id, mas_name="AG2", benchmark="B", round="Round 1",
        taxonomy_version="v1", n_annotators=3, present=present,
    )


def test_aggregate_runs_mean_and_spread():
    gold = _gold("t1", {"FM-1.5": True, "FM-1.1": False})
    # run A: perfect (κ=1); run B: fires spurious FM-1.1 (κ<1). Mean sits between.
    run_a = [(_report("t1", ["FM-1.5"]), gold)]
    run_b = [(_report("t1", ["FM-1.5", "FM-1.1"]), gold)]
    agg = evals.aggregate_runs([run_a, run_b])
    assert agg.n_runs == 2
    assert agg.per_run_kappa[0] == 1.0
    assert agg.max_kappa == 1.0
    assert agg.min_kappa < 1.0
    assert agg.min_kappa <= agg.mean_kappa <= agg.max_kappa
    assert agg.std_kappa is not None and agg.std_kappa > 0


def test_aggregate_runs_flags_unstable_cells():
    gold = _gold("t1", {"FM-1.5": True, "FM-1.1": False})
    # FM-1.5 fires in both runs (stable); FM-1.1 fires in only one (unstable).
    run_a = [(_report("t1", ["FM-1.5"]), gold)]
    run_b = [(_report("t1", ["FM-1.5", "FM-1.1"]), gold)]
    agg = evals.aggregate_runs([run_a, run_b])
    assert agg.unstable_cells == ["t1/FM-1.1 (1/2)"]


def test_aggregate_runs_all_stable_has_no_unstable_cells():
    gold = _gold("t1", {"FM-1.5": True})
    run = [(_report("t1", ["FM-1.5"]), gold)]
    agg = evals.aggregate_runs([run, run, run])
    assert agg.unstable_cells == []
    assert agg.std_kappa == 0.0


def test_aggregate_runs_empty_raises():
    import pytest

    with pytest.raises(ValueError):
        evals.aggregate_runs([])


# --------------------------------------------------------------------------- #
# Baseline-vs-new diff
# --------------------------------------------------------------------------- #
def test_diff_runs_toward_and_away():
    gold = _gold("t1", {"FM-1.5": True, "FM-1.1": False, "FM-2.5": True})
    # baseline: fires FM-1.1 (FP) and FM-2.5 (TP), misses FM-1.5 (FN).
    baseline = [(_report("t1", ["FM-1.1", "FM-2.5"]), gold)]
    # new: drops FM-1.1 (removed FP -> toward), adds FM-1.5 (fixed FN -> toward),
    #      drops FM-2.5 (lost a TP -> away). FM-2.5 unchanged? no, it flipped.
    new = [(_report("t1", ["FM-1.5"]), gold)]
    changes = evals.diff_runs(baseline, new)
    by_mode = {c.mode: c for c in changes}
    assert by_mode["FM-1.1"].verdict == "toward_gold"   # FP removed
    assert by_mode["FM-1.5"].verdict == "toward_gold"   # FN fixed
    assert by_mode["FM-2.5"].verdict == "away_from_gold"  # TP lost
    assert by_mode["FM-1.1"].baseline_fired and not by_mode["FM-1.1"].new_fired


def test_diff_runs_unchanged_cells_omitted():
    gold = _gold("t1", {"FM-1.5": True, "FM-1.1": False})
    # identical fired sets -> no changes at all.
    same = [(_report("t1", ["FM-1.5"]), gold)]
    assert evals.diff_runs(same, [(_report("t1", ["FM-1.5"]), gold)]) == []


def test_diff_runs_skips_traces_absent_from_baseline():
    gold1 = _gold("t1", {"FM-1.5": True})
    gold2 = _gold("t2", {"FM-1.5": True})
    baseline = [(_report("t1", []), gold1)]
    new = [(_report("t1", ["FM-1.5"]), gold1), (_report("t2", ["FM-1.5"]), gold2)]
    changes = evals.diff_runs(baseline, new)
    # t2 has no baseline to diff against -> only t1's flip is reported.
    assert [c.trace_id for c in changes] == ["t1"]
