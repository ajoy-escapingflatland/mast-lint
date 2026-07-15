from pathlib import Path
from mastlint.schema import Trace
from mastlint.taxonomy import failure_modes

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "trace.example.json"


def test_example_trace_parses():
    trace = Trace.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    assert trace.spans, "example trace should have spans"
    assert len(trace.agents) >= 2, "multi-agent trace should have >= 2 agents"


def test_taxonomy_has_14_modes():
    modes = failure_modes()
    assert len(modes) == 14, f"MAST has 14 modes, taxonomy.yaml has {len(modes)}"
    assert {m.category for m in modes} == {"FC1", "FC2", "FC3"}
