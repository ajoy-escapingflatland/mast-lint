"""Tests for the MAST human-labeled dataset adapter."""
import json
from pathlib import Path

import pytest

from mastlint.adapters import mast
from mastlint.schema import Trace
from mastlint.taxonomy import failure_modes

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mad_human_sample.json"


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return mast.load_human_dataset(FIXTURE)


# --------------------------------------------------------------------------- #
# Label normalization
# --------------------------------------------------------------------------- #
def test_mapping_targets_are_all_real_fm_ids():
    """Every FM id the mapping points at must exist in the canonical taxonomy —
    guards against the mapping drifting away from taxonomy.yaml."""
    real_ids = {m.id for m in failure_modes()}
    assert real_ids == {f"FM-{c}.{i}" for c, n in ((1, 5), (2, 6), (3, 3)) for i in range(1, n + 1)}
    for target in mast.MAST_LABEL_TO_FM.values():
        assert target in real_ids, f"{target} is not one of the 14 canonical modes"


def test_mapping_covers_all_14_final_modes():
    """The final-round label names must reach every one of the 14 modes."""
    reached = set(mast.MAST_LABEL_TO_FM.values())
    assert reached == {m.id for m in failure_modes()}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.1 Poor task constraint compliance", "FM-1.1"),   # v1 name
        ("1.1 Disobey Task Specification", "FM-1.1"),         # final name
        ("2.2 Step repetition", "FM-1.3"),                    # v1 numbering
        ("1.5 Step repetition", "FM-1.3"),                    # v2 numbering
        ("1.3 Step Repetition", "FM-1.3"),                    # final numbering
        ("1.2 Inconsistency between reasoning and action", "FM-2.6"),
        ("2.6 Reasoning-Action Mismatch", "FM-2.6"),
        ("2.4 Information Witholding", "FM-2.4"),             # dataset misspelling
        ("3.2 Withholding relevant information", "FM-2.4"),
        ("4.2 Lack of result verification", "FM-3.2"),
        ("4.3 Lack of critical verification", "FM-3.3"),
        ("1.4 Loss of Conversation History", "FM-1.4"),
    ],
)
def test_label_to_fm_across_taxonomy_versions(raw, expected):
    assert mast.label_to_fm(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "2.1 Unbatched repetitive execution",
        "2.3 Backtracking interruption",
        "3.1 Disagreement induced inaction",
        "3.4 Waiting for known information",
    ],
)
def test_consolidated_early_modes_map_to_none(raw):
    assert mast.label_to_fm(raw) is None


def test_unknown_label_raises_loudly():
    with pytest.raises(KeyError):
        mast.label_to_fm("9.9 Some mode that does not exist")


def test_multiline_label_uses_first_line_only():
    raw = "1.1 Poor task constraint compliance\n\nFailure to adhere to constraints..."
    assert mast.label_to_fm(raw) == "FM-1.1"


# --------------------------------------------------------------------------- #
# Gold labels
# --------------------------------------------------------------------------- #
def test_gold_labels_ag2_round1(records):
    ag2 = records[0]  # AG2, Round 1, trace_id 2
    gold = mast.gold_labels(ag2)
    assert gold.trace_id == "mad-2"
    assert gold.mas_name == "AG2"
    assert gold.taxonomy_version == "v1"
    assert gold.n_annotators == 3
    # Known ground truth: all three annotators flagged these two modes.
    assert "FM-1.5" in gold.fired  # 1.5 Unaware of stopping conditions
    assert "FM-2.5" in gold.fired  # 3.3 Ignoring suggestions from agents
    # A mode nobody flagged should be absent, not fired.
    assert gold.present.get("FM-1.1") is False


def test_gold_majority_vote_semantics(records):
    gold = mast.gold_labels(records[0])
    for fm, ballots in gold.votes.items():
        expected = any(ballots) and sum(ballots) * 2 >= len(ballots)
        assert gold.present[fm] is expected


def test_unmapped_modes_are_recorded_not_dropped(records):
    """Round-1 records include consolidated modes; they belong in `unmapped`,
    never silently discarded and never in `present`."""
    gold = mast.gold_labels(records[0])  # Round 1 has the extra draft modes
    assert gold.unmapped, "round-1 record should surface consolidated draft modes"
    fm_ids = set(gold.present)
    assert fm_ids <= {m.id for m in failure_modes()}


def test_taxonomy_version_detection(records):
    versions = {r["round"]: mast.gold_labels(r).taxonomy_version for r in records}
    assert versions["Round 1"] == "v1"
    assert versions["Round 2"] == "v2"


