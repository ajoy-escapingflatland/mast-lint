# Step-4 adjudication: the naive κ under-rates the judge

**TL;DR.** The naive Step-4 numbers (precision **0.40**, Cohen's κ **0.25**) treat the
3-annotator MAST labels as perfect ground truth. They aren't. When the 52
judge-vs-human **disagreement** cells are re-judged against the actual trace
evidence, most of the judge's "false positives" turn out to be **real,
span-verifiable failures the human panel missed**. Adjudicated:

| Measure | Naive (labels = truth) | Adjudicated (conservative) | Adjudicated (generous) |
|---|---|---|---|
| Precision | 0.40 | **0.86** | 0.86 |
| Recall | 0.48 | 0.69 | 0.88 |
| Cohen's κ | 0.25 | **0.67** | 0.82 |

Paper's *human–human* κ = 0.88. **Precision is now a point estimate (0.86), not a
band** — see the second-opinion pass below. Only recall retains a band (the 13
unresolved FN borderlines). The honest read is **κ ≈ 0.67–0.82, precision ≈ 0.86**,
i.e. the judge is at/near human-panel quality; the raw 0.25 was measuring label noise.

## Method (blind, to blunt "graded my own homework")

- Only the **52 disagreement cells** (judge XOR human-majority) were adjudicated;
  the 132 agreement cells (TP+TN) are assumed correct (standard adjudication move).
- Each cell was judged **PRESENT/ABSENT from the trace against the taxonomy's
  operational definition first**, then compared to who fired. Both directions were
  scrutinised — judge false-positives *and* judge false-negatives — so the pass can
  find judge under-performance, not just flatter it.
- Verdicts that hinge on a literal string in the trace were **verified** (marked
  VERIFIED in `adjudicate.py`): e.g. mad-6 really contains `pip uninstall
  scikit-learn`; mad-10 really co-emits `Table read successfully` + `1 passed`
  alongside an unresolved `ValueError`; mad-3's task really says "solver/creator".

Reproducible: `python evals/adjudicate.py` (pure, no API).

## What the disagreements actually are

**Judge "false positives" (30 cells): 23 correct · 7 wrong** (after the
second-opinion pass resolved the 10 borderlines to 4 correct / 6 wrong). 23 of 30
"false positives" are real failures the 3-annotator panels missed. The 7 genuine
judge errors are **not hallucinations** — they are real behaviours with imperfect
mode attribution: mad-7/mad-1 FM-1.1 (reasoning-error/invented-content tagged as
spec-disobey), redundant overlap firings (mad-2 FM-1.3, mad-10 FM-1.5 double-label a
loop already caught), and MetaGPT's structural pipeline-end mislabelled FM-3.1
(mad-9, mad-14).

### Second-opinion pass on the 10 borderline FPs (adversarial)

Because the first pass had a pro-judge thesis, the 10 `borderline` FP cells were
re-judged from fresh trace evidence **while actively trying to prove the judge
wrong**. Result: 4 correct, 6 wrong — and precision collapsed from a 0.78–0.98 band
to a firm **0.86**. Even under adversarial ruling, precision never approaches the
naive 0.40. Decisive verifications this pass: mad-1 really contains contradictory
`def _separable` bodies (one even has signature `(left, right)`) and its
"verification" is the Executor saying *"the output will be the same"* — predicting
output it never ran — then declaring "the issue has been resolved"; mad-6's
"Pipeline fitted successfully" is a fabricated `print`, never executed. Per-cell
rulings live in `SECOND_OPINION` in `adjudicate.py`.

Gold-extraction cross-check (done): mad-10's `note.options` checks "Step repetition:
yes", "Trajectory restart: yes", "Invented content: yes", which at first looked to
contradict the aggregated gold (those modes scored 0–1/3). **Checked — not a bug.**
The adapter's `gold_labels()` faithfully majority-votes the structured 3-annotator
`annotations` array (there, "1.5 Step repetition" = a1 True / a2,a3 False = 1/3);
`note.options` is a *single-view* artifact (≈ annotator_1), not the 3-way ground
truth. The gold labels — and therefore the numbers above — stand. Bonus: the judge's
mad-10 FM-1.3/2.1/2.6 firings agree with annotator_1, i.e. they are real signals
majority-voting washed out, not judge inventions.

**Judge false-negatives (22 cells): 6 genuine misses · 13 borderline · 3 human over-labels.**
The recall gap is real but narrow, and concentrated in two places:
1. **Mode-overlap** — the judge fires *one* mode where humans tag several neighbours
   (FM-1.5↔FM-1.3 stopping/repetition; FM-1.1↔FM-2.3 disobey/derailment;
   FM-2.6↔FM-2.2 reasoning-mismatch/clarification). It found the failure, under an
   adjacent label.
2. **FC2 clarification/derailment** (FM-2.2, FM-2.3) — the judge genuinely
   under-fires "should have asked / drifted" modes (mad-10, mad-12).

**3 human over-labels** (mad-3/mad-4 FM-2.1 "Conversation Reset", mad-4 FM-2.3):
no restart/derailment exists anywhere in those traces — the judge was right to stay
silent.

## Consequences for the taxonomy work (this changes the plan)

The original Step-4 lever was "tighten definitions so the judge *fires less*." That
is now the **wrong** fix — suppressing firings would delete real detections to chase
lossy labels (Goodhart). The evidence says the lever is **disambiguation, not
suppression**:

- Sharpen `near_miss` / `confused_with` for the overlap clusters so the judge picks
  the *sharpest single* mode (or is explicitly allowed to fire multiple): 1.1↔2.3↔3.3,
  1.3↔1.5, 2.2↔2.6.
- Improve **recall** on FM-2.2 / FM-2.3, which the judge currently under-fires — the
  opposite of the "over-firing" story the naive precision told.

## Caveats

- Single adjudicator (me). A one-person gold is weaker than a panel; per-cell
  reasoning is written out in `adjudicate.py` for audit.
- v1 traces (Round 1, 18-mode draft taxonomy) carry a version confound: mad-3's six
  unanimous FNs could not be individually verified in a 314K-char trace and are
  parked as `borderline`, counted against the judge in the conservative bound.
- MetaGPT ProgramDev traces are terse role-action logs whose review/exec content
  lived in external `logs/NN.txt` files absent from the released dataset; a few
  cells are genuinely undecidable from the trace-as-adapted (`data-limited`).
