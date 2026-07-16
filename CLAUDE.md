# CLAUDE.md — working guide for mast-lint

This file orients any Claude Code session on this repo. Read it before making changes.

## What this is
`mast-lint` is a **linter for multi-agent LLM traces**. You give it a trace of a
multi-agent run; it tells you which of the **14 MAST failure modes** occurred and
on which spans — e.g. *"FM-3.1 Premature Termination at span s4; the planner
declared done before the tester ran."*

MAST = the taxonomy from *Why Do Multi-Agent LLM Systems Fail?* (arXiv:2503.13657):
14 failure modes in 3 categories. It's encoded in `taxonomy/taxonomy.yaml`.

## The north star (do not drift from this)
Build the **measurement layer, never the runtime layer.** `mast-lint` observes and
judges traces after the fact. It must NEVER sit in a production trust/enforcement
path (no auth, no gating, no blocking actions). That single rule keeps the project
maintainable by one person, credible as a neutral tool, and free of the liability
that would come with being depended on at runtime. It is also what keeps this
project safely clear of the maintainer's day job (a DXP vendor): this is agent
*evaluation*, not agent content-ops or commerce — keep it that way.

## Architecture & the sacred contract
The flow is deliberately small:

    trace file → [adapter] → canonical Trace (schema.py) → segment() → judge() → Report

- **`taxonomy/taxonomy.yaml` is the core IP.** The 14 modes with operational
  definitions, signals, positive examples, and near-misses. Judge prompts are
  RENDERED from this file (see `judge.py::render_system_prompt`). When you improve a
  definition, do it here — never hard-code mode text elsewhere.
- **`src/mastlint/schema.py` is THE CONTRACT.** `Trace`/`Span`/`Finding`/`Report`.
  It is OTel-GenAI-shaped and framework-agnostic on purpose. All framework-specific
  knowledge stays inside `adapters/`; nothing downstream of an adapter should know
  whether a trace came from LangGraph, CrewAI, or AutoGen.
- **`Finding` must always carry `span_ids` evidence.** No finding without a pointer
  to where in the trace it happened. A judge that "feels" a failure but can't point
  to spans is a bug, not a finding.

## Current state (Step 4 in progress — held-out validation)
Scaffold, taxonomy, schema, judge, segmenter (v0: whole-trace-as-one-window, see
`segment.py`), report renderer, and the MAST/MAD dataset adapter (`adapters/mast.py`
— NOT LangGraph; that framework was never built) all exist and work. `mast-lint
lint` runs the real judge end-to-end. `mast-lint lint examples/trace.example.json`
surfacing FM-3.1 + FM-3.2 is verified at the plumbing level offline
(`tests/test_judge.py::test_judge_trace_surfaces_known_example_labels`, faked
judge) — not yet re-verified against a live judge call.

Step 4's original plan (hand-label 30–50 traces in `evals/labeled/`, κ vs the
paper's 0.88) was corrected via `/office-hours` on 2026-07-14 — the paper already
ships a validated annotator and 0.88 is inter-*human* agreement, not a κ-vs-0.88
comparison mast-lint can win. Ground truth now comes from the MAD human-labelled
dataset (19 records) instead; see `evals/README.md`. A 2026-07-16 status
check-in found the taxonomy-tuning cycles had been validated against the same
traces that shaped them — `taxonomy.yaml` is now frozen against a genuinely
held-out set (`evals/held_out.md`). Current honest number: κ ≈ 0.37 (95% CI
[-0.10, 0.71]) on 4 properly-segmented held-out traces across two independent
frameworks — real signal, nowhere near publishable (n far too small; the
19-record dataset is close to exhausted). Full trail: `evals/held_out.md`.

## Roadmap (build in this order)
1. **[done] Step 1** — taxonomy.yaml, schema, scaffold, example trace.
2. **[done] Step 2** — adapter into `Trace` for the MAST/MAD dataset, covering
   AG2, MetaGPT, ChatDev, HyperAgent, AppWorld, and Magentic-One-shaped GAIA
   traces (`adapters/mast.py`). Went further than "one framework" because the
   credibility-moat work in Step 4 needed several for a held-out split.
3. **[done, plumbing-level] Step 3** — `judge.py`, `segment.py` (v0), `report.py`
   implemented; `examples/trace.example.json` regression case passes offline
   (see above).
4. **Step 4 (the credibility moat), in progress** — see "Current state" above.
   Remaining: a proper contamination-ceiling writeup, and either more
   segmented-framework parsers or (better signal per unit effort) fresh
   dogfooded traces — the 19-record MAD set is close to exhausted.
5. **Step 5** — dogfood on real agent-loop runs; the results become the launch essay.

## Conventions
- Python ≥3.10, Pydantic v2, Typer CLI, `ruff` + `pytest`. Keep deps minimal.
- The LLM provider is intentionally unpinned until Step 3 — decide it then.
- Prefer small, pure functions the judge can be unit-tested around.
- `examples/trace.example.json` has KNOWN correct labels (FM-3.1, FM-3.2); use it
  as the first regression case.
- Never commit real customer traces (see `.gitignore`).

## Definition of done for v0
`mast-lint lint <trace>` runs an LLM judge over a real (adapted) trace, emits
evidence-backed Findings across the 14 modes, and there's a published κ number
saying how much to trust it.
