# Contamination ceiling

The design doc (`~/.gstack/projects/mast-lint/ashishjoy-unknown-design-20260714-204816.md`,
Key Design Notes) requires this statement before any number is published: *"agreement on
in-distribution MAST traces is optimistically biased ... state plainly."* This is that
statement, plus the arithmetic behind it.

## Two different contamination channels — only one is fixed

**Channel A — taxonomy-induction contamination.** `taxonomy.yaml` was iteratively edited
while looking at judge output on the 14-trace tuning pool (AG2, ChatDev, HyperAgent,
MetaGPT). Grading on those same 14 traces is partly test-on-training at the taxonomy
level, not just the trace level.

*Status: addressed.* `taxonomy.yaml` was frozen 2026-07-16 against AppWorld (`mad-0`,
`mad-5`, `mad-11`) and GAIA (`mad-17`, `mad-18`) — the two frameworks in the 19-record
dataset that fed zero taxonomy edits and zero adjudication rounds (see `held_out.md`).
No edit to the taxonomy since the freeze has been informed by these 5 traces.

**Channel B — pretraining-exposure contamination.** `MAD_human_labelled_dataset.json` is
a public, CC-BY-4.0 HuggingFace dataset (`mcemri/MAD`) drawn from a paper (arXiv:2503.13657,
submitted March 2025) that is itself public. The judge model (`claude-opus-4-8`) has a
training cutoff well after both dates. It is plausible the model saw this dataset, or the
paper's own worked examples, during training — independent of anything mast-lint did.

*Status: NOT addressed, and not addressable with this dataset.* The AppWorld/GAIA
held-out split guards only against Channel A. Every trace in `MAD_human_labelled_dataset.json`
— tuning-set and held-out alike — is equally exposed to Channel B, because they all come
from the same public corpus. A held-out *split* of a public dataset is not a held-out
*sample* with respect to the model's training data. This is exactly the distinction
Premise 2 of the design doc draws ("grade only on data the judge plausibly hasn't
memorized") and it is not satisfied by anything currently in `evals/`.

## Quantifying Channel A's effect size (the part we can measure)

Numbers already committed, none newly re-run for this writeup (`evals/kappa_report.json`,
`evals/adjudication.md`, `evals/adjudication_lever1.md`, `held_out.md`):

| Evaluation | Guards against | n | κ | 95% CI |
|---|---|---|---|---|
| Tuning-set, naive (labels = truth) | neither A nor B | 14 traces / 184 cells | 0.19 ± 0.04 (5-run mean) | not computed per-run |
| Tuning-set, adjudicated (re-checked truth) | neither A nor B | 14 traces / 52 disagreement cells re-judged | 0.67–0.82 | not computed (point/band, pre-bootstrap tooling) |
| Held-out, unsegmented (AppWorld+GAIA before parsers) | A only | 5 traces / 67 cells | -0.11 | [-0.15, 0.00] |
| Held-out, segmented (AppWorld + GAIA `mad-17`) | A only | 4 traces / cells per `raw_held_out_all_segmented.json` | 0.37 | [-0.10, 0.71] |

The adjudicated tuning-set number (κ 0.67–0.82) is the best-case figure achievable when
grading generously against re-checked truth on traces the taxonomy was tuned on. The
held-out segmented number (κ 0.37, wide CI) is the best figure achievable once Channel A
is removed. The drop between them — **roughly 0.3–0.45 κ** — is attributable to Channel A
alone (taxonomy overfit to the tuning pool), since Channel B is present in both rows
equally and therefore cancels out of the *comparison*, even though it doesn't cancel out
of either individual number.

That means: **taxonomy-induction contamination alone was worth about a third to a half of
a κ point.** Channel B's contribution is unknown and could be smaller or larger — there is
no clean row in this table where Channel B is absent, so its size cannot be isolated the
same way.

## Why Channel B can't be bounded with current tooling, and what would

Two options, neither done yet:

1. **A membership-inference probe** (cheap, doesn't need new ground truth): prompt the
   judge model with a truncated raw trace from `MAD_human_labelled_dataset.json` and check
   whether it completes the remainder above chance, compared to a paraphrased or synthetic
   control trace of matched length/content. Verbatim-completion ability above baseline
   would be positive evidence of memorization; failure to complete is *not* proof of
   non-memorization (the model could recognize content without being able to reproduce it
   token-for-token). This was not run this session — no `ANTHROPIC_API_KEY` was available
   in this environment, so it stays an open, low-cost follow-up rather than a finding.
2. **Fresh dogfooded traces** (the real fix, and already Step 5 on the roadmap): traces
   from a framework never published anywhere, generated after this writeup, can't be in
   any training set by construction. This is the only channel-B-clean evaluation possible.
   `held_out.md` already flags this as the next highest-leverage step once the 19-record
   MAD dataset is exhausted for taxonomy purposes — it's also the only way to get a
   Channel-B-clean number, which this writeup shows is a distinct reason to prioritize it,
   not just "more data."

## The statement to publish alongside any mast-lint number

> All reported κ / precision / recall figures are computed against
> `MAD_human_labelled_dataset.json` (Cemri et al., arXiv:2503.13657), a public dataset that
> predates the judge model's training cutoff. Two contamination channels apply: (1)
> taxonomy-induction contamination, which we control for via a taxonomy freeze and a
> held-out split (AppWorld + GAIA, untouched by any taxonomy edit) — held-out κ = 0.37,
> 95% CI [-0.10, 0.71], n=4 properly-segmented traces; (2) pretraining-exposure
> contamination, which no split of a public dataset can control for, and which we have not
> yet measured. Until evaluated on traces provably absent from the judge model's training
> data (fresh, unpublished, dogfooded traces — planned for Step 5), all numbers above
> should be read as an optimistic ceiling on out-of-distribution performance, not a
> generalization guarantee.

## Known adjacent gap (not in scope here, noted so it isn't lost)

The design doc's D2 segmentation decision also requires reporting the excluded-trace
fraction and the failure-mode prevalence within excluded traces, since `segment.py` is
still v0 (whole-trace-as-one-window, no token-budget cap implemented yet — see
`segment.py`). No traces have been excluded because exclusion isn't implemented, so this
requirement is currently vacuous rather than satisfied. Relevant again only once windowing
is built.
