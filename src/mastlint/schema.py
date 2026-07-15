"""Canonical trace schema — THE CONTRACT everything else depends on.

Design decision (see docs/design.md, Fork 1): the internal representation is
OTel-GenAI-shaped and framework-agnostic. Adapters in adapters/ translate
LangGraph / CrewAI / AutoGen exports INTO this schema. Never let a framework's
native shape leak past the adapter boundary.
"""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Span(BaseModel):
    """One atomic step in the trace (a model call, a tool call, a handoff)."""
    span_id: str
    parent_id: str | None = None
    agent: str = Field(description="Logical agent/role that produced this span")
    role: Role = Role.assistant
    kind: str = Field("message", description="message | tool_call | tool_result | handoff")
    content: str = ""
    tool_name: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    meta: dict = Field(default_factory=dict)


class Trace(BaseModel):
    """A full multi-agent run, normalized."""
    trace_id: str
    framework: str = Field("unknown", description="Source framework, informational only")
    task: str = Field("", description="The task/goal given to the system, if known")
    spans: list[Span]

    @property
    def agents(self) -> list[str]:
        return sorted({s.agent for s in self.spans})


class Finding(BaseModel):
    """One detected failure — the unit of mast-lint's output."""
    failure_mode_id: str          # e.g. "FM-3.1"
    failure_mode_name: str        # e.g. "Premature Termination"
    category: str                 # e.g. "FC3"
    span_ids: list[str]           # where in the trace it occurred
    rationale: str                # judge's justification, quoting the spans
    confidence: float = Field(ge=0.0, le=1.0)


class Report(BaseModel):
    trace_id: str
    findings: list[Finding]
    modes_fired: list[str] = Field(default_factory=list)
