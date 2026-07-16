"""Adapter for the MAST human-labeled dataset (`MAD_human_labelled_dataset.json`).

Source: Cemri et al., "Why Do Multi-Agent LLM Systems Fail?" (arXiv:2503.13657),
released at https://github.com/multi-agent-systems-failure-taxonomy/MAST and on the
HuggingFace hub as `mcemri/MAD` / `mcemri/MAST-Data`.

This adapter does TWO distinct jobs, deliberately kept separate:

1. ``to_trace(record)`` — parse a run into a canonical ``schema.Trace``. AG2, MetaGPT,
   ChatDev, HyperAgent, AppWorld, and (one of two log shapes of) GAIA are parsed into
   real per-turn spans (see ``STRUCTURED_FRAMEWORKS`` / ``_PARSERS``); MetaGPT ships in
   two on-disk formats and both are handled (see ``_metagpt_spans``); GAIA is a
   benchmark, not one framework, and only its Magentic-One-shaped traces parse (see
   ``_gaia_spans``) — the other GAIA log shape stays raw_unsegmented on purpose.
   Every other framework's ``trace`` is a
   semi-structured log blob and is passed through as a single, explicitly-marked
   ``raw_unsegmented`` span until its own parser is written. Downstream code stays honest
   because the marker is in ``span.meta``.

2. ``gold_labels(record)`` — extract the HUMAN ground-truth labels. These are the
   yardstick for the credibility moat (Step 4): mast-lint's judge is measured against
   them. Two wrinkles the raw file forces us to handle honestly:

   * **Three taxonomy versions.** The dataset was annotated over several rounds while the
     taxonomy itself was still evolving. Round 1 used an 18-mode / 4-category draft,
     Rounds 2-3 a 17-mode revision, and the "Generalizability" round the final published
     14 modes (the ones in ``taxonomy/taxonomy.yaml``). ``MAST_LABEL_TO_FM`` normalizes
     all three onto the canonical FM ids.
   * **Four early modes have no canonical home.** ``unbatched repetitive execution``,
     ``backtracking interruption``, ``disagreement induced inaction``, and
     ``waiting for known information`` were consolidated away and map to nothing. We
     record them in ``MASTGold.unmapped`` rather than forcing them into a final mode —
     inventing a mapping would silently corrupt any agreement number computed later.

   Labels are TRACE-LEVEL (each of 3 annotators ticks a box per mode for the whole run),
   so gold labels are a set of present/absent-per-mode booleans, not span pointers. We
   aggregate to a per-mode boolean by majority vote across annotators.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, Field

from ..schema import Role, Span, Trace

# ---------------------------------------------------------------------------
# Label normalization: raw MAST labels (across 3 taxonomy versions) -> FM ids
# ---------------------------------------------------------------------------
# Keys are the mode's DESCRIPTIVE phrase, canonicalized by ``_canon`` (leading
# "N.N" number stripped, lowercased, punctuation dropped). The leading number is
# NOT part of the key because the same mode carries different numbers in different
# rounds — e.g. "Step Repetition" is 2.2 in Round 1, 1.5 in Rounds 2-3, 1.3 final.

MAST_LABEL_TO_FM: dict[str, str] = {
    # --- FC1 / final 1.x ---
    "poor task constraint compliance": "FM-1.1",          # v1/v2 name
    "disobey task specification": "FM-1.1",               # final name
    "disobey role specification": "FM-1.2",
    "step repetition": "FM-1.3",
    "loss of conversation history": "FM-1.4",             # only exists in the final round
    "unaware of stopping conditions": "FM-1.5",           # v1/v2 name
    "unaware of termination conditions": "FM-1.5",        # final name
    # --- FC2 / final 2.x ---
    "conversation reset": "FM-2.1",
    "fail to elicit clarification": "FM-2.2",             # v1/v2 name
    "fail to ask for clarification": "FM-2.2",            # final name
    "task derailment": "FM-2.3",                          # final name
    "derailment from task": "FM-2.3",                     # v1/v2 name
    "information withholding": "FM-2.4",                  # final name
    "information witholding": "FM-2.4",                   # dataset misspelling (final round)
    "withholding relevant information": "FM-2.4",         # v1/v2 name
    "ignored other agents input": "FM-2.5",               # final name
    "ignoring suggestions from agents": "FM-2.5",         # v1/v2 name
    "reasoning action mismatch": "FM-2.6",                # final name
    "action reasoning mismatch": "FM-2.6",                # definitions.txt variant
    "inconsistency between reasoning and action": "FM-2.6",  # v1/v2 name
    # --- FC3 / final 3.x ---
    "premature termination": "FM-3.1",                    # final name
    "ill specified termination condition leading to premature termination": "FM-3.1",  # v1/v2
    "no or incomplete verification": "FM-3.2",            # final name
    "lack of result verification": "FM-3.2",              # v1/v2 name
    "incorrect verification": "FM-3.3",                   # final name
    "lack of critical verification": "FM-3.3",            # v1/v2 name
    # --- MERGED / lower-confidence mappings (see MERGED_LABELS) ---
    "undetected conversation ambiguities and contradictions": "FM-2.2",
}

# Early-round modes the final 14-mode taxonomy consolidated away. They map to no
# canonical FM id; surfaced via ``MASTGold.unmapped`` for transparency, never forced.
UNMAPPED_LABELS: frozenset[str] = frozenset({
    "unbatched repetitive execution",
    "backtracking interruption",
    "disagreement induced inaction",
    "waiting for known information",
})

# Mappings where an early mode was folded into a final one that is not a verbatim
# rename — recorded so the judgement is auditable, not hidden inside the dict above.
MERGED_LABELS: frozenset[str] = frozenset({
    "undetected conversation ambiguities and contradictions",  # -> FM-2.2 (clarification family)
    "lack of critical verification",                           # -> FM-3.3 (weak == incorrect verification)
})

# Frameworks whose ``trace`` we parse into real per-turn spans. Everything else is
# passed through as one raw_unsegmented span (see module docstring, job #1).
STRUCTURED_FRAMEWORKS: frozenset[str] = frozenset(
    {"AG2", "MetaGPT", "ChatDev", "HyperAgent", "AppWorld", "GAIA"}
)

# ``span.meta["parsing"]`` value stamped by the single-span fallback. ``is_segmented``
# keys off it to tell a real per-turn trace from an un-parsed blob (see Step 4 evals).
RAW_PARSING_MARKER = "raw_unsegmented"

_NUM_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\s*")
_PUNCT = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")


def _canon(label: str) -> str:
    """Canonicalize a raw MAST label to its number-stripped descriptive key."""
    first_line = label.strip().splitlines()[0] if label.strip() else ""
    without_num = _NUM_PREFIX.sub("", first_line).lower()
    return _WS.sub(" ", _PUNCT.sub(" ", without_num)).strip()


def label_to_fm(label: str) -> str | None:
    """Map one raw MAST label string to a canonical FM id, or ``None`` if the mode
    was consolidated away in the final taxonomy.

    Raises ``KeyError`` on a label we have never seen — silently dropping an
    unrecognized mode would understate failures, so unknowns must fail loudly.
    """
    key = _canon(label)
    if key in MAST_LABEL_TO_FM:
        return MAST_LABEL_TO_FM[key]
    if key in UNMAPPED_LABELS:
        return None
    raise KeyError(f"Unrecognized MAST label {label.splitlines()[0]!r} (canonical: {key!r})")


# ---------------------------------------------------------------------------
# Ground-truth (gold) labels
# ---------------------------------------------------------------------------
_ANNOTATOR_KEYS = ("annotator_1", "annotator_2", "annotator_3")


def _taxonomy_version(round_name: str) -> str:
    r = round_name.lower()
    if "gener" in r:             # "Generlazability" (sic in dataset) — final 14-mode round
        return "final"
    if "1" in r:
        return "v1"               # Round 1: 18-mode / 4-category draft
    return "v2"                   # Rounds 2-3: 17-mode revision


class MASTGold(BaseModel):
    """Human ground-truth labels for one MAST trace — the eval yardstick.

    Kept out of ``schema.py`` on purpose: a ``Finding`` is what mast-lint's judge
    *emits*; ``MASTGold`` is what it is *scored against*. They must not be confused.
    """

    trace_id: str = Field(description="Matches the Trace.trace_id this labels")
    mas_name: str
    benchmark: str
    round: str
    taxonomy_version: str = Field(description="v1 | v2 | final — which label set was used")
    n_annotators: int
    present: dict[str, bool] = Field(
        default_factory=dict,
        description="Canonical FM id -> present, by majority vote across annotators. "
        "Only covers modes reachable from this round's taxonomy version.",
    )
    votes: dict[str, list[bool]] = Field(
        default_factory=dict,
        description="FM id -> per-annotator booleans (OR-folded when several raw modes "
        "map to the same FM id). Preserved for inter-annotator agreement work.",
    )
    unmapped: dict[str, list[bool]] = Field(
        default_factory=dict,
        description="Raw labels with no canonical FM id -> per-annotator votes. Present "
        "for transparency; never folded into `present`.",
    )

    @property
    def fired(self) -> list[str]:
        """Canonical FM ids the humans judged present (majority vote), sorted."""
        return sorted(fm for fm, present in self.present.items() if present)


def gold_labels(record: dict) -> MASTGold:
    """Extract human ground-truth labels from one dataset record."""
    votes: dict[str, list[bool]] = {}
    unmapped: dict[str, list[bool]] = {}
    n = 0
    for ann in record.get("annotations", []):
        ballots = [bool(ann.get(k)) for k in _ANNOTATOR_KEYS if k in ann]
        n = max(n, len(ballots))
        fm = label_to_fm(ann["failure mode"])
        target = unmapped if fm is None else votes
        key = _canon(ann["failure mode"]) if fm is None else fm
        if key in target:
            # OR-fold: several raw modes can collapse onto one FM id.
            target[key] = [a or b for a, b in zip(target[key], ballots)]
        else:
            target[key] = ballots

    present = {fm: any(b) and sum(b) * 2 >= len(b) for fm, b in votes.items()}
    return MASTGold(
        trace_id=_trace_id(record),
        mas_name=record["mas_name"],
        benchmark=record["benchmark_name"],
        round=record["round"],
        taxonomy_version=_taxonomy_version(record["round"]),
        n_annotators=n,
        present=present,
        votes=votes,
        unmapped=unmapped,
    )


# ---------------------------------------------------------------------------
# Trace parsing
# ---------------------------------------------------------------------------
def _trace_id(record: dict) -> str:
    return f"mad-{record['trace_id']}"


def _ag2_spans(raw: dict) -> tuple[str, list[Span]]:
    """Parse an AG2 (AutoGen) run into (task, spans).

    AG2 stores a ``trajectory`` list of chat messages ``{content, role, name}``. The
    agent IDENTITY is ``name`` (``role`` is the OpenAI chat role from that agent's
    vantage point, so the "assistant" agent's turns confusingly carry role="user").
    We key ``span.agent`` off ``name`` and keep the raw chat role in ``meta``.
    """
    problem = raw.get("problem_statement") or []
    task = " ".join(problem) if isinstance(problem, list) else str(problem)

    spans: list[Span] = []
    prev: str | None = None
    for i, msg in enumerate(raw.get("trajectory", []), start=1):
        content = msg.get("content")
        text = "\n".join(str(c) for c in content) if isinstance(content, list) else str(content or "")
        raw_role = msg.get("role")
        span = Span(
            span_id=f"s{i}",
            parent_id=prev,
            agent=msg.get("name") or raw_role or "agent",
            role=Role(raw_role) if raw_role in Role._value2member_map_ else Role.assistant,
            kind="message",
            content=text,
            meta={"ag2_role": raw_role},
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


# MetaGPT ships its runs in TWO formats (both present in the human-labeled set):
#
#   Format A — a JSON envelope ``{"prompt", "content", ...}`` whose ``content`` is one
#   log string where each turn is announced by a role-dispatch line, e.g.
#       ...metagpt.roles.role:_act:391 - Alice(SimpleCoder): to do SimpleWriteCode(...)
#   The persona (Alice) is cosmetic; the ROLE (SimpleCoder) is the functional identity.
#
#   Format B — a plaintext "Agent Communication Log": timestamped blocks, the first a
#   ``FROM: Human TO: {...} / ACTION / CONTENT:`` requirement, the rest
#   ``[ts] NEW MESSAGES:\n\n<Role>:\n<body>``.
#
# Both formats expose the same role names (Human, SimpleCoder, SimpleTester,
# SimpleReviewer), so we key ``span.agent`` on the ROLE in both — a trace stays
# comparable regardless of which format it arrived in.

# Format A: a whole dispatch log line, e.g.
#   "2025-01-17 ... | INFO | metagpt.roles.role:_act:391 - Alice(SimpleCoder): to do SimpleWriteCode(...)"
# We anchor on the entire line (every dispatch line carries "_act:NN - ") so a turn's
# body runs from the END of its dispatch line to the START of the next — otherwise the
# following line's "<timestamp> | INFO | ...:_act:NN - " prefix leaks into this body.
_MG_ACT = re.compile(
    r"^.*?_act:\d+ - ([A-Za-z]\w*)\(([\w ]+)\): to do (\w+)(?:\([^)]*\))?.*$",
    re.MULTILINE,
)
# Format B: split on the leading "[YYYY-MM-DD HH:MM:SS]" of each block.
_MG_BLOCK = re.compile(r"(?=^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\])", re.MULTILINE)
_MG_FROM = re.compile(r"FROM:\s*(\S+)\s+TO:")
_MG_NEWMSG = re.compile(r"NEW MESSAGES:\s*\n+\s*([A-Za-z_]\w*):")


def _metagpt_json_spans(obj: dict) -> tuple[str, list[Span]]:
    """Parse a Format-A MetaGPT run. Returns ``(task, [])`` if no turn markers are
    found, so the caller can fall back to a single raw span rather than fake structure."""
    task = str(obj.get("prompt") or "")
    content = str(obj.get("content") or "")
    markers = list(_MG_ACT.finditer(content))
    if not markers:
        return task, []

    spans: list[Span] = []
    prev: str | None = None
    for i, m in enumerate(markers):
        persona, role_name, action = m.group(1), m.group(2).strip(), m.group(3)
        end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
        body = content[m.end():end].strip()
        span = Span(
            span_id=f"s{i + 1}",
            parent_id=prev,
            agent=role_name,
            role=Role.assistant,
            kind="message",
            content=body,
            meta={"parsing": "metagpt", "persona": persona, "metagpt_action": action},
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


def _metagpt_log_spans(raw: str) -> tuple[str, list[Span]]:
    """Parse a Format-B MetaGPT communication log. Returns ``(task, [])`` if no
    speaker blocks are found (caller falls back to a raw span)."""
    spans: list[Span] = []
    prev: str | None = None
    task = ""
    for block in _MG_BLOCK.split(raw):
        block = block.strip()
        if not block:
            continue
        from_m = _MG_FROM.search(block)
        new_m = _MG_NEWMSG.search(block)
        if from_m:  # requirement / hand-in block
            speaker = from_m.group(1)
            idx = block.find("CONTENT:")
            body = block[idx + len("CONTENT:"):].strip() if idx >= 0 else block
        elif new_m:  # an agent's reply
            speaker = new_m.group(1)
            body = block[new_m.end():].strip()
        else:
            continue  # log preamble ("=== ... ===") — no speaker, skip
        role = Role.user if speaker.lower() == "human" else Role.assistant
        if role is Role.user and not task:
            task = body
        span = Span(
            span_id=f"s{len(spans) + 1}",
            parent_id=prev,
            agent=speaker,
            role=role,
            kind="message",
            content=body,
            meta={"parsing": "metagpt"},
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


def _metagpt_spans(record: dict) -> tuple[str, list[Span]]:
    """Dispatch a MetaGPT run to the right format parser (JSON envelope vs. log)."""
    raw = record["trace"]
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        obj = None
    if isinstance(obj, dict) and "content" in obj:
        return _metagpt_json_spans(obj)
    return _metagpt_log_spans(str(raw))


# ChatDev emits a verbose Markdown log: timestamped ``[YYYY-DD-MM HH:MM:SS INFO]``
# lines, each opening a block whose body runs across continuation lines to the next
# header. Three kinds of block matter, and three are pure noise:
#
#   signal — "<Role>: **<A><->B on : <Phase>, turn <N>**\n<utterance>"   (role dialogue)
#          — "System: **[chatting]** / **[RolePlaying]** ..."           (seminar context)
#          — "**[Seminar Conclusion]** / **[Update Codes]** / **[Test Reports]** ..." (artifacts)
#   noise  — "flask app.py did not start for online log"  (logged on every step)
#          — "HTTP Request: POST https://api.openai.com/..."
#          — "**[OpenAI_Usage_Info Receive]**"            (token-accounting blocks)
#
# We keep every signal block as a span (agent = the role, or "ChatDev" for a
# system/environment event), drop the three noise kinds, and lift the phase/turn and
# event tag into ``span.meta``. The customer task comes from the Preprocessing header's
# ``**task_prompt**``.
_CD_HDR = re.compile(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d INFO\] ")
_CD_SPEAKER = re.compile(r"^([A-Z][A-Za-z ]+?): ")
_CD_EVENT = re.compile(r"^\*\*\[([^\]]+)\]\*\*")
_CD_PHASE = re.compile(r"on\s*:\s*([A-Za-z]+),\s*turn\s*(\d+)")
_CD_TASK = re.compile(r"\*\*task_prompt\*\*:\s*(.+)")


def _cd_is_noise(first_line: str) -> bool:
    return (
        first_line == "flask app.py did not start for online log"
        or first_line.startswith("HTTP Request:")
        or first_line.startswith("**[OpenAI_Usage_Info")
    )


def _chatdev_blocks(raw: str) -> Iterator[str]:
    """Group the log into per-header blocks (header prefix stripped, body lines kept)."""
    cur: list[str] | None = None
    for line in raw.split("\n"):
        if _CD_HDR.match(line):
            if cur is not None:
                yield "\n".join(cur)
            cur = [_CD_HDR.sub("", line, count=1)]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        yield "\n".join(cur)


def _chatdev_spans(record: dict) -> tuple[str, list[Span]]:
    """Parse a ChatDev run into per-turn/per-phase spans. Returns ``(task, [])`` when no
    signal blocks are found, so the caller falls back to a single raw span."""
    raw = str(record["trace"])
    task_m = _CD_TASK.search(raw)
    task = task_m.group(1).strip() if task_m else ""

    spans: list[Span] = []
    prev: str | None = None
    for block in _chatdev_blocks(raw):
        first = block.split("\n", 1)[0]
        if _cd_is_noise(first):
            continue
        meta: dict = {"parsing": "chatdev"}
        speaker_m = _CD_SPEAKER.match(first)
        if speaker_m:
            agent = speaker_m.group(1)
            role = Role.system if agent == "System" else Role.assistant
            body = block[speaker_m.end():]  # drop the "<Speaker>: " prefix, keep the rest
        else:
            agent, role, body = "ChatDev", Role.assistant, block
            event_m = _CD_EVENT.match(first)
            if event_m:
                meta["chatdev_event"] = event_m.group(1)
        phase_m = _CD_PHASE.search(first)
        if phase_m:
            meta["phase"], meta["turn"] = phase_m.group(1), phase_m.group(2)
        body = body.strip()
        if not body:
            continue
        span = Span(
            span_id=f"s{len(spans) + 1}",
            parent_id=prev,
            agent=agent,
            role=role,
            kind="message",
            content=body,
            meta=meta,
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


# HyperAgent ships a JSON envelope ``{problem_statement, trajectory, ...}`` whose
# ``trajectory`` is a flat list of log LINES (not turns): each logical entry opens with
# a ``HyperAgent_<instance> - INFO - `` header line and continues across the following
# non-header lines. A run is a Planner delegating to three sub-agents — Navigator,
# Editor, Executor — each of which appears twice per turn:
#   "<Role>'s Response: ..."            — the agent's own reasoning/answer
#   "Inner-<Role>-Assistant's Response" — a sub-agent's internal reasoning
#   "<Role>->Planner: ..."              — the sub-agent handing its result back
# ``Inner-<Role>-Assistant`` and ``<Role>->Planner`` are the same actor, so both
# normalize to the bare role; the reasoning-vs-handoff distinction is kept in ``meta``.
_HA_HDR = re.compile(r"^HyperAgent_\S+ - \w+ - ")
_HA_RESPONSE = re.compile(r"^(.+?)'s Response:\s*")
_HA_HANDOFF = re.compile(r"^(\w+)->(\w+):\s*")
_HA_INNER = re.compile(r"^Inner-(.+?)-Assistant$")


def _ha_role(name: str) -> str:
    """Normalize ``Inner-Navigator-Assistant`` -> ``Navigator``; pass others through."""
    m = _HA_INNER.match(name)
    return m.group(1) if m else name


def _hyperagent_spans(record: dict) -> tuple[str, list[Span]]:
    """Parse a HyperAgent run into per-turn spans. Returns ``(task, [])`` when the
    trajectory has no recognizable entries, so the caller falls back to a raw span."""
    raw = json.loads(record["trace"])  # may raise; to_trace catches and falls back
    problem = raw.get("problem_statement") or []
    task = "\n".join(str(p) for p in problem) if isinstance(problem, list) else str(problem)
    trajectory = raw.get("trajectory")
    if not isinstance(trajectory, list):
        return task, []

    # Reassemble the flat line list into logical log entries.
    entries: list[list[str]] = []
    cur: list[str] | None = None
    for line in trajectory:
        line = str(line)
        if _HA_HDR.match(line):
            if cur is not None:
                entries.append(cur)
            cur = [_HA_HDR.sub("", line, count=1)]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        entries.append(cur)

    spans: list[Span] = []
    prev: str | None = None
    for entry in entries:
        block = "\n".join(entry)
        first = entry[0]
        meta: dict = {"parsing": "hyperagent"}
        resp_m = _HA_RESPONSE.match(first)
        handoff_m = _HA_HANDOFF.match(first)
        if resp_m:
            agent, role = _ha_role(resp_m.group(1)), Role.assistant
            body = block[resp_m.end():]
            meta["hyperagent_kind"] = "response"
        elif handoff_m:
            agent, role = _ha_role(handoff_m.group(1)), Role.assistant
            body = block[handoff_m.end():]
            meta["hyperagent_kind"] = "handoff"
            meta["to"] = handoff_m.group(2)
        elif first.startswith("Initialized "):
            continue  # per-subagent boot boilerplate ("Initialized tools", ...) — no signal
        else:  # other framework/environment lines
            agent, role, body = "System", Role.system, block
        body = body.strip()
        if not body:
            continue
        span = Span(
            span_id=f"s{len(spans) + 1}",
            parent_id=prev,
            agent=agent,
            role=role,
            kind="message",
            content=body,
            meta=meta,
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


# AppWorld emits an indentation-nested plain-text log, no timestamps. A run opens
# with a banner announcing which benchmark task this is, then a Supervisor agent
# delegates to per-app sub-agents (Spotify, SimpleNote, ...) via a fixed vocabulary
# of headers, each a bare line (indentation grows with nesting depth, ignored here —
# the header text alone is the boundary signal):
#
#   ******************** Task N/M (id) ********************   — task banner, once
#   Response from Supervisor Agent / Response from <App> Agent
#   Message to Supervisor Agent / Message to <App> Agent
#   Entering <App> Agent message loop / Exiting <App> Agent message loop  — no body
#   Code Execution Output
#   Response from send_message API
#
# App names are inconsistently cased across traces (``Spotify`` vs ``spotify``) —
# normalized so the same app isn't split into two agent identities. The task
# instruction is the text between the banner and the first header, lifted the same
# way ChatDev lifts its ``task_prompt`` (never emitted as a span, only as ``task``).
_AW_TASK_BANNER = re.compile(r"^[ \t]*\*{5,}\s*Task \d+/\d+ \([^)]*\)\s*\*{5,}[ \t]*$",
                              re.MULTILINE)
_AW_HDR = re.compile(
    r"^[ \t]*(?:"
    r"Response from (?P<resp_agent>.+?) Agent"
    r"|Response from send_message API"
    r"|Message to (?P<msg_agent>.+?) Agent"
    r"|Entering (?P<enter_agent>.+?) Agent message loop"
    r"|Exiting (?P<exit_agent>.+?) Agent message loop"
    r"|Code Execution Output"
    r")[ \t]*$",
    re.MULTILINE,
)


def _aw_agent(name: str) -> str:
    """Normalize app-name casing (``spotify`` vs ``Spotify``) without mangling names
    that are already mixed-case (``SimpleNote``)."""
    name = name.strip()
    return name[:1].upper() + name[1:] if name.islower() else name


def _appworld_blocks(raw: str) -> Iterator[tuple[str, str]]:
    """Split the log into (header_line, body) blocks at each ``_AW_HDR`` match."""
    matches = list(_AW_HDR.finditer(raw))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        yield m.group(0).strip(), raw[m.end():end]


def _appworld_spans(record: dict) -> tuple[str, list[Span]]:
    """Parse an AppWorld run into per-turn spans. Returns ``(task, [])`` when no
    known headers are found, so the caller falls back to a raw span."""
    raw = str(record["trace"])

    task = ""
    banner_m = _AW_TASK_BANNER.search(raw)
    first_hdr = _AW_HDR.search(raw)
    if banner_m and first_hdr:
        task = raw[banner_m.end():first_hdr.start()].strip()

    spans: list[Span] = []
    prev: str | None = None
    for header, body in _appworld_blocks(raw):
        body = body.strip()
        if not body:
            continue  # Entering/Exiting loop markers, and any other empty block
        meta: dict = {"parsing": "appworld"}
        if header.startswith("Response from Supervisor Agent"):
            agent, role, meta["appworld_kind"] = "Supervisor", Role.assistant, "response"
        elif header.startswith("Response from send_message API"):
            agent, role, meta["appworld_kind"] = "send_message", Role.tool, "tool_response"
        elif header.startswith("Response from "):
            m = re.match(r"Response from (.+) Agent", header)
            agent = _aw_agent(m.group(1)) if m else "Agent"
            role, meta["appworld_kind"] = Role.assistant, "response"
        elif header.startswith("Message to Supervisor Agent"):
            agent, role, meta["appworld_kind"] = "Supervisor", Role.assistant, "message"
        elif header.startswith("Message to "):
            m = re.match(r"Message to (.+) Agent", header)
            agent = _aw_agent(m.group(1)) if m else "Agent"
            role, meta["appworld_kind"] = Role.assistant, "message"
        elif header.startswith("Code Execution Output"):
            agent, role, meta["appworld_kind"] = "CodeExecutor", Role.tool, "code_output"
        else:
            agent, role, meta["appworld_kind"] = "System", Role.system, "loop_boundary"
        span = Span(
            span_id=f"s{len(spans) + 1}",
            parent_id=prev,
            agent=agent,
            role=role,
            kind="message",
            content=body,
            meta=meta,
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


# GAIA is a BENCHMARK, not one agent framework — the 2 human-labeled GAIA traces
# were produced by two unrelated systems with unrelated log formats. Only the
# Magentic-One-shaped one is parsed here; the other stays raw_unsegmented (see
# module docstring) rather than writing a second parser validated against a single
# example with no way to check it generalizes.
#
# Magentic-One (AutoGen's orchestrator) traces open with docker/pip-install setup
# noise, then ``SCENARIO.PY STARTING !#!#``, then simple ``---------- Speaker
# ----------`` block headers (user / MagenticOneOrchestrator / WebSurfer / ...),
# and close with ``SCENARIO.PY COMPLETE !#!#`` / runtime / ``RUN.SH COMPLETE``
# harness footer lines that must not leak into the last turn's content.
_GAIA_SCENARIO_START = re.compile(r"SCENARIO\.PY STARTING.*$", re.MULTILINE)
_GAIA_HDR = re.compile(r"^-{4,}\s*(.+?)\s*-{4,}\s*$", re.MULTILINE)
_GAIA_FOOTER_NOISE = re.compile(
    r"^(SCENARIO\.PY (COMPLETE|RUNTIME:.*)|RUN\.SH COMPLETE).*$\n?", re.MULTILINE
)


def _gaia_spans(record: dict) -> tuple[str, list[Span]]:
    """Parse a Magentic-One-shaped GAIA run into per-turn spans. Returns ``(task, [])``
    for any other GAIA log shape (no ``SCENARIO.PY STARTING`` marker, or no speaker
    headers), so the caller falls back to a raw span rather than mis-parsing it."""
    raw = str(record["trace"])
    start_m = _GAIA_SCENARIO_START.search(raw)
    if not start_m:
        return "", []
    body_text = _GAIA_FOOTER_NOISE.sub("", raw[start_m.end():])

    matches = list(_GAIA_HDR.finditer(body_text))
    if not matches:
        return "", []

    task = ""
    spans: list[Span] = []
    prev: str | None = None
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
        speaker = m.group(1).strip()
        turn_body = body_text[m.end():end].strip()
        if not turn_body:
            continue
        role = Role.user if speaker.lower() == "user" else Role.assistant
        if role is Role.user and not task:
            task = turn_body
        span = Span(
            span_id=f"s{len(spans) + 1}",
            parent_id=prev,
            agent=speaker,
            role=role,
            kind="message",
            content=turn_body,
            meta={"parsing": "gaia_magentic_one"},
        )
        spans.append(span)
        prev = span.span_id
    return task, spans


def _raw_span(record: dict) -> tuple[str, list[Span]]:
    """Fallback for frameworks without a dedicated parser yet: emit the whole run as
    one explicitly-marked span. Honest, lossy, and clearly temporary."""
    blob = record["trace"]
    task = ""
    body = blob
    try:
        obj = json.loads(blob)
        if isinstance(obj, dict):
            task = str(obj.get("prompt") or obj.get("problem_statement") or "")
            body = obj.get("content") or blob
    except (json.JSONDecodeError, TypeError):
        pass
    span = Span(
        span_id="s1",
        agent=record["mas_name"],
        role=Role.assistant,
        kind="message",
        content=str(body),
        meta={"parsing": RAW_PARSING_MARKER, "framework": record["mas_name"]},
    )
    return task, [span]


def _ag2_parse(record: dict) -> tuple[str, list[Span]]:
    """Adapt the AG2 record shape to the ``(record) -> (task, spans)`` parser contract."""
    raw = json.loads(record["trace"])  # may raise; to_trace catches and falls back
    return _ag2_spans(raw)


# Per-framework structured parsers. Each takes a record and returns (task, spans);
# an empty span list (or a raised parse error) means "couldn't segment — fall back".
_PARSERS = {
    "AG2": _ag2_parse,
    "MetaGPT": _metagpt_spans,
    "ChatDev": _chatdev_spans,
    "HyperAgent": _hyperagent_spans,
    "AppWorld": _appworld_spans,
    "GAIA": _gaia_spans,
}


def to_trace(record: dict) -> Trace:
    """Convert one MAST dataset record into a canonical ``Trace``."""
    mas = record["mas_name"]
    parser = _PARSERS.get(mas)
    task: str = ""
    spans: list[Span] = []
    if parser is not None:
        try:
            task, spans = parser(record)
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            spans = []
    if not spans:  # unknown framework, or parser found no structure — stay honest
        task, spans = _raw_span(record)

    return Trace(
        trace_id=_trace_id(record),
        framework=mas,
        task=task,
        spans=spans,
    )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_human_dataset(path: str | Path) -> list[dict]:
    """Load raw records from ``MAD_human_labelled_dataset.json``."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_segmented(trace: Trace) -> bool:
    """True when the adapter produced real per-turn spans, False when it fell back to a
    single raw blob. The κ run uses this to score only traces whose findings can carry
    genuine span evidence (blob traces would collapse every finding onto one span)."""
    return not (
        len(trace.spans) == 1
        and trace.spans[0].meta.get("parsing") == RAW_PARSING_MARKER
    )


def iter_labeled_traces(
    path: str | Path, *, segmented_only: bool = False
) -> Iterator[tuple[Trace, MASTGold]]:
    """Yield ``(Trace, MASTGold)`` pairs for every record — the shape Step 4 evals want.

    ``segmented_only=True`` drops traces the adapter couldn't segment (still blob-only
    frameworks), so the κ run scores only evidence-bearing traces."""
    for record in load_human_dataset(path):
        trace = to_trace(record)
        if segmented_only and not is_segmented(trace):
            continue
        yield trace, gold_labels(record)
