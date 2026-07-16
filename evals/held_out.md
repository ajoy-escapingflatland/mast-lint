# Held-out set (frozen 2026-07-16, as of commit `cd9fdf7`)

Status check-in against the 2026-07-14 office-hours design doc found that Step 4's
14-trace pool (AG2, ChatDev, HyperAgent, MetaGPT — 3/4/3/4 traces) had been used for
both taxonomy tuning *and* measurement, with no clean signal held back. That's the
circularity Premise 2 of the design doc exists to prevent.

**AG2 was the first candidate and was rejected.** All 3 AG2 traces (`mad-2`, `mad-7`,
`mad-12`) already fed the Lever-1 taxonomy edits — `mad-2` informed the FM-1.3
adjudication, `mad-7` informed FM-1.1. Picking AG2 would have given a
forward-clean-only set, not a genuinely held-out one.

## The held-out set: AppWorld

`data/MAD_human_labelled_dataset.json` has 19 total records across 6 frameworks.
Two frameworks were never touched by any judge run or adjudication round:
AppWorld (3 traces) and GAIA (2 traces). AppWorld was chosen — same size as AG2
would have been, so no loss of eval power, and large enough on its own without
mixing two architectures into one held-out number.

| trace_id (raw) | Adapted id | Round | Benchmark |
|---|---|---|---|
| 0 | `mad-0` | Round 1 | Test-C |
| 5 | `mad-5` | Round 2 | Test-C |
| 11 | `mad-11` | Round 3 | Test-C |

None of these three appear anywhere in `evals/adjudicate.py`, `evals/kappa_report.json`,
or any `evals/raw_lever1.run*.json` — confirmed genuinely untouched as of the freeze date.

## The freeze rule

**From 2026-07-16 forward: no edit to `taxonomy/taxonomy.yaml` may be informed by
`mad-0`, `mad-5`, or `mad-11`.** Don't read their judge output before deciding a
taxonomy change; don't adjudicate disagreement cells on them; don't use them to
justify a near_miss/boundary edit. They exist to answer one question once, cleanly:
does the taxonomy as tuned on the other 14 traces generalize, or not.

## Known limitation (disclose, don't hide)

AppWorld is not in `STRUCTURED_FRAMEWORKS` (`src/mastlint/adapters/mast.py`) — it has
no per-turn parser yet, so it's adapted as a single `raw_unsegmented` span rather than
real per-turn spans. The judge will still produce per-mode findings, but span-grounding
on AppWorld traces will be coarser than on the four structured frameworks. This is a
real limitation of the held-out result, not a reason to swap it for a contaminated
framework — state it alongside the held-out numbers when published.

## Held-out result (2026-07-16) — done

Ran once (`claude-opus-4-8`, `mast-lint eval data/held_out_appworld.json --raw-out
evals/raw_held_out_appworld.json --out evals/held_out_appworld_report.json`), no
re-runs, no cherry-picking. Raw findings + report committed as the audit trail:
`evals/raw_held_out_appworld.json`, `evals/held_out_appworld_report.json`.
(`data/held_out_appworld.json` — the 3-record AppWorld-only input — is a regenerable
staging file, not committed; `data/` is gitignored.)

**Overall: κ = -0.09, precision = 0.00, recall = 0.00. Zero true positives across
all 3 traces and all 14 modes.** Bootstrap 95% CI on κ: **[-0.18, 0.00]** — solidly
non-positive, does not cross into "better than chance." 2 false positives (FM-2.2,
FM-3.2), 6 false negatives, 0 true positives, out of 39 scored cells.

This is the honest number the design doc's Premise 1 asked for, and it's a
materially different result than the tuning-set numbers imply. For comparison, the
same bootstrap tooling run against the existing (contaminated) tuning-set
`evals/raw_lever1.run1.json` gives overall κ = 0.18, 95% CI [-0.00, 0.37] — already
weak, but the held-out set is worse and the CI doesn't even overlap zero on the
positive side. **The judge caught nothing real on data it wasn't tuned against.**
That's a stronger, more specific finding than "the numbers are thin" — it's evidence
the taxonomy-tuning cycles improved fit to the 14-trace pool without improving (or
while actively hurting) generalization.

Caveat still applies: AppWorld has no dedicated parser (`raw_unsegmented`), so this
result also confounds "judge generalizes poorly" with "judge sees a worse-quality
input on this framework." Untangling those two needs a second held-out framework —
see below.

## GAIA (2026-07-16) — second held-out set

**Correction to the earlier plan:** HyperAgent was proposed as the disambiguating
second held-out set, but it's contaminated too — all 3 HyperAgent traces in the
entire dataset (`mad-1`, `mad-6`, `mad-10`) are already in the 14-trace tuning pool.
No untouched HyperAgent data exists. GAIA (`mad-17`, `mad-18`, 2 traces) is the only
other genuinely untouched framework in the full 19-record dataset — same
`raw_unsegmented` confound as AppWorld (no dedicated parser), but a second,
independent framework.

Result: κ = -0.12, precision = recall = 0.00, **zero true positives across both
traces**. Bootstrap 95% CI on κ: [-0.12, 0.00]. Same story as AppWorld.
Raw findings + report: `evals/raw_held_out_gaia.json`, `evals/held_out_gaia_report.json`.

## Combined held-out (AppWorld + GAIA, 5 traces, 2026-07-16)

