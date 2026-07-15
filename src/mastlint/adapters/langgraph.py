"""LangGraph adapter — STUB (Step 2/3).

Translate a LangGraph run export into schema.Trace. Keep ALL framework-specific
knowledge inside this file; the rest of mast-lint only sees canonical Traces.
"""
from __future__ import annotations
from ..schema import Trace


def from_langgraph(raw: dict) -> Trace:
    raise NotImplementedError("Step 2: map LangGraph state/messages -> Trace")