@pytest.mark.parametrize(
    "round_name,expected",
    [
        ("Round 1", "v1"),
        ("Round 2", "v2"),
        ("Round 3", "v2"),
        ("Generlazability", "final"),  # dataset's actual (misspelled) label for the final round
        ("Generalizability", "final"),
    ],
)
def test_final_round_detected_despite_misspelling(round_name, expected):
    rec = {
        "round": round_name,
        "mas_name": "AG2",
        "benchmark_name": "X",
        "trace_id": 99,
        "trace": "{}",
        "annotations": [],
    }
    assert mast.gold_labels(rec).taxonomy_version == expected


# --------------------------------------------------------------------------- #
# Trace parsing
# --------------------------------------------------------------------------- #
def test_ag2_parses_into_per_turn_spans(records):
    ag2 = records[0]
    trace = mast.to_trace(ag2)
    assert isinstance(trace, Trace)
    assert trace.framework == "AG2"
    assert trace.task, "AG2 task should come from problem_statement"
    assert len(trace.spans) >= 2, "AG2 run should segment into multiple turns"
    # Agent identity comes from `name`, not the chat role.
    assert "mathproxyagent" in trace.agents
    # Spans form a linear parent chain.
    assert trace.spans[0].parent_id is None
    assert trace.spans[1].parent_id == trace.spans[0].span_id
    # Raw chat role preserved for later use.
    assert "ag2_role" in trace.spans[0].meta


def test_ag2_span_content_is_non_empty(records):
    trace = mast.to_trace(records[0])
    assert any(s.content.strip() for s in trace.spans)


def test_metagpt_json_format_parses_into_per_turn_spans(records):
    """Format A: a JSON envelope whose `content` log carries `Name(Role): to do ...`
    dispatch lines. Turns segment; the ROLE (not the persona) is the agent identity."""
    trace = mast.to_trace(records[2])  # MetaGPT trace_id 4, Round 1 (Format A)
    assert trace.framework == "MetaGPT"
    assert trace.task, "task should come from the JSON `prompt`"
    assert len(trace.spans) >= 2, "MetaGPT run should segment into multiple turns"
    assert {"SimpleCoder", "SimpleTester", "SimpleReviewer"} <= set(trace.agents)
    assert all(s.meta.get("parsing") == "metagpt" for s in trace.spans)
    # Linear parent chain, same invariant as AG2.
    assert trace.spans[0].parent_id is None
    assert trace.spans[1].parent_id == trace.spans[0].span_id
    # Persona (Alice/Bob/Charlie) is preserved in meta but is not the agent id.
    coder = next(s for s in trace.spans if s.agent == "SimpleCoder")
    assert coder.meta.get("persona") and coder.meta["persona"] not in trace.agents
    assert "metagpt_action" in coder.meta


def test_metagpt_json_body_excludes_dispatch_log_prefix(records):
    """A turn's body must not swallow the next turn's `<ts> | INFO | ...:_act:NN - `
    log prefix — the regression that made reviewer turns capture a stray log line."""
    trace = mast.to_trace(records[2])
    for s in trace.spans:
        assert "_act:" not in s.content, f"{s.span_id} leaked a dispatch log prefix"


def test_metagpt_log_format_parses_into_per_turn_spans(records):
    """Format B: a plaintext communication log (`FROM: Human` / `NEW MESSAGES:`).
    The human requirement becomes the task and its own user-role span."""
    trace = mast.to_trace(records[3])  # MetaGPT trace_id 16, final round (Format B)
    assert trace.framework == "MetaGPT"
    assert len(trace.spans) >= 3
    assert trace.task, "task should come from the Human requirement block"
    first = trace.spans[0]
    assert first.agent == "Human"
    assert first.role.value == "user"
    # Agent turns come through as distinct assistant spans.
    assert {"SimpleCoder", "SimpleTester", "SimpleReviewer"} <= set(trace.agents)
    assert all(s.meta.get("parsing") == "metagpt" for s in trace.spans)


def test_unknown_framework_falls_back_to_single_marked_span():
    """A framework with no dedicated parser is passed through as one honest,
    explicitly-marked raw span — never silently invented structure."""
    rec = {
        "round": "Round 1", "mas_name": "CrewAI", "benchmark_name": "X",
        "trace_id": 123, "trace": '{"prompt": "p", "content": "unsegmented blob"}',
        "annotations": [],
    }
    trace = mast.to_trace(rec)
    assert trace.framework == "CrewAI"
    assert len(trace.spans) == 1
    assert trace.spans[0].meta.get("parsing") == "raw_unsegmented"
    assert trace.spans[0].content.strip()


