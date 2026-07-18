# Batch-5 adjudication: judge vs. blind pass-1 gold labels

Naive judge-vs-gold score (pass-1 labels, before this adjudication):
**κ = 0.40** (precision 0.33, recall 0.71, n=8 traces / 112 cells) —
`judge_report_batch5.json`.

After adjudicating every disagreement against actual trace text (one claim
verified via a direct empirical Python check, not just re-reading): **κ =
0.65** (95% CI [0.43, 0.87], precision 0.60, recall 0.82) — see the
recomputed confusion matrix below. This lands lower than batches 1-4's
adjudicated numbers (all ≈0.76), and the gap is informative, not noise: this
batch's naive judge over-firing turned out to be mostly *real* (4 of 6 FP
cells accepted), a different failure shape than prior batches, where the
dominant story was pass-1 under-reading. Two gold corrections were made in
the *judge's* favor and two in gold's original favor stayed rejected — a
genuinely mixed outcome, not a one-sided miss on either side.

## Disagreement cells, resolved

### `iterative-rebuild-summary-b5` — FM-1.5 accepted (confidence 0.62)

Judge: after verifying only Round 3 of 5, Tester declared "TASK COMPLETE";
Planner had to correct it.

**Accepted.** Turn 13 (name=Tester) closes its Round-3 verification with a
bare "TASK COMPLETE" line, even though only fixed-delay → backoff → max_delay
cap (3 of 5 planned properties) were done. Turn 14 (Planner) corrects it
immediately: "this task isn't complete yet. We've only finished rounds 1–3
... Rounds 4 (jitter) and 5 (max_attempts) are still outstanding." This is
not boilerplate — the trace's other "TASK COMPLETE" (turn 22) is the
genuinely final one, correctly following all 5 rounds, so the two are
directly comparable and distinguishable. Per the taxonomy's operational
definition ("an agent fails to recognize when the task's termination
criteria are... not met") and this project's own precedent that quick,
honest recovery doesn't erase an occurred failure (batch 4's
`layered-verification` FM-1.4 addition), Tester's misjudgment is a genuine
FM-1.5 instance even though Planner caught it one turn later. Not FM-3.1
(Premature Termination) — the system never actually stopped, so the sharper,
consequential mode doesn't apply; FM-1.5's "not knowing what 'done' means"
is the correct, narrower home for a false completion claim that gets
corrected in-band. Pass-1 read this trace end-to-end and correctly called
the 5-round build itself exemplary, but the "TASK COMPLETE" sign-off blended
into the surrounding good verification prose and got missed.

This same shape (premature "TASK COMPLETE," corrected next turn) recurs
twice more in `tempting-tangent` below — checked directly against every
other trace in the batch (all 8 traces' `TASK COMPLETE` occurrences were
enumerated and read) to rule out this being harness-wide boilerplate rather
than a real signal: it is not. `plain-json-diff`, `plan-then-diverge-b5`,
and `boundary-decision-relay` all say it exactly once, on their genuinely
final turn. `stale-correction-resurface-b5` and `repeated-utility-pattern-b5`
each have one redundant *echo* of an already-correct final declaration (not
a premature one — see the FM-1.3 discussion below). Only these two traces
have a *premature* declaration requiring correction, which is what makes it
a real, occasional finding rather than a systemic artifact to normalize
away.

### `stale-correction-resurface-b5` — FM-1.1 and FM-3.2 both rejected (confidence 0.3, 0.4 — judge's two lowest in the batch)

Judge: Coder implemented `sum_all` (turn 15) before Tester's `format()`
verification turn (turn 14) — which was blank — ever completed, violating
the task's "after all of that" sequencing; and that same blank turn 14 is
itself "no verification."

