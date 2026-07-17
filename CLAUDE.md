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

## Current state (Step 5 in progress — dogfood batch 3 done, task-content lever exhausted)
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

**Step 5 (dogfood on real agent-loop runs) now has three batches, 24 traces
total.** `evals/dogfood/` holds 24 fresh AG2 (Planner/Coder/Tester
`GroupChat`) traces run against organic, non-benchmark coding tasks designed
to *plausibly* exercise specific failure modes without forcing them
(`evals/dogfood/tasks.md`, `tasks_batch2.md`, `tasks_batch3.md`,
`run_ag2.py`) — contamination-clean by construction, since they were never
published anywhere before this project generated them.

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
- Batch 3 (8 more traces, targeting the remaining 9 never-fired modes with
  mechanisms deliberately different from batch 2's, same harness kept
  unchanged on purpose): blind labels (`evals/dogfood/gold_labels_batch3.md`),
  judged and adjudicated (`evals/dogfood/adjudication_batch3.md`) — κ = 0.76
  (95% CI [0.44, 0.96], n=8). A third consecutive null on the targeted
  modes — zero of the 8 newly-targeted modes fired. Adjudication caught a
  second, independent instance of the batch-2 self-correction pattern (a
  clean-labeled trace that actually had the same FM-1.2 violation caught
  elsewhere in the same batch).

**Combined: κ = 0.76 (95% CI [0.61, 0.88], n=24)** — see `evals/README.md`.
Tighter CI than the 16-trace number. Still single-annotator on all three
batches, and none has been re-audited by an actual second annotator (only by
re-reading against the judge's own findings) — that's the honest next step
before any batch counts as validated ground truth. FM-1.2 (Disobey Role
Specification) and FM-3.2 (claimed-but-unexecuted verification, plus one new
"zero verification attempted at all" flavor in batch 3) are the dominant
organic findings across all three batches (14/24 and 10/24 traces
respectively) — neither was targeted by any task design in any batch — and
the judge's FM-1.2 recall, while improving batch over batch (0/3 → 3/6 →
5/5), sits at 0.64 combined, still the weakest spot in judge coverage. **More
importantly: after three batches with genuinely varied task designs, 9 of
the 14 MAST modes have never organically fired once.** The task-content
lever looks exhausted for this specific harness (AG2, `auto` speaker
selection, `max_round=12`, no human in the loop) — see the recommendation at
the end of `evals/dogfood/gold_labels_batch3.md`. Getting the remaining modes
likely needs a structural harness change (longer/multi-session conversations,
genuine context truncation, or a different framework), not a fourth batch of
new task content on the same runner.

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
   become the launch essay. Three batches done, 24 AG2 traces combined,
   κ = 0.76 (95% CI [0.61, 0.88] — see "Current state"). CI is tight enough
   to anchor a headline number. Two things remain before this is genuinely
   done: (a) single-annotator ground truth — a second qualified annotator, or
   at minimum a stricter self-consistency re-check of batch 1, since batches
   2 and 3 both caught the pass-1 annotator missing true FM-1.2 instances;
   (b) coverage — 9 of 14 MAST modes have never organically fired across 24
   traces despite two batches of deliberately varied task designs aimed at
   them, which points at a harness limitation rather than a task-design one.
   A fourth batch should change the harness (longer conversations, real
   context truncation, a different framework) rather than repeat the same
   recipe with new task content — see `evals/dogfood/gold_labels_batch3.md`'s
   closing recommendation.

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
