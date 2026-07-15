"""Tests for the LLM-as-judge (Step 3).

No network / no API cost: a FakeJudge implements the JudgeClient protocol and returns
canned JSON, so we exercise prompt rendering, output parsing, the evidence contract,
and the end-to-end pipeline deterministically.
"""
import json
from pathlib import Path

import pytest

from mastlint import judge as J
from mastlint.schema import Span, Trace
from mastlint.taxonomy import failure_modes

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "trace.example.json"


class FakeJudge:
    """Canned JudgeClient. Records the last prompt so tests can assert on it."""

    def __init__(self, payload: str):
        self.payload = payload
        self.last_system = ""
        self.last_user = ""
        self.last_schema = None

    def complete(self, system: str, user: str, *, json_schema=None) -> str:
        self.last_system, self.last_user, self.last_schema = system, user, json_schema
        return self.payload


def _spans(*ids: str) -> list[Span]:
    return [Span(span_id=i, agent="a", content=f"content {i}") for i in ids]


# --------------------------------------------------------------------------- #
# Prompt rendering
# --------------------------------------------------------------------------- #
def test_system_prompt_lists_all_14_modes_with_definitions():
    prompt = J.render_system_prompt()
    for fm in failure_modes():
        assert fm.id in prompt, f"{fm.id} missing from judge prompt"
        assert fm.name in prompt
    # near-miss boundaries (the IP) must reach the judge
    assert "NOT FM-3.1 when" in prompt
    assert "{{TAXONOMY}}" not in prompt, "template placeholder should be substituted"


def test_serialize_spans_includes_ids_task_and_content():
    text = J.serialize_spans(_spans("s1", "s2"), task="do the thing")
    assert "do the thing" in text
    assert "[s1]" in text and "[s2]" in text
    assert "content s1" in text


def test_serialize_spans_truncates_huge_span():
    big = Span(span_id="s1", agent="a", content="x" * (J.MAX_CHARS_PER_SPAN + 500))
    text = J.serialize_spans([big])
    assert "[truncated]" in text
    assert len(text) < J.MAX_CHARS_PER_SPAN + 500


def test_findings_schema_enum_matches_taxonomy():
    schema = J.findings_schema()
    enum = schema["properties"]["findings"]["items"]["properties"]["failure_mode_id"]["enum"]
    assert set(enum) == {m.id for m in failure_modes()}


# --------------------------------------------------------------------------- #
# Output parsing — the evidence contract
# --------------------------------------------------------------------------- #
def test_parse_valid_finding():
    raw = json.dumps({"findings": [{
        "failure_mode_id": "FM-3.1", "failure_mode_name": "whatever",
        "category": "FCX", "span_ids": ["s1"], "rationale": "stopped early",
        "confidence": 0.9,
    }]})
    findings = J.parse_findings(raw, {"s1", "s2"})
    assert len(findings) == 1
    f = findings[0]
    assert f.failure_mode_id == "FM-3.1"
    # name/category are taken from the taxonomy, not the model's text
    assert f.failure_mode_name == "Premature Termination"
    assert f.category == "FC3"
    assert f.span_ids == ["s1"]


def test_hallucinated_span_ids_are_dropped():
    raw = json.dumps({"findings": [{
        "failure_mode_id": "FM-3.1", "failure_mode_name": "x", "category": "FC3",
        "span_ids": ["s1", "s999"], "rationale": "r", "confidence": 0.8,
    }]})
    findings = J.parse_findings(raw, {"s1"})
    assert findings[0].span_ids == ["s1"], "unknown span id must be filtered out"


def test_finding_with_no_valid_span_is_dropped():
    raw = json.dumps({"findings": [{
        "failure_mode_id": "FM-3.1", "failure_mode_name": "x", "category": "FC3",
        "span_ids": ["ghost"], "rationale": "r", "confidence": 0.8,
    }]})
    assert J.parse_findings(raw, {"s1"}) == [], "no evidence -> no finding"


def test_unknown_mode_id_is_dropped():
    raw = json.dumps({"findings": [{
        "failure_mode_id": "FM-9.9", "failure_mode_name": "x", "category": "FCZ",
        "span_ids": ["s1"], "rationale": "r", "confidence": 0.8,
    }]})
    assert J.parse_findings(raw, {"s1"}) == []


def test_confidence_is_clamped():
    raw = json.dumps({"findings": [{
        "failure_mode_id": "FM-3.1", "failure_mode_name": "x", "category": "FC3",
        "span_ids": ["s1"], "rationale": "r", "confidence": 5.0,
    }]})
    assert J.parse_findings(raw, {"s1"})[0].confidence == 1.0


