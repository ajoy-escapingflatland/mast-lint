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

`dogfood/` holds two batches of fresh AG2 traces, contamination-clean by
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

**Combined, both batches: κ = 0.76 (95% CI [0.59, 0.94], n=16).** This is the
first dogfood number with a CI clear of zero and is the current headline
number for the project — see `dogfood/judge_report_combined_16trace.json`.
Still single-annotator on both batches (no second qualified annotator on
either), and batch 1's labels haven't been re-audited with the stricter
consistency check that surfaced batch 2's self-correction — the honest next
step before treating either batch's gold as validated ground truth remains a
second annotator pass.

Across both batches, **FM-1.2 (Disobey Role Specification) fires in at least
9 of 16 traces and FM-3.2 (No or Incomplete Verification, specifically
claimed-but-unexecuted verification) in at least 7 of 16** — both organic,
neither targeted by task design. The judge's recall on FM-1.2 specifically
remains weak (0.44–0.50 across the two batches) even after adjudication,
confirming this project's earlier "FM-1.2 recall gap" finding
(see git history) rather than resolving it.
