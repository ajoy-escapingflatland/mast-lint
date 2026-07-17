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

## Current state (Step 5 in progress — dogfood batch 2 done, κ off zero)
Scaffold, taxonomy, schema, judge, segmenter (v0: whole-trace-as-one-window, see
`segment.py`), report renderer, and the MAST/MAD dataset adapter (`adapters/mast.py`
— NOT LangGraph; that framework was never built) all exist and work. `mast-lint
lint` runs the real judge end-to-end. `mast-lint lint examples/trace.example.json`
surfacing FM-3.1 + FM-3.2 is verified at the plumbing level offline
(`tests/test_judge.py::test_judge_trace_surfaces_known_example_labels`, faked
judge) — not yet re-verified against a live judge call.

**Step 4 (the credibility moat) is essentially closed.** Its original plan
(hand-label 30–50 traces in `evals/labeled/`, κ vs the paper's 0.88) was
corrected via `/office-hours` on 2026-07-14 — the paper already ships a
validated annotator and 0.88 is inter-*human* agreement, not a κ-vs-0.88
comparison mast-lint can win. Ground truth came from the MAD human-labelled
dataset (19 records) instead; see `evals/README.md`. A 2026-07-16 status
check-in found the taxonomy-tuning cycles had been validated against the same
traces that shaped them — `taxonomy.yaml` was frozen against a genuinely
held-out set (`evals/held_out.md`): κ ≈ 0.37 (95% CI [-0.10, 0.71]) on 4
properly-segmented held-out traces across two independent frameworks — real
signal, nowhere near publishable alone (n far too small; the 19-record MAD
dataset is close to exhausted). The contamination-ceiling writeup
(`evals/contamination_ceiling.md`) distinguishes two channels:
taxonomy-induction contamination (closed by the freeze+held-out split above)
vs. pretraining-exposure contamination (the MAD dataset is public and predates
the judge model's cutoff, so no split of it can rule this out — only fresh
dogfooded traces can).

**Step 5 (dogfood on real agent-loop runs) now has two batches, 16 traces
total.** `evals/dogfood/` holds 16 fresh AG2 (Planner/Coder/Tester
`GroupChat`) traces run against organic, non-benchmark coding tasks designed
to *plausibly* exercise specific failure modes without forcing them
(`evals/dogfood/tasks.md`, `evals/dogfood/tasks_batch2.md`, `run_ag2.py`) —
contamination-clean by construction, since they were never published
anywhere before this project generated them.

- Batch 1 (8 traces): blind single-annotator labels
  (`evals/dogfood/gold_labels.md`), judged and adjudicated
  (`evals/dogfood/adjudication.md`) — κ = 0.65 (95% CI [-0.01, 0.94], n=8).
  That run also surfaced and fixed a real FM-1.2/FM-3.2 taxonomy boundary
  dispute (see the "resolve FM-1.2/FM-3.2 boundary dispute" and "live-verify
  the FM-3.2 edit, find it wrong, fix the real cause" commits).
- Batch 2 (8 more traces, targeting the six modes batch 1 never exercised):
  blind labels (`evals/dogfood/gold_labels_batch2.md`), judged and
  adjudicated (`evals/dogfood/adjudication_batch2.md`) — κ = 0.79 (95% CI
  [0.62, 0.94], n=8). Adjudication here also caught the pass-1 annotator
  applying its own FM-1.2 criterion inconsistently (two traces called clean
  actually had the same violation caught elsewhere in the batch) — recorded
  as a self-correction rather than silently fixed, since it's real evidence
  about single-annotator reliability.

**Combined: κ = 0.76 (95% CI [0.59, 0.94], n=16)** — see `evals/README.md`.
This is the first dogfood number with a CI clear of zero. Still
single-annotator on both batches, and batch 1's labels haven't been
re-audited with the stricter check that caught batch 2's self-correction —
that consistency pass, or a second qualified annotator, is the honest next
step before either batch counts as validated ground truth. FM-1.2 (Disobey
Role Specification) and FM-3.2 (claimed-but-unexecuted verification) are now
the dominant organic findings across both batches (9/16 and 7/16 traces
respectively) — neither was targeted by any task design — and the judge's
FM-1.2 recall stays weak (0.44–0.50) even after adjudication, confirming
rather than resolving this project's earlier documented recall gap.

## Roadmap (build in this order)
1. **[done] Step 1** — taxonomy.yaml, schema, scaffold, example trace.
2. **[done] Step 2** — adapter into `Trace` for the MAST/MAD dataset, covering
   AG2, MetaGPT, ChatDev, HyperAgent, AppWorld, and Magentic-One-shaped GAIA
   traces (`adapters/mast.py`). Went further than "one framework" because the
   credibility-moat work in Step 4 needed several for a held-out split.
3. **[done, plumbing-level] Step 3** — `judge.py`, `segment.py` (v0), `report.py`
   implemented; `examples/trace.example.json` regression case passes offline
   (see above).
4. **[done] Step 4 (the credibility moat)** — see "Current state" above.
   `taxonomy.yaml` frozen against a held-out MAD split; contamination-ceiling
   writeup done (`evals/contamination_ceiling.md`); it identified
   pretraining-exposure contamination as structurally unresolvable on the MAD
   dataset, which is why Step 5 (fresh, unpublished traces) is the only way to
   get a contamination-clean number.
5. **Step 5, in progress** — dogfood on real agent-loop runs; the results
   become the launch essay. Two batches done, 16 AG2 traces combined, κ = 0.76
   (95% CI [0.59, 0.94] — see "Current state"). CI is now off zero. Remaining
   before this can anchor the essay: a second qualified annotator (or at
   minimum a stricter self-consistency re-check of batch 1, since batch 2's
   adjudication caught the pass-1 annotator missing half its own true FM-1.2
   instances) — single-annotator ground truth is still the honest limitation,
   not sample size anymore.

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
