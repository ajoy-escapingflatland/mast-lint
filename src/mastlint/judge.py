"""LLM-as-judge: classify a trace/window against the 14 MAST modes.

Fork 2 (docs/design.md): the classifier is an LLM-as-judge. The prompt is RENDERED
from taxonomy.yaml (never hard-coded) so sharpening a definition updates the judge.

The judge is deliberately **provider-agnostic** (Step-3 decision): everything here
depends only on the ``JudgeClient`` protocol — one text-in/text-out method. The
concrete Anthropic backend lives in ``AnthropicJudge`` at the bottom; a second
provider (or a fake, for tests) is a drop-in. This keeps mast-lint a neutral
measurement tool and lets us later report agreement under *different* judge models.

Contract enforced here, not trusted from the model:
  * Every ``Finding`` MUST cite span_ids that actually exist in the window. Findings
    citing no real span are dropped — "evidence or it didn't happen" (schema.py).
  * ``failure_mode_id`` must be one of the 14 canonical ids; name/category are filled
    from the taxonomy, never from the model's text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .schema import Finding, Report, Span, Trace
from .taxonomy import failure_modes

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "judge_system.md"

# Provider pinned at Step 3 (see docs/design.md, Fork 2 discussion): Anthropic Claude,
# behind a protocol so it isn't load-bearing. Skill default model unless overridden.
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 16000
# Cap per-span text fed to the judge. The MAST fallback adapter can emit a single
# 600KB+ span (unsegmented framework logs); without a cap one span would dominate
# the prompt. Generous enough that structured traces pass through whole.
MAX_CHARS_PER_SPAN = 20000


class JudgeError(RuntimeError):
    """An LLM judge call failed. Carries actionable context (likely cause + fix) so the
    CLI can show a clean message instead of a raw provider traceback."""


class JudgeClient(Protocol):
    """Minimal seam between judge logic and any LLM provider.

    ``json_schema``, when given, is a JSON-Schema the implementation MAY use to
    constrain output (Anthropic structured outputs, etc.). Implementations that
    can't enforce it should ignore it and lean on the prompt — the returned string
    is parsed defensively either way.
    """

    def complete(self, system: str, user: str, *, json_schema: dict | None = None) -> str: ...


# --------------------------------------------------------------------------- #
# Prompt rendering
# --------------------------------------------------------------------------- #
def _catalog() -> str:
    """Render the 14 modes with the fields that lift agreement: definition, signals,
    and the near-miss boundary (the IP in taxonomy.yaml)."""
    blocks: list[str] = []
    for fm in failure_modes():
        lines = [f"### {fm.id} — {fm.name}  [{fm.category}]", fm.operational_definition]
        if fm.signals:
            lines.append("Signals: " + "; ".join(fm.signals))
        if fm.near_miss:
            lines.append(f"NOT {fm.id} when: {fm.near_miss}")
        if fm.confused_with:
            lines.append("Often confused with: " + ", ".join(fm.confused_with))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_system_prompt() -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{{TAXONOMY}}", _catalog())


def serialize_spans(spans: list[Span], task: str = "") -> str:
    """Render spans as the judge's user message. Each span keeps its id so the judge
    can cite it as evidence."""
    parts: list[str] = []
    if task:
        parts.append(f"TASK GIVEN TO THE SYSTEM:\n{task}\n")
    parts.append("TRACE SPANS (in order). Cite these span ids as evidence:")
    for s in spans:
        header = f"[{s.span_id}] agent={s.agent} role={s.role.value} kind={s.kind}"
        if s.tool_name:
            header += f" tool={s.tool_name}"
        content = s.content.strip()
        if len(content) > MAX_CHARS_PER_SPAN:
            content = content[:MAX_CHARS_PER_SPAN] + "\n…[truncated]"
        parts.append(f"{header}\n{content or '(empty)'}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Output schema + parsing
# --------------------------------------------------------------------------- #
def findings_schema() -> dict:
    """JSON schema for the judge's structured output, built from the taxonomy so the
    enum of valid ids can never drift from taxonomy.yaml."""
    ids = [m.id for m in failure_modes()]
    cats = sorted({m.category for m in failure_modes()})
    finding = {
        "type": "object",
        "properties": {
            "failure_mode_id": {"type": "string", "enum": ids},
            "failure_mode_name": {"type": "string"},
            "category": {"type": "string", "enum": cats},
            "span_ids": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["failure_mode_id", "failure_mode_name", "category",
                     "span_ids", "rationale", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"findings": {"type": "array", "items": finding}},
        "required": ["findings"],
        "additionalProperties": False,
    }


def _extract_json(raw: str) -> str:
    """Strip a ```json fence if a provider wrapped the output in one."""
    t = raw.strip()
    if t.startswith("```"):
        t = t[3:]
        if t[:4].lower() == "json":
            t = t[4:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def parse_findings(raw: str, allowed_span_ids: set[str]) -> list[Finding]:
    """Turn the judge's raw text into validated ``Finding`` objects.

    Defensive on purpose: unknown ids, hallucinated span ids, and out-of-range
    confidences are corrected or dropped rather than trusted.
    """
    by_id = {m.id: m for m in failure_modes()}
    try:
        data = json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError):
        return []

    items = data.get("findings", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        fm = by_id.get(item.get("failure_mode_id"))
        if fm is None:
            continue  # not one of the 14 canonical modes
        spans = [s for s in item.get("span_ids", []) if s in allowed_span_ids]
        if not spans:
            continue  # evidence or it didn't happen
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        findings.append(
            Finding(
                failure_mode_id=fm.id,
                failure_mode_name=fm.name,   # authoritative from taxonomy, not the model
                category=fm.category,
                span_ids=spans,
                rationale=str(item.get("rationale", "")).strip(),
                confidence=min(1.0, max(0.0, confidence)),
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# Judging
# --------------------------------------------------------------------------- #
def judge_window(spans: list[Span], client: JudgeClient, *, task: str = "") -> list[Finding]:
    """Classify one window of spans. Returns evidence-backed Findings (possibly none)."""
    if not spans:
        return []
    raw = client.complete(render_system_prompt(), serialize_spans(spans, task),
                          json_schema=findings_schema())
    return parse_findings(raw, {s.span_id for s in spans})


def judge_trace(trace: Trace, client: JudgeClient) -> Report:
    """Run the judge over a whole trace (via segment.windows) and assemble a Report."""
    from .segment import windows

    findings: list[Finding] = []
    for window in windows(trace):
        findings.extend(judge_window(window, client, task=trace.task))
    return Report(
        trace_id=trace.trace_id,
        findings=findings,
        modes_fired=sorted({f.failure_mode_id for f in findings}),
    )


# --------------------------------------------------------------------------- #
# Anthropic backend (the one concrete provider, behind JudgeClient)
# --------------------------------------------------------------------------- #
class AnthropicJudge:
    """``JudgeClient`` backed by Anthropic Claude.

    Requires the optional ``anthropic`` dependency (``pip install mastlint[llm]``) and
    credentials in the environment (``ANTHROPIC_API_KEY`` or an ``ant auth login``
    profile). Uses adaptive thinking + structured outputs for reliable, well-reasoned
    classifications.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        thinking: bool = True,
        client: object | None = None,
    ) -> None:
        if client is None:
            import anthropic  # lazy: keep core import-light and dependency optional

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.thinking = thinking

    def complete(self, system: str, user: str, *, json_schema: dict | None = None) -> str:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        if json_schema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}

        try:
            resp = self.client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 — re-raised with context, never swallowed
            raise JudgeError(
                f"Judge call to model {self.model!r} failed — {type(exc).__name__}: {exc}. "
                "Likely causes: an outdated 'anthropic' SDK missing output_config/adaptive "
                "thinking (pip install -U 'mastlint[llm]'), an unknown model id, an "
                "unsupported request-parameter combination, or missing/invalid credentials."
            ) from exc

        if getattr(resp, "stop_reason", None) == "refusal":
            return '{"findings": []}'
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return '{"findings": []}'