def test_parse_handles_code_fence_and_bare_list():
    fenced = "```json\n" + json.dumps({"findings": [{
        "failure_mode_id": "FM-3.2", "failure_mode_name": "x", "category": "FC3",
        "span_ids": ["s1"], "rationale": "r", "confidence": 0.7}]}) + "\n```"
    assert len(J.parse_findings(fenced, {"s1"})) == 1

    bare = json.dumps([{
        "failure_mode_id": "FM-3.2", "failure_mode_name": "x", "category": "FC3",
        "span_ids": ["s1"], "rationale": "r", "confidence": 0.7}])
    assert len(J.parse_findings(bare, {"s1"})) == 1


def test_parse_empty_and_garbage():
    assert J.parse_findings('{"findings": []}', {"s1"}) == []
    assert J.parse_findings("not json at all", {"s1"}) == []


# --------------------------------------------------------------------------- #
# Judging pipeline
# --------------------------------------------------------------------------- #
def test_judge_window_passes_schema_and_returns_findings():
    payload = json.dumps({"findings": [{
        "failure_mode_id": "FM-2.6", "failure_mode_name": "x", "category": "FC2",
        "span_ids": ["s1"], "rationale": "reasoning-action mismatch", "confidence": 0.6}]})
    fake = FakeJudge(payload)
    findings = J.judge_window(_spans("s1"), fake, task="t")
    assert fake.last_schema is not None, "schema should be offered to the client"
    assert findings[0].failure_mode_id == "FM-2.6"


def test_judge_window_empty_spans_short_circuits():
    fake = FakeJudge("{}")
    assert J.judge_window([], fake) == []
    assert fake.last_user == "", "no LLM call should be made for empty input"


def test_judge_trace_surfaces_known_example_labels():
    """Roadmap Step-3 acceptance: the example trace's known labels (FM-3.1 + FM-3.2)
    flow end-to-end from judge output into the Report. (Judge is faked; this pins the
    plumbing, not the model.)"""
    trace = Trace.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    span_ids = [s.span_id for s in trace.spans]
    payload = json.dumps({"findings": [
        {"failure_mode_id": "FM-3.1", "failure_mode_name": "x", "category": "FC3",
         "span_ids": [span_ids[-1]], "rationale": "planner declared done before tester ran",
         "confidence": 0.9},
        {"failure_mode_id": "FM-3.2", "failure_mode_name": "x", "category": "FC3",
         "span_ids": [span_ids[-1]], "rationale": "no test was ever run", "confidence": 0.85},
    ]})
    report = J.judge_trace(trace, FakeJudge(payload))
    assert report.trace_id == trace.trace_id
    assert report.modes_fired == ["FM-3.1", "FM-3.2"]
    assert {f.failure_mode_id for f in report.findings} == {"FM-3.1", "FM-3.2"}


# --------------------------------------------------------------------------- #
# AnthropicJudge request/response handling (mock client, no network)
# --------------------------------------------------------------------------- #
class _MockBlock:
    def __init__(self, type_, text=""):
        self.type = type_
        self.text = text


class _MockResp:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class _MockMessages:
    def __init__(self, resp=None, raiser=None):
        self._resp, self._raiser = resp, raiser
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raiser:
            raise self._raiser
        return self._resp


class _MockClient:
    def __init__(self, resp=None, raiser=None):
        self.messages = _MockMessages(resp, raiser)


def test_anthropic_judge_builds_request_and_extracts_text_block():
    # Real responses put thinking block(s) before the text block; we must skip them.
    resp = _MockResp([_MockBlock("thinking", ""), _MockBlock("text", '{"findings": []}')])
    client = _MockClient(resp=resp)
    judge = J.AnthropicJudge(model="claude-opus-4-8", client=client)
    out = judge.complete("SYS", "USER", json_schema=J.findings_schema())
    assert out == '{"findings": []}'
    kw = client.messages.last_kwargs
    assert kw["model"] == "claude-opus-4-8"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"]["format"]["type"] == "json_schema"


def test_anthropic_judge_refusal_returns_empty_findings():
    resp = _MockResp([], stop_reason="refusal")
    judge = J.AnthropicJudge(client=_MockClient(resp=resp))
    assert J.parse_findings(judge.complete("s", "u"), set()) == []


def test_anthropic_judge_wraps_api_errors_in_judgeerror():
    judge = J.AnthropicJudge(client=_MockClient(raiser=TypeError("unexpected keyword")))
    with pytest.raises(J.JudgeError) as ei:
        judge.complete("s", "u", json_schema=J.findings_schema())
    assert "anthropic" in str(ei.value)  # message points at the likely fix
