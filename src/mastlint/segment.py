"""Segment a Trace into judge-sized windows (turns / handoffs).

STUB — Step 3. Some failure modes are local to one span (FM-2.6 reasoning-action
mismatch); others need the whole trace (FM-3.1 premature termination). Start by
passing the whole trace to each judge; add smarter windowing only if context
limits or cost force it.
"""
from __future__ import annotations
from .schema import Trace, Span


def windows(trace: Trace) -> list[list[Span]]:
    # TODO(step3): real segmentation. For v0, one window = the whole trace.
    return [trace.spans]
