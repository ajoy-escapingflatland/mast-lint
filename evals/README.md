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

## Step 5 (dogfood) — first pass

`dogfood/` is the first Step 5 batch: 8 fresh AG2 traces, contamination-clean
by construction (never published, generated after `contamination_ceiling.md`
was written specifically because MAD couldn't produce a clean number). See
`dogfood/gold_labels.md` for the blind single-annotator labels and
`dogfood/adjudication.md` for the judge run against them — adjudicated κ =
0.65 (95% CI [-0.01, 0.94], n=8), replicating this project's earlier
naive-vs-adjudicated pattern on genuinely fresh data. Single-annotator and
n=8: informative, not publishable on its own.
