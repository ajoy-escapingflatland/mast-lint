"""Tests for report.py — pure rendering, no network, no API cost."""
import sys

from mastlint.report import _print_plain, print_human, to_json
from mastlint.schema import Finding, Report


def _finding(mode_id: str, confidence: float, span: str = "s1", rationale: str = "why") -> Finding:
    return Finding(
        failure_mode_id=mode_id,
        failure_mode_name=f"name-{mode_id}",
        category="FC1",
        span_ids=[span],
        rationale=rationale,
        confidence=confidence,
    )


# --------------------------------------------------------------------------- #
# to_json
# --------------------------------------------------------------------------- #
def test_to_json_round_trips():
    report = Report(trace_id="t1", findings=[_finding("FM-1.2", 0.5)], modes_fired=["FM-1.2"])
    payload = to_json(report)
    assert Report.model_validate_json(payload) == report


def test_to_json_on_no_findings():
    report = Report(trace_id="clean", findings=[], modes_fired=[])
    payload = to_json(report)
    assert Report.model_validate_json(payload) == report


# --------------------------------------------------------------------------- #
# print_human — rich available (the normal path in this project's venv)
# --------------------------------------------------------------------------- #
def test_print_human_no_findings_prints_all_clear(capsys):
    report = Report(trace_id="clean-trace", findings=[], modes_fired=[])
    print_human(report)
    out = capsys.readouterr().out
    assert "clean-trace" in out
    assert "no MAST failure modes detected" in out


def test_print_human_sorts_by_mode_then_confidence_desc(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    report = Report(
        trace_id="t1",
        findings=[
            _finding("FM-1.2", 0.3, span="low"),
            _finding("FM-3.2", 0.5, span="mid"),
            _finding("FM-1.2", 0.9, span="high"),
        ],
        modes_fired=["FM-1.2", "FM-3.2"],
    )
    print_human(report)
    out = capsys.readouterr().out
    # sort key is (mode_id, -confidence): FM-1.2/0.9, then FM-1.2/0.3, then FM-3.2/0.5
    assert out.index("high") < out.index("low") < out.index("mid")


def test_print_human_summary_line_reports_count_and_modes(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    report = Report(
        trace_id="t1",
        findings=[_finding("FM-1.2", 0.5), _finding("FM-3.2", 0.5)],
        modes_fired=["FM-1.2", "FM-3.2"],
    )
    print_human(report)
    out = capsys.readouterr().out
    assert "2 finding(s)" in out
    assert "2 mode(s)" in out
    assert "FM-1.2, FM-3.2" in out


# --------------------------------------------------------------------------- #
# print_human — rich missing: falls back to plain text
# --------------------------------------------------------------------------- #
def test_print_human_falls_back_to_plain_when_rich_missing(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "rich.console", None)
    monkeypatch.setitem(sys.modules, "rich.table", None)
    report = Report(trace_id="t1", findings=[_finding("FM-1.2", 0.5, span="s9")],
                     modes_fired=["FM-1.2"])
    print_human(report)
    out = capsys.readouterr().out
    assert "MAST findings — t1" in out
    assert "FM-1.2" in out
    assert "s9" in out
    # plain text output draws no box-drawing table borders
    assert "┃" not in out and "─" not in out


def test_print_human_no_findings_falls_back_to_plain_when_rich_missing(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "rich.console", None)
    monkeypatch.setitem(sys.modules, "rich.table", None)
    report = Report(trace_id="clean-trace", findings=[], modes_fired=[])
    print_human(report)
    out = capsys.readouterr().out
    assert out.strip() == "OK clean-trace: no MAST failure modes detected."


# --------------------------------------------------------------------------- #
# _print_plain — direct
# --------------------------------------------------------------------------- #
def test_print_plain_with_findings_includes_rationale(capsys):
    report = Report(
        trace_id="t1",
        findings=[_finding("FM-1.2", 0.42, span="s9", rationale="because x")],
        modes_fired=["FM-1.2"],
    )
    _print_plain(report)
    out = capsys.readouterr().out
    assert "FM-1.2" in out
    assert "s9" in out
    assert "0.42" in out
    assert "because x" in out