# A compact but format-faithful ChatDev log: the real traces are ~305 KB, so we
# exercise every parser branch (task_prompt, role dialogue + phase, System seminar,
# a **[event]** artifact, and all three noise kinds) on a small crafted input.
CHATDEV_LOG = """[2025-17-01 11:36:43 INFO] **[Preprocessing]**

**task_prompt**: Build a Sudoku solver.

**project_name**: Sudoku
[2025-17-01 11:36:43 INFO] flask app.py did not start for online log
[2025-17-01 11:36:43 INFO] System: **[chatting]**

CEO and CPO discuss the requirements in a seminar.
[2025-17-01 11:36:45 INFO] HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
[2025-17-01 11:36:45 INFO] **[OpenAI_Usage_Info Receive]**
prompt_tokens: 42
[2025-17-01 11:36:46 INFO] Chief Product Officer: **Chief Product Officer<->Chief Executive Officer on : DemandAnalysis, turn 0**

We should support a 9x9 grid with mistake checking.
[2025-17-01 11:36:47 INFO] flask app.py did not start for online log
[2025-17-01 11:36:48 INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**

```python
def solve(board): ...
```
[2025-17-01 11:36:49 INFO] **[Seminar Conclusion]**:

The team agreed on the grid design.
"""


def _chatdev_record() -> dict:
    return {
        "round": "Round 1", "mas_name": "ChatDev", "benchmark_name": "X",
        "trace_id": 200, "trace": CHATDEV_LOG, "annotations": [],
    }


def test_chatdev_parses_into_per_turn_spans():
    """ChatDev's Markdown log segments into role/phase-attributed spans, with the
    customer task lifted from the Preprocessing `task_prompt`."""
    trace = mast.to_trace(_chatdev_record())
    assert trace.framework == "ChatDev"
    assert trace.task == "Build a Sudoku solver."
    assert {"System", "Chief Product Officer", "Programmer"} <= set(trace.agents)
    assert all(s.meta.get("parsing") == "chatdev" for s in trace.spans)
    # Linear parent chain, same invariant as the other adapters.
    assert trace.spans[0].parent_id is None
    assert trace.spans[1].parent_id == trace.spans[0].span_id


def test_chatdev_drops_noise_blocks():
    """flask / HTTP / OpenAI-usage lines are logged on every step and must never
    become spans — they would drown the real turns."""
    trace = mast.to_trace(_chatdev_record())
    for s in trace.spans:
        assert "flask app.py" not in s.content
        assert not s.content.startswith("HTTP Request:")
        assert "OpenAI_Usage_Info" not in s.content


def test_chatdev_lifts_phase_and_event_metadata():
    """Role turns carry their phase/turn; system-event blocks carry the `[event]` tag."""
    trace = mast.to_trace(_chatdev_record())
    cpo = next(s for s in trace.spans if s.agent == "Chief Product Officer")
    assert cpo.meta.get("phase") == "DemandAnalysis"
    assert cpo.meta.get("turn") == "0"
    assert not cpo.content.startswith("Chief Product Officer:")  # speaker prefix stripped
    conclusion = next(
        s for s in trace.spans if s.meta.get("chatdev_event") == "Seminar Conclusion"
    )
    assert conclusion.agent == "ChatDev"


def test_chatdev_without_headers_falls_back():
    """A ChatDev blob with no INFO headers yields no spans → honest raw fallback."""
    rec = {
        "round": "Round 1", "mas_name": "ChatDev", "benchmark_name": "X",
        "trace_id": 201, "trace": "just an opaque blob with no headers", "annotations": [],
    }
    trace = mast.to_trace(rec)
    assert len(trace.spans) == 1
    assert trace.spans[0].meta.get("parsing") == "raw_unsegmented"


def test_metagpt_without_turn_markers_falls_back(records):
    """If a MetaGPT trace has no recognizable turn markers, the parser returns no
    spans and to_trace falls back to the raw span rather than emitting nothing."""
    rec = {
        "round": "Round 1", "mas_name": "MetaGPT", "benchmark_name": "X",
        "trace_id": 124, "trace": '{"prompt": "p", "content": "no dispatch lines here"}',
        "annotations": [],
    }
    trace = mast.to_trace(rec)
    assert len(trace.spans) == 1
    assert trace.spans[0].meta.get("parsing") == "raw_unsegmented"


# A format-faithful mini HyperAgent record: real trajectories are 578–10 535 flat log
# lines (46–644 KB). This exercises header reconstruction, the Response/handoff/Inner
# speaker forms, the role normalization, and the "Initialized" boot filter.
def _hyperagent_record() -> dict:
    inst = "scikit-learn__scikit-learn-25570"

    def hdr(msg: str) -> str:
        return f"HyperAgent_{inst} - INFO - {msg}"

    trajectory = [
        hdr("Initialized HyperAgent instance " + inst),
        hdr("Initialized tools"),
        hdr("Planner's Response: Thought: I need to locate the ColumnTransformer."),
        "  (continued planner reasoning across a second line)",
        hdr("Inner-Navigator-Assistant's Response: Thought: Searching the codebase."),
        hdr("Navigator->Planner: The class lives in compose/_column_transformer.py."),
        hdr("Inner-Editor-Assistant's Response: Thought: Applying the fix."),
        hdr("Editor->Planner: Thought: The changes have been applied successfully."),
        hdr("Executor->Planner: The reproduction script now runs without error."),
    ]
    return {
        "round": "Round 2", "mas_name": "HyperAgent", "benchmark_name": "SWE",
        "trace_id": 300, "annotations": [],
        "trace": json.dumps(
            {"instance_id": inst,
             "problem_statement": ["ColumnTransformer bug", "cannot handle 0 features"],
             "trajectory": trajectory}
        ),
    }