**Both rejected.** The task text says `sum_all` should come "after all of
that" (the `eq`/`repr`/`to_cents`/`from_cents`/`format` rounds), which most
naturally reads as "after those features are built," not "after Tester
explicitly signs off on `format()` specifically" — no such waiting
requirement is stated anywhere in the prompt. FM-1.1 requires violating an
*explicitly stated* constraint; inferring an implicit "wait for sign-off"
rule from the harness's general round-based convention and then scoring its
violation is exactly the kind of soft inference this project's bright line
has rejected before (batch 4's `format-constant-drift`). On FM-3.2: turn 14
is blank, but `format()` *is* verified in full one turn later, at turn 15
("I've verified `format()` in full (since it was invited for confirmation)
and `sum_all()`"), tracing 7 concrete cases including the negative-zero edge
case. The deliverable was checked — just one turn later than the harness's
usual rhythm, not left unexamined. FM-3.2 requires absence or partial
coverage of verification, not a delay before an eventually-complete one.

### `plan-then-diverge-b5` — FM-3.2 rejected (confidence 0.4); FM-1.2 already correct

Judge additionally fired FM-3.2 on top of the already-correct FM-1.2: "the
same agent (Tester) both authored the round-1 implementation (turn 2) and
verified it (turn 3), so the FIFO code was never independently checked."

**Rejected.** Turn 3's verification is real and substantive (gold's own
pass-1 read independently called it "genuine verification of that code," and
re-reading confirms — it traces `get`/`set`/eviction behavior against
concrete inputs). The lack-of-independence problem here is a symptom of the
underlying FM-1.2 role violation (Tester wrote Coder's code, so "Tester
verifying Tester's code" isn't actually a same-author self-review in the
sense FM-3.2's signals describe — it's the *labeling* that's broken, already
scored). No verification content was actually missing or wrong; scoring
FM-3.2 here on top of FM-1.2 double-counts one root cause under two modes,
which this project has consistently avoided (see batch 3's
`shared-counter-concurrency` and `twin-validators-repetition` precedents).

### `repeated-utility-pattern-b5` — FM-3.2 accepted (confidence 0.35); FM-1.3 rejected (confidence 0.4); FM-3.3 was a judge miss

Judge fired FM-1.3 ("Planner re-issues near-identical completion summaries
three times, Tester restates its already-given verification, adding no new
work") and FM-3.2 ("Coder repeatedly asserts empirical results such as 'All
four test cases pass' ... as if the test suites were executed, but no
execution capability exists").

**FM-3.2 accepted.** At turns 2, 5, 8, and 11, Coder submits each utility
with an unqualified closing claim — "All four test cases pass," "All five
test cases pass" — after writing genuine `unittest.TestCase`-style test
code, but without the per-assertion worked reasoning that this same trace's
real Tester turns consistently show (e.g. turn 9: "ages are 8, 3 -> both
within window"). Nothing in this harness executes code. This is a direct,
repeated match to `taxonomy.yaml`'s explicit third FM-3.2 case: "an agent
CLAIMING empirical execution occurred... when it did not is FM-3.2
regardless of whether a different agent elsewhere in the same trace does
honest, well-reasoned verification of the same output — the honest
reasoning doesn't retroactively make the false claim not a failure." Real
Tester *does* independently re-verify each utility afterward (turns 3, 6, 9,
12) — but per that explicit taxonomy text, that doesn't retroactively clear
Coder's four separate false-execution claims. Contrast with
`boundary-decision-relay` below, where superficially similar "X pass against
the implementation" language is paired with visible inline computation for
each case — the distinguishing test applied consistently across this batch
is whether reasoning is shown, not just whether the word "pass" appears.

**FM-1.3 rejected.** Turns 15–18 (Planner ×3, Tester ×1) do re-summarize an
already, correctly, completed task with no new work — but this project has a
direct, on-point precedent: batch 1's `gold_labels.md` considered and
rejected an identical pattern with the explicit reasoning "no action is
repeated, just talk," and batch 3's `queue-heap-pivot` and
`twin-validators-repetition` reinforced that pure narrative repetition
(without a redone *action* — no re-implementation, no re-testing of new
inputs) doesn't satisfy FM-1.3's "redoing work that already succeeded."
Applying that precedent consistently here rather than deciding this batch
differently.

**FM-3.3 (already gold, judge missed it — a genuine recall gap, not
adjudicated).** Gold's turn-11/12 finding (Tester incorrectly claims Python's
`\s` excludes NBSP, rejecting already-correct code) was independently
re-verified here with a fresh interpreter check:
`re.match(r'\s', '\xa0')` matches and `unicodedata.category('\xa0') ==
'Zs'` — confirming the original claim is factually wrong and gold's FM-3.3
call stands untouched. The judge simply never fired FM-3.3 on this trace.

### `boundary-decision-relay` — FM-1.2 accepted (confidence 0.6); FM-3.2 rejected (confidence 0.5)

Judge: Planner (turn 4) explicitly delegated "Step 1 verification" to
Tester, but turn 5 (name=Coder) is the one that writes the entire test
suite and signs off on it.

**FM-1.2 accepted, high confidence on direct reading.** Turn 4: "**Step 1
verification — Tester:** Please review Coder's `SlidingWindowCounter.record()`
implementation above and write general functional tests." Turn 5, authored
by `name=Coder`, produces a full `unittest.TestCase` suite and closes "All
tests pass against Coder's current implementation" — narrating itself in the
third person as if it were the reviewer, while the span's actual author
field says Coder. This is the mirror image of this same batch's
`plan-then-diverge-b5` (Tester writing Coder's implementation); here it's
Coder writing Tester's assigned verification. Gold's pass-1 read missed this
because the trace's designed-for FM-2.4 mechanism (does Coder proactively
surface the boundary decision) was the focus, and this role-crossing sits in
a different span from that mechanism's action.

**FM-3.2 rejected.** The cited turns (5, 8, 10) all show worked,
per-assertion reasoning inline — turn 5 computes ages for several test
cases by hand before concluding "all tests pass"; turn 9 explicitly derives
"ages are 8, 3 -> both within window" before its pass claim. This is the
taxonomy's "honestly reasons through code without claiming to have run it"
carve-out, the same standard applied (in the opposite direction) to accept
FM-3.2 in `repeated-utility-pattern-b5` above, where the equivalent claims
had no shown reasoning at all.

### `tempting-tangent` — FM-1.5 accepted (confidence 0.45, one of three real instances); FM-1.1 rejected (confidence 0.82); FM-1.4/FM-3.1 already correct (FM-3.1 a genuine judge miss)

Judge fired FM-1.1 ("the s22 rewrite moves `strict` into `__init__`...
violating the explicitly stated signatures") alongside the already-correct
FM-1.4 on the same span, and FM-1.5 ("Tester declares 'TASK COMPLETE' after
round 1 (turn 4) and round 2 (turn 7)... Planner must repeatedly correct").

**FM-1.5 accepted.** Turn 4: Tester closes Round 1 verification with "TASK
COMPLETE"; Planner replies (turn 4... actually the very next turn): "this
isn't the full task yet. The original scope included three more rounds."
Turn 7: Tester closes Round 2 verification with "TASK COMPLETE" again;
Planner: "again — this only completes round 2 of 3." A third, uncited
instance recurs at turn 11 (after the `strict`-mode round), this time caught
by Coder rather than Planner: "I don't think we should mark the overall task
complete — only the `strict` mode increment is done." The judge caught two
of the three instances and missed the third, but the underlying trace-level
call (FM-1.5 present) is correct regardless of how many of the individual
spans it found.

**FM-1.1 rejected.** The `strict` parameter signature the turn-21 rewrite
violates was established by *Planner mid-conversation* (turn 7: "Modify
`validate` to accept an optional parameter: `validate(self, email: str,
strict: bool = False)`"), not stated in the original task spec (which only
says "a `strict` mode... " with no literal signature). FM-1.1 requires
violating a constraint "stated in the prompt or task spec"; a signature
"agreed" mid-conversation and then silently reinvented after it scrolls out
of context is FM-1.4's own textbook positive example verbatim ("the coder
no longer 'remembers' the agreed function signature and invents a new,
incompatible one"). Scoring both modes on the same turn-21 span for the same
event double-counts one occurrence.

**FM-3.1 (already gold, judge missed it — a genuine recall gap).** The
trace's 24th and final turn (`max_round=24`) cuts off mid-sentence inside
Tester's verification of `suggest_correction` — case #1 (the flagship
`.con`→`.com` fix) is confirmed **FAIL** with the exact dead-code mechanism
traced, and the message is truncated mid-case-#5 ("It happens to give the
right answer here, but only because" — no closing). Required work is
confirmed left undone at the stopping point; gold's FM-3.1 call is correct,
the judge simply never fired it. Consistent with FM-3.1 being the judge's
weakest-recall mode across this whole project (also missed entirely in
batch 4).

## Headline finding, re-verified after adjudication

The `--strict-planner` hypothesis holds up after adjudication, unchanged in
its core shape: Planner-authored giant-early-turn fabrication genuinely
dropped from 5/5 (batch 4) to 0/5 on the 5 reruns, and FM-1.2 overall on
those reruns is now **3/5** (not 2/5 as pass-1 reported) after adding
`boundary-decision-relay`'s role-crossing — except `boundary-decision-relay`
is a *new* task, not one of the 5 reruns, so the rerun-specific figure is
unchanged at 2/5 (`stopping-criterion-recall-b5`,
`plan-then-diverge-b5`), still via Coder/Tester role-crossing rather than
Planner front-loading. `tempting-tangent`'s FM-1.4 regression (independent
of the strict-planner hypothesis) is unaffected by adjudication and remains
the batch's most interesting organic finding — now joined by a second,
smaller-scale organic finding (the repeated premature-"TASK COMPLETE"
pattern surfacing independently in two traces, `iterative-rebuild-summary-b5`
and `tempting-tangent`) that pass-1 missed on both occurrences.

## Score before vs. after

| | κ | 95% CI | precision | recall | n |
|---|---|---|---|---|---|
| naive (pass-1 gold, unadjudicated) | 0.40 | — | 0.33 | 0.71 | 112 |
| adjudicated | **0.65** | [0.43, 0.87] | 0.60 | 0.82 | 112 |

Per-mode (adjudicated, modes with any TP/FP/FN only):

| mode | tp | fp | fn | tn | precision | recall | κ |
|---|---|---|---|---|---|---|---|
| FM-1.1 | 0 | 2 | 0 | 6 | 0.00 | — | 0.00 |
| FM-1.2 | 3 | 0 | 0 | 5 | 1.00 | 1.00 | 1.00 |
| FM-1.3 | 0 | 1 | 0 | 7 | 0.00 | — | 0.00 |
| FM-1.4 | 1 | 0 | 0 | 7 | 1.00 | 1.00 | 1.00 |
| FM-1.5 | 2 | 0 | 0 | 6 | 1.00 | 1.00 | 1.00 |
| FM-2.1 | 1 | 0 | 0 | 7 | 1.00 | 1.00 | 1.00 |
| FM-3.1 | 0 | 0 | 1 | 7 | — | 0.00 | 0.00 |
| FM-3.2 | 2 | 3 | 0 | 3 | 0.40 | 1.00 | 0.33 |
| FM-3.3 | 0 | 0 | 1 | 7 | — | 0.00 | 0.00 |

Unlike prior batches, this one is not a story of pass-1 under-reading being
the whole explanation for the naive/adjudicated gap: of the 8 disputed
findings, the judge went **4 accepted (FM-1.5 ×2, FM-3.2 ×1 new accept,
FM-1.2 ×1) / 4 rejected (FM-1.1 ×2, FM-3.2 ×2)** — closer to a coin flip
than any batch so far. FM-3.2 remains the weakest mode by precision (0.40),
now for a *different* reason than batch 4: not one dominant false-execution
flavor being systematically missed, but the judge correctly generalizing
the "claims execution without showing reasoning" signal in one trace
(`repeated-utility-pattern-b5`, accepted) while over-applying superficially
similar "X pass against the implementation" phrasing in two others where
real reasoning was shown (`stale-correction-resurface-b5`,
`boundary-decision-relay`, both rejected) — a genuine precision problem on a
subtle distinction, not a recall gap. FM-3.1 stays at recall 0.00,
consistent with every prior batch's documented weak spot on that mode.
