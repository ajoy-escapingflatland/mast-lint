"""Tests for segment.py (Step 3 stub: one window = the whole trace)."""
from mastlint.schema import Span, Trace
from mastlint.segment import windows


def _spans(*ids: str) -> list[Span]:
    return [Span(span_id=i, agent="a", content=f"content {i}") for i in ids]


def _trace(spans: list[Span]) -> Trace:
    return Trace(trace_id="t1", spans=spans)


def test_windows_returns_a_single_window():
    trace = _trace(_spans("s1", "s2", "s3"))
    result = windows(trace)
    assert len(result) == 1


def test_windows_single_window_contains_all_spans_in_order():
    spans = _spans("s1", "s2", "s3")
    trace = _trace(spans)
    result = windows(trace)
    assert result[0] == spans


def test_windows_on_empty_trace_returns_one_empty_window():
    trace = _trace([])
    result = windows(trace)
    assert result == [[]]


def test_windows_on_single_span_trace():
    spans = _spans("only")
    trace = _trace(spans)
    result = windows(trace)
    assert result == [spans]