def test_hyperagent_parses_trajectory_into_per_turn_spans():
    """HyperAgent's flat log-line trajectory reassembles into per-turn spans; the task
    comes from problem_statement and the Planner/Navigator/Editor/Executor roles appear."""
    trace = mast.to_trace(_hyperagent_record())
    assert trace.framework == "HyperAgent"
    assert "ColumnTransformer bug" in trace.task
    assert {"Planner", "Navigator", "Editor", "Executor"} <= set(trace.agents)
    assert all(s.meta.get("parsing") == "hyperagent" for s in trace.spans)
    assert trace.spans[0].parent_id is None
    assert trace.spans[1].parent_id == trace.spans[0].span_id


def test_hyperagent_normalizes_inner_assistant_and_records_handoffs():
    """`Inner-Navigator-Assistant` and `Navigator->Planner` are the same actor → both
    map to `Navigator`; a handoff records its recipient and kind in meta."""
    trace = mast.to_trace(_hyperagent_record())
    nav_spans = [s for s in trace.spans if s.agent == "Navigator"]
    assert len(nav_spans) == 2  # one Inner-Assistant reasoning + one ->Planner handoff
    kinds = {s.meta.get("hyperagent_kind") for s in nav_spans}
    assert kinds == {"response", "handoff"}
    handoff = next(s for s in nav_spans if s.meta.get("hyperagent_kind") == "handoff")
    assert handoff.meta.get("to") == "Planner"
    assert not handoff.content.startswith("Navigator->")  # prefix stripped


def test_hyperagent_drops_initialization_boilerplate():
    """The repeated `Initialized ...` boot lines carry no turn signal and must not
    become spans."""
    trace = mast.to_trace(_hyperagent_record())
    assert all(not s.content.startswith("Initialized ") for s in trace.spans)
    assert "System" not in trace.agents  # the only System lines here were boot lines


def test_hyperagent_without_trajectory_falls_back():
    """A HyperAgent record whose trajectory yields no entries falls back to a raw span."""
    rec = {
        "round": "Round 2", "mas_name": "HyperAgent", "benchmark_name": "SWE",
        "trace_id": 301, "annotations": [],
        "trace": json.dumps({"problem_statement": ["p"], "trajectory": []}),
    }
    trace = mast.to_trace(rec)
    assert len(trace.spans) == 1
    assert trace.spans[0].meta.get("parsing") == "raw_unsegmented"


def test_to_trace_roundtrips_through_schema(records):
    """Every produced Trace must survive schema (re)validation — proves the adapter
    never leaks a shape the contract rejects."""
    for r in records:
        trace = mast.to_trace(r)
        Trace.model_validate(trace.model_dump())


def test_iter_labeled_traces_pairs_align(records):
    pairs = list(mast.iter_labeled_traces(FIXTURE))
    assert len(pairs) == len(records)
    for trace, gold in pairs:
        assert trace.trace_id == gold.trace_id


def test_is_segmented_distinguishes_parsed_from_blob():
    parsed = mast.to_trace(_chatdev_record())
    blob = mast.to_trace({
        "round": "Round 1", "mas_name": "CrewAI", "benchmark_name": "X",
        "trace_id": 400, "trace": "opaque", "annotations": [],
    })
    assert mast.is_segmented(parsed) is True
    assert mast.is_segmented(blob) is False


def test_segmented_only_filter_drops_blob_traces(tmp_path):
    """The fixture's AG2/MetaGPT records all segment, so a blob record must be the only
    one dropped by segmented_only."""
    blob = {
        "round": "Round 1", "mas_name": "AppWorld", "benchmark_name": "X",
        "trace_id": 401, "trace": "an unparsed AppWorld blob", "annotations": [],
    }
    data = mast.load_human_dataset(FIXTURE) + [blob]
    path = tmp_path / "with_blob.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    all_pairs = list(mast.iter_labeled_traces(path))
    seg_pairs = list(mast.iter_labeled_traces(path, segmented_only=True))
    assert len(all_pairs) == len(data)
    assert len(seg_pairs) == len(data) - 1
    assert all(mast.is_segmented(t) for t, _ in seg_pairs)
    assert "mad-401" not in {g.trace_id for _, g in seg_pairs}
