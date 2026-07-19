"""Tests for cli.py — all offline: the judge is always a fake/mocked client, never a
real AnthropicJudge / network call. See CLAUDE.md for the never-pay-for-tests rule."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from typer.testing import CliRunner

import mastlint.judge as J
from mastlint.adapters.mast import MASTGold
from mastlint.cli import app
from mastlint.evals import save_raw_results
from mastlint.schema import Finding, Report

runner = CliRunner()

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "trace.example.json"
DATASET_FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mad_human_sample.json"
)


def _report(trace_id: str, modes: list[str], confidence: float = 0.9) -> Report:
    findings = [
        Finding(failure_mode_id=m, failure_mode_name="x", category="FC1",
                span_ids=["s1"], rationale="r", confidence=confidence)
        for m in modes
    ]
    return Report(trace_id=trace_id, findings=findings, modes_fired=sorted(set(modes)))


def _gold(trace_id: str, present: dict[str, bool]) -> MASTGold:
    return MASTGold(trace_id=trace_id, mas_name="AG2", benchmark="B", round="Round 1",
                     taxonomy_version="final", n_annotators=3, present=present)


class FakeJudgeClient:
    """Minimal JudgeClient stand-in: returns a canned findings payload, no network."""

    def __init__(self, payload: str = '{"findings": []}'):
        self.payload = payload
        self.calls = 0

    def complete(self, system, user, *, json_schema=None):
        self.calls += 1
        return self.payload


# --------------------------------------------------------------------------- #
# modes — fully offline, no judge involved at all
# --------------------------------------------------------------------------- #
def test_modes_lists_all_14_failure_modes():
    result = runner.invoke(app, ["modes"])
    assert result.exit_code == 0
    assert "FM-1.1" in result.output
    assert "FM-3.3" in result.output
    assert result.output.count("FM-") >= 14


# --------------------------------------------------------------------------- #
# lint — mocked judge
# --------------------------------------------------------------------------- #
def test_lint_clean_trace_reports_no_findings(monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    result = runner.invoke(app, ["lint", str(EXAMPLE)])
    assert result.exit_code == 0
    assert "no MAST failure modes detected" in result.output


def test_lint_json_flag_emits_a_valid_report(monkeypatch):
    payload = json.dumps({"findings": [
        {"failure_mode_id": "FM-3.1", "failure_mode_name": "Premature Termination",
         "category": "FC3", "span_ids": ["s1"], "rationale": "quit early", "confidence": 0.8},
    ]})
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient(payload))
    result = runner.invoke(app, ["lint", str(EXAMPLE), "--json"])
    assert result.exit_code == 0
    report = Report.model_validate_json(result.output)
    assert report.trace_id == "example-0001"
    assert report.modes_fired == ["FM-3.1"]


def test_lint_missing_trace_file_fails_loudly():
    result = runner.invoke(app, ["lint", "does/not/exist.json"])
    assert result.exit_code != 0


def test_lint_judge_init_failure_is_a_clean_error(monkeypatch):
    class BrokenJudge:
        def __init__(self, model):
            raise RuntimeError("no credentials")

    monkeypatch.setattr(J, "AnthropicJudge", BrokenJudge)
    result = runner.invoke(app, ["lint", str(EXAMPLE)])
    assert result.exit_code != 0
    assert "Could not initialize the judge client" in result.output


def test_lint_missing_anthropic_package_suggests_the_extra(monkeypatch):
    # Setting sys.modules["anthropic"] = None forces the next `import anthropic`
    # to raise ImportError, regardless of whether the real package is installed.
    monkeypatch.setitem(sys.modules, "anthropic", None)
    result = runner.invoke(app, ["lint", str(EXAMPLE)])
    assert result.exit_code != 0
    # rich's error box can wrap the message across lines, so check the pieces
    # separately rather than one contiguous substring.
    assert "pip install" in result.output
    assert "mastlint[llm]" in result.output


def test_lint_judge_error_during_judging_exits_nonzero(monkeypatch):
    class ExplodingJudge:
        def complete(self, system, user, *, json_schema=None):
            raise J.JudgeError("simulated API failure")

    monkeypatch.setattr(J, "AnthropicJudge", lambda model: ExplodingJudge())
    result = runner.invoke(app, ["lint", str(EXAMPLE)])
    assert result.exit_code == 1
    assert "simulated API failure" in result.output


# --------------------------------------------------------------------------- #
# eval — mocked judge, small fixture dataset
# --------------------------------------------------------------------------- #
def test_eval_writes_report_and_raw_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    out = tmp_path / "report.json"
    raw_out = tmp_path / "raw.json"
    result = runner.invoke(app, [
        "eval", str(DATASET_FIXTURE), "--out", str(out), "--raw-out", str(raw_out),
    ])
    assert result.exit_code == 0
    assert out.exists()
    assert raw_out.exists()
    assert "κ" in result.output


def test_eval_json_flag_emits_a_valid_eval_report(monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    result = runner.invoke(app, ["eval", str(DATASET_FIXTURE), "--json"])
    assert result.exit_code == 0
    # progress lines go to stderr; only stdout is the --json payload
    payload = json.loads(result.stdout)
    assert "overall" in payload
    assert "n_traces" in payload


def test_eval_limit_scores_only_the_first_n_traces(monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    result = runner.invoke(app, ["eval", str(DATASET_FIXTURE), "--limit", "1", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["n_traces"] == 1


def test_eval_multi_run_writes_suffixed_raw_files(tmp_path, monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    raw_out = tmp_path / "raw.json"
    result = runner.invoke(app, [
        "eval", str(DATASET_FIXTURE), "--runs", "2", "--raw-out", str(raw_out),
    ])
    assert result.exit_code == 0
    assert (tmp_path / "raw.run1.json").exists()
    assert (tmp_path / "raw.run2.json").exists()


# --------------------------------------------------------------------------- #
# eval-sweep / eval-ci / eval-agg / eval-diff — fully offline, saved findings only
# --------------------------------------------------------------------------- #
def test_eval_sweep_offline_from_saved_raw_results(tmp_path):
    gold = _gold("t1", {"FM-1.5": True, "FM-2.5": False})
    raw = tmp_path / "raw.json"
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], raw)

    result = runner.invoke(app, ["eval-sweep", str(raw), "--steps", "3"])
    assert result.exit_code == 0
    assert "κ" in result.output or "kappa" in result.output.lower()


def test_eval_ci_offline_bootstrap(tmp_path):
    gold = _gold("t1", {"FM-1.5": True})
    raw = tmp_path / "raw.json"
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], raw)

    result = runner.invoke(app, ["eval-ci", str(raw), "--resamples", "100"])
    assert result.exit_code == 0


def test_eval_agg_across_two_runs(tmp_path):
    gold = _gold("t1", {"FM-1.5": True})
    raw1 = tmp_path / "raw1.json"
    raw2 = tmp_path / "raw2.json"
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], raw1)
    save_raw_results([(_report("t1", []), gold)], raw2)

    result = runner.invoke(app, ["eval-agg", str(raw1), str(raw2)])
    assert result.exit_code == 0


def test_eval_diff_flags_cells_that_flipped(tmp_path):
    gold = _gold("t1", {"FM-1.5": True})
    baseline = tmp_path / "baseline.json"
    new = tmp_path / "new.json"
    save_raw_results([(_report("t1", []), gold)], baseline)
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], new)

    result = runner.invoke(app, ["eval-diff", str(baseline), str(new)])
    assert result.exit_code == 0
    assert "FM-1.5" in result.output


def test_eval_diff_no_changes_says_so(tmp_path):
    gold = _gold("t1", {"FM-1.5": True})
    baseline = tmp_path / "baseline.json"
    new = tmp_path / "new.json"
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], baseline)
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], new)

    result = runner.invoke(app, ["eval-diff", str(baseline), str(new)])
    assert result.exit_code == 0
    assert "No cells changed" in result.output


def test_eval_ci_json_flag_emits_a_valid_bootstrap_report(tmp_path):
    gold = _gold("t1", {"FM-1.5": True})
    raw = tmp_path / "raw.json"
    save_raw_results([(_report("t1", ["FM-1.5"]), gold)], raw)

    result = runner.invoke(app, ["eval-ci", str(raw), "--resamples", "100", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "overall" in payload
    assert "ci_level" in payload


# --------------------------------------------------------------------------- #
# eval — --segmented-only skip message, and eval's own judge-init/JudgeError
# error paths (same shape as lint's, exercised separately since it's distinct code)
# --------------------------------------------------------------------------- #
def _dataset_with_one_blob_trace(tmp_path) -> Path:
    """A 2-record dataset: one real AG2 record (segmented) copied from the shared
    fixture, plus one synthetic record whose framework has no parser at all, so it
    falls back to a single raw blob span -- exactly what --segmented-only should skip."""
    records = json.loads(DATASET_FIXTURE.read_text(encoding="utf-8"))
    blob_record = {
        "round": "Round 1",
        "mas_name": "TotallyUnknownFramework",
        "benchmark_name": "X",
        "trace_id": 999,
        "trace": "some unparsed raw transcript text",
        "annotations": [],
    }
    path = tmp_path / "mixed.json"
    path.write_text(json.dumps([records[0], blob_record]), encoding="utf-8")
    return path


def test_eval_segmented_only_skips_blob_traces_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    dataset = _dataset_with_one_blob_trace(tmp_path)

    result = runner.invoke(app, ["eval", str(dataset), "--segmented-only"])
    assert result.exit_code == 0
    assert "Scoring 1 segmented trace(s); skipping 1 blob-only trace(s)" in result.output


def test_eval_without_segmented_only_scores_the_blob_trace_too(tmp_path, monkeypatch):
    monkeypatch.setattr(J, "AnthropicJudge", lambda model: FakeJudgeClient())
    dataset = _dataset_with_one_blob_trace(tmp_path)

    result = runner.invoke(app, ["eval", str(dataset)])
    assert result.exit_code == 0
    assert "skipping" not in result.output


def test_eval_judge_init_failure_is_a_clean_error(monkeypatch):
    class BrokenJudge:
        def __init__(self, model):
            raise RuntimeError("no credentials")

    monkeypatch.setattr(J, "AnthropicJudge", BrokenJudge)
    result = runner.invoke(app, ["eval", str(DATASET_FIXTURE)])
    assert result.exit_code != 0
    assert "Could not initialize the judge client" in result.output


def test_eval_missing_anthropic_package_suggests_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    result = runner.invoke(app, ["eval", str(DATASET_FIXTURE)])
    assert result.exit_code != 0
    # rich's error box can wrap the message across lines, so check the pieces
    # separately rather than one contiguous substring.
    assert "pip install" in result.output
    assert "mastlint[llm]" in result.output


def test_eval_judge_error_during_run_exits_nonzero(monkeypatch):
    class ExplodingJudge:
        def complete(self, system, user, *, json_schema=None):
            raise J.JudgeError("simulated API failure")

    monkeypatch.setattr(J, "AnthropicJudge", lambda model: ExplodingJudge())
    result = runner.invoke(app, ["eval", str(DATASET_FIXTURE)])
    assert result.exit_code == 1
    assert "simulated API failure" in result.output
