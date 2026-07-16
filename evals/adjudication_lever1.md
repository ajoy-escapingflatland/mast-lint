# Lever-1 adjudication: the taxonomy edit was a wash, and eval-diff hid why

**Context.** After the 6 Lever-1 disambiguation edits (`taxonomy.yaml`, commit 186cba8),
the judge was re-run 5× (`evals/raw_lever1.run{1..5}.json`). `eval-diff` against the
pre-edit baseline (`evals/raw_findings.json`) flagged changed cells toward/away the
*human gold*. But the human gold is lossy — the prior adjudication
(`evals/adjudication.md`) already established the *true* status of many cells. Re-scoring
the **stable** changed cells (fired-status consistent across the 5 runs) against that
**adjudicated truth** — not lossy gold — flips two of the verdicts `eval-diff` reported.

Method: `evals/raw_lever1.run*.json` cross-referenced per (trace, mode); a cell is
"stable" if it fired in 0/5 or 5/5 runs. k/5 firing counts below are literal from the run
files.

## Verdicts (against adjudicated truth, not lossy gold)

| cell | baseline | L1 k/5 | prior adjudication | Lever-1 verdict |
|---|---|---|---|---|
| mad-1/FM-1.1  | fired | 0/5 | **wrong** (invented-content, not spec-disobey) | ✓ WIN — error removed |
| mad-2/FM-1.3  | fired | 0/5 | **wrong** (redundant double-label of FM-1.5 loop) | ✓ WIN — error removed |
| mad-7/FM-1.1  | fired | 1/5 | **wrong** (reasoning error, mis-attributed) | ✓ WIN — mostly removed |
| mad-16/FM-3.1 | fired | 1/5 | **correct** (real premature term, humans missed) | ✗ REGRESSION — true detection silenced |
| mad-1/FM-2.5  | fired | 0/5 | (agreement TP, not previously adjudicated) | ~ borderline — see below |
| mad-14/FM-3.3 | fired | 0/5 | (agreement TP) | ~ borderline — failure still caught under FM-3.2 |

### The FM-1.1 / FM-1.3 edits worked (3 solid wins)
All three silenced cells were adjudicated **genuine judge errors** (over-attribution /
redundant double-labels). Removing them is pure precision gain the naive κ can't see.
Keep these edits.

### The FM-3.1 edit BACKFIRED (the important negative)
The edit ("exclude fixed-pipeline/harness structural end; FM-3.1 needs an AGENT declaring
done") aimed to kill the MetaGPT structural-end mislabels mad-9 and mad-14 (both
adjudicated **wrong**). It did the opposite:

- `mad-9/FM-3.1` fires **5/5** — *not* silenced. Rationale: "run ends with empty reviewer
  responses ... tests never executed ... unverified inconsistent state."
- `mad-14/FM-3.1` fires **5/5** — *not* silenced. "run ends on an empty reviewer message
  ... task effectively incomplete."
- `mad-16/FM-3.1` fires **1/5** — the one adjudicated **correct** premature-termination,
  now suppressed. "ends after the reviewer's methodology comment with the delivered answer
  (0) still incorrect ... true task goal unmet."

Root cause: **MetaGPT always ends the same way** (after an empty/critique reviewer message
with the task incomplete), so "structural harness end" and "genuine premature stop" are
indistinguishable at the trace level. The adjudication's own line between mad-9/14 (wrong)
and mad-16 (correct) was fine and arguable — mad-9/14 were only resolved to "wrong" in the
adversarial second pass. A definition-level exclusion can't operationalize that line. FM-3.1
is intrinsically unreliable on fixed-round frameworks; the fix is not a sharper near_miss.

### The two "regressions" eval-diff over-counted are mostly benign
- `mad-14/FM-3.3` (Incorrect Verification): the faulty-tester failure is real, but the judge
  still fires `FM-3.2` **5/5** and `FM-1.3` **5/5** on mad-14 — the verification failure is
  still flagged, under a neighbor. This is de-duplication (like mad-2/FM-1.3), not a lost
  detection.
- `mad-1/FM-2.5` (Ignored Other Agent's Input): the s99/s101 behavior (agents disregard the
  confirmed bug reproduction, call it "working as expected") is real, but mad-1 is the 277K
  HyperAgent chaos-trace whose judge firings swing wildly run-to-run (FM-1.4/2.1/2.4/2.6/1.5
  come and go across the 5 runs). With only a **single** baseline run, the 0/5 cannot be
  attributed to Lever-1 vs. baseline noise, and FM-3.3 (5/5) partly absorbs the same
  behavior. Unattributable without the baseline arm (original taxonomy × N), which was
  deferred.

## Bottom line
Lever-1 is **net wash-to-slightly-positive**: +3 real precision fixes (FM-1.1/1.3), −1 real
regression (FM-3.1 mad-16), the FM-3.1 edit missed both its actual targets, and the FM-2.2/2.3
recall lever did not fire at all. Naive κ stayed flat (0.19 ± 0.04) because the wins and the
regression roughly cancel on the lossy metric — but the *composition* matters for the next edit.

## Next taxonomy actions
1. **Keep** the FM-1.1 and FM-1.3 near_miss/confused_with edits — verified wins.
2. **Revert or rethink** the FM-3.1 structural-end exclusion — it inverted its target.
   FM-3.1 on MetaGPT/fixed-round harnesses may be inherently undecidable from the trace;
   consider framework-aware handling rather than a definition tweak.
3. **Rework** the FM-2.2/FM-2.3 recall edits — no stable toward-gold firing resulted.
4. The remaining open question (did Lever-1 *cause* the mad-1/FM-2.5 drop?) needs the
   deferred baseline arm to answer cleanly.
