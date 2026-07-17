# Evals — the credibility harness (Step 4)

The whole product hinges on one question: **why should anyone trust the judge?**
Answer it with a number.

**Superseded plan, kept for history:** the original plan below (self-collect
30-50 traces into `labeled/`, grade against your own labels, compare κ to the
paper's 0.88) was replaced on 2026-07-14 by the corrected office-hours design
(`~/.gstack/projects/mast-lint/ashishjoy-unknown-design-20260714-204816.md`):
κ-vs-0.88 is apples-to-oranges (0.88 is inter-human, not LLM-vs-human), and the
paper already ships a validated annotator. `labeled/` is empty and unused —
ground truth now comes from the MAD human-labelled dataset instead.

## Current methodology
- Gold labels: `data/MAD_human_labelled_dataset.json` (19 records, 3 annotators
  each), adapted via `src/mastlint/adapters/mast.py`.
- 14 traces (AG2×3, ChatDev×4, HyperAgent×3, MetaGPT×4) are the **tuning set** —
  used for taxonomy adjudication and the per-mode P/R/F1/κ in `kappa_report.json`.
- **`mad-0`, `mad-5`, `mad-11` (AppWorld) are the held-out set — frozen, never
  used to inform `taxonomy.yaml`.** See [`held_out.md`](held_out.md) for the
  freeze rule, the AG2-was-contaminated finding, and the raw_unsegmented caveat.
- Report per-mode P/R/F1 + bootstrap CI (see `held_out.md`) and the contamination
  ceiling (see [`contamination_ceiling.md`](contamination_ceiling.md)) before
  publishing any number. Both are written up; the contamination ceiling itself is
  only partially closable — see that file for the taxonomy-induction vs
  pretraining-exposure distinction and what remains open.

`examples/trace.example.json` is the first seed case (known labels: FM-3.1 + FM-3.2).

## Step 5 (dogfood)

`dogfood/` holds three batches of fresh AG2 traces, contamination-clean by
construction (never published, generated after `contamination_ceiling.md`
was written specifically because MAD couldn't produce a clean number).

- **Batch 1** (8 traces): see `dogfood/gold_labels.md` for the blind
  single-annotator labels and `dogfood/adjudication.md` for the judge run
  against them — adjudicated κ = 0.65 (95% CI [-0.01, 0.94], n=8).
- **Batch 2** (8 more traces, designed to probe the six failure modes batch 1
  never exercised): see `dogfood/gold_labels_batch2.md` and
  `dogfood/adjudication_batch2.md` — adjudicated κ = 0.79 (95% CI [0.62,
  0.94], n=8). Batch 2's adjudication also caught a real inconsistency in its
  own blind pass-1 labels (two traces initially called clean actually had the
  same FM-1.2 violation caught elsewhere in the batch) — see
  `adjudication_batch2.md` for the self-correction, kept in the record rather
  than silently fixed.
- **Batch 3** (8 more traces, targeting the remaining 9 modes with mechanisms
  deliberately different from batch 2's attempts — same harness, kept
  unchanged on purpose): see `dogfood/gold_labels_batch3.md` and
  `dogfood/adjudication_batch3.md` — adjudicated κ = 0.76 (95% CI [0.44,
  0.96], n=8). A third consecutive null result on the targeted modes: zero of
  the 8 newly-targeted modes fired. Batch 3's adjudication caught a second,
  independent instance of the exact self-correction pattern from batch 2 (a
  trace called clean on the blind pass turned out to have the same FM-1.2
  violation already caught elsewhere in the same batch) — see
  `adjudication_batch3.md`.

**Combined, all three batches: κ = 0.76 (95% CI [0.61, 0.88], n=24).** Tighter
CI than the 16-trace number and still the current headline number for the
project — see `dogfood/judge_report_combined_24trace.json`. Still
single-annotator on all three batches, and none of the batches has been
re-audited by a second annotator (only by re-reading against the judge's own
findings) — the honest next step before treating any of this as validated
ground truth remains a second qualified annotator.

Across all three batches, **FM-1.2 (Disobey Role Specification) fires in at
least 14 of 24 traces and FM-3.2 (No or Incomplete Verification) in at least
10 of 24** — both organic, neither targeted by any task design across any
batch. No other mode has fired more than twice in 24 traces. The judge's
recall on FM-1.2 specifically has improved batch over batch (0/3 → 3/6 →
5/5) but sits at 0.64 combined — still the weakest spot in the judge's
coverage, confirming rather than resolving this project's earlier documented
recall gap. **After three batches with genuinely varied task designs
producing zero organic instances of 9 of the 14 MAST modes, the task-content
lever looks exhausted for this specific harness** (AG2 Planner/Coder/Tester
`GroupChat`, `auto` speaker selection, `max_round=12`, no human in the loop)
— see the recommendation at the end of `dogfood/gold_labels_batch3.md`.
Getting organic coverage of the remaining modes likely needs a structural
change to the harness itself (longer/multi-session conversations, a
different framework, or genuine context truncation), not another batch of
new task content on the same runner.

## Step 5, batch 4 — a genuinely different harness (reported separately)

**Batch 4 changes the harness itself**, not just task content, per the
recommendation above: `run_ag2.py --context-window 6 --max-round 24` gives
each agent a real sliding window (AG2's `MessageHistoryLimiter`, confirmed
to actually trim history both offline and in-trace) instead of full
conversation history, with `max_round` doubled to give the window room to
matter. See `dogfood/tasks_batch4.md` for the harness design and the 8 tasks
built around it, `dogfood/gold_labels_batch4.md` for blind labels, and
`dogfood/adjudication_batch4.md` for the judge run — adjudicated **κ = 0.76
(95% CI [0.50, 0.87], n=8)**.

**This number is reported separately, not pooled into the combined 24-trace
figure above** — it's a structurally different, deliberately harder harness
(agents genuinely lose context, not just a different task distribution), so
combining it would silently change what the headline number means without
changing its label.

Batch 4's biggest finding isn't a κ number, though: `long-horizon-scope-creep`
produced a real, organic regression caused by context truncation itself — a
defensive list copy silently dropped when Coder reconstructed "the full
class" after the original code scrolled out of its window, falsely claimed
"unchanged" by both Coder and a later Tester pass that never actually diffed
against the true original (FM-1.1 + FM-3.3, both confirmed by direct text
comparison). `repeated-utility-pattern` independently reproduced the same
"silently-broken logic pass, final verification never happens" pattern. In 5
of 8 traces, though, FM-1.2's usual early-consolidation habit meant the
targeted mechanism never got a fair test — the harness change is real and
working, but FM-1.2 remains the dominant confound even here.