`evals/raw_held_out_combined.json`. **κ = -0.11, 95% CI [-0.15, 0.00]. Zero true
positives across every held-out trace, both frameworks, 67 scored cells.**

Two independent, unsegmented, never-tuned-against frameworks agree: the judge
detects nothing real on data outside the 14-trace tuning pool. Because both
held-out sets share the same `raw_unsegmented` confound, this doesn't yet fully
separate "the judge/taxonomy doesn't generalize" from "the judge does badly on
any unsegmented input regardless of tuning" — but it does rule out "AppWorld was
just an unlucky framework." The confound that's left is about segmentation, not
about which specific traces were picked.

## AppWorld, re-run with a real parser (2026-07-16)

`_appworld_spans()` written (`src/mastlint/adapters/mast.py`), verified against
all 3 real held-out traces (29/73/68 spans, correct task extraction, correct
agent sets), 99/99 tests pass. Re-ran the judge on the same 3 traces, now
properly segmented instead of one raw blob:
`evals/raw_held_out_appworld_segmented.json`, `evals/held_out_appworld_segmented_report.json`.

**Result: κ = 0.41, precision 0.60, recall 0.43. 3 true positives (up from 0).**
Bootstrap 95% CI: **[-0.18, 0.81]** — wide (n=3), but the point estimate is
meaningfully off zero, unlike the unsegmented run which was capped at 0.00.
**This confirms the pre-registered decision rule: segmentation matters, and
matters a lot.** The earlier "judge detects nothing" verdict was significantly
an artifact of feeding it one raw blob, not proof the judge/taxonomy has zero
capability.

**Per-trace picture, stated honestly rather than just the aggregate:**

| trace | version | human fired | judge fired | verdict |
|---|---|---|---|---|
| `mad-11` | v2 | FM-1.1, FM-2.2, FM-2.3, FM-3.2 | FM-1.1, FM-2.2, FM-3.2 | 3 TP, 1 FN, **0 FP** — a genuinely clean match |
| `mad-5` | v2 | FM-3.2 | (none) | silent miss, no false alarms |
| `mad-0` | v1 | FM-1.5, FM-2.5 | FM-2.2, FM-3.1 | **total mismatch** — zero overlap, all wrong modes |

`mad-11` alone drives most of the positive signal. `mad-0` shows the judge can
still confidently fire on completely wrong modes even with real spans — this
isn't "solved," it's "meaningfully better, still inconsistent, n=3 is nowhere
near enough to generalize from."

**What's still open:** GAIA remains unsegmented (2 traces, zero TP) — no parser
written for it yet. That's now a useful natural comparison rather than pure
confound: same "never touched by tuning" property, but AppWorld-segmented shows
real detection while GAIA-unsegmented shows none. Consistent with segmentation
being the dominant factor, but 3 + 2 traces is far too few to call this settled.
Next real test, if pursued: a GAIA parser, or — better signal per unit effort —
actual fresh dogfooded traces (the original Step 5 plan) from a framework with
real span structure that was never in this dataset at all.

## GAIA, partially segmented (2026-07-16)

GAIA isn't one framework — the 2 human-labeled GAIA traces come from two unrelated
agent systems with unrelated log formats. `_gaia_spans()` (`src/mastlint/adapters/mast.py`)
parses only the Magentic-One-shaped one (`mad-17`); `mad-18` (a different,
Python-logging-formatted agent) has no parser and correctly stays
`raw_unsegmented` rather than being force-fit. Re-ran the judge on both
(`evals/raw_held_out_gaia_segmented.json`):

- **`mad-17` (now segmented) alone: kappa = 0.28** (tp=1, fp=1, fn=2, tn=10) — a
  real, if modest, positive signal, consistent with AppWorld's pattern.
- **`mad-18` (still raw_unsegmented, and a trace with ZERO real human-labeled
  failures) alone: kappa = 0.0**, tp=0, **fp=4**, fn=0 — the judge hallucinated
  4 different failure modes on a clean trace fed as one blob. This is new,
  specific evidence that unsegmented input doesn't just cause misses — it also
  causes confident false alarms on runs with no real failures at all.
- Pooling both (1 segmented + 1 still-confounded) gives kappa=0.09 — a muddied
  number; reporting it alone would hide that the segmented trace is doing much
  better than the unsegmented one.

## All truly-segmented held-out traces combined (4 traces, 2026-07-16)

AppWorld's 3 segmented traces + GAIA's `mad-17`: **kappa = 0.37, 95% CI
[-0.10, 0.71]** (`evals/raw_held_out_all_segmented.json`). Consistent with
AppWorld alone (0.41) — now confirmed across two independent frameworks, not
one. Compare against the all-unsegmented baseline from earlier today (5 traces,
kappa = -0.11, CI [-0.15, 0.00]): **segmentation is the dominant factor found so
far**, not framework identity, not a fluke of AppWorld specifically.

Still true: n=4 is far too small to call this settled, mad-0 and mad-18 both
show the judge can be confidently wrong even with real spans (or none), and no
number here has been through a proper contamination-ceiling writeup yet. The
next highest-leverage step, if this continues, is fresh dogfooded traces —
more of the same 19-record dataset is close to exhausted.

Decision logged: see `gstack-decision-log` entries for `mast-lint`, 2026-07-16
(AG2-then-AppWorld resolution).
