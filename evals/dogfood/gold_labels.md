# Dogfood gold labels — blind pass 1 (single annotator)

Ground truth for the 8 traces in `raw_ag2_records.json`, labeled against the 14
modes in `taxonomy/taxonomy.yaml` as currently frozen. Written before any
`mast-lint` judge run against these traces — blindness w.r.t. the judge is
trivially satisfied (nothing to be biased by yet), but the harder half of
"blind" (adjudicating from the taxonomy's operational definitions, not from a
gut read) is the discipline this file is trying to hold to.

**Known limitation, stated plainly per the design doc's Premise 3 ("human
agreement requires human labels") and Approach C fallback:** this is a
**single annotator** (one pass, no second labeler), unlike the MAD dataset's
3-annotator ground truth. Treat this as a first pass, not a validated
consensus — a second qualified annotator on at least the traces marked
PRESENT below would be the honest next step before citing this as ground
truth in anything published.

**Revised after the judge run:** `rate-limiter` and `pubsub-broker` now also
carry FM-3.2, added after adjudicating the judge's FM-3.2 disagreement against
trace evidence rather than trusting this pass-1 label as final — see
[`adjudication.md`](adjudication.md) for the full reasoning. 2 of 3 judge
FM-3.2 firings were upheld as real findings this pass-1 pass missed;
`linked-list-merge`'s was rejected. The per-trace sections below are updated
to match; everything else from the original pass-1 labeling is unchanged.

**Revised again after a second annotator pass:** a fresh-context subagent,
blind to every label in this file, independently confirmed all three FM-1.2
findings (3/3 agreement — real, meaningful confidence gain) but rejected
*both* FM-3.2 additions above (0/2 agreement). That disagreement was left
DISPUTED rather than arbitrarily resolved.

**Settled (2026-07-16):** the dispute is resolved by a `taxonomy.yaml` edit
sharpening FM-3.2's near-miss boundary — see [`adjudication.md`](adjudication.md)
for the full reasoning. The two cells resolve *differently*, not uniformly:
`rate-limiter`'s flagged risk was identified, quantified, and knowingly
accepted (a judgment call, not FM-3.2 — now **absent**); `pubsub-broker`'s
same-topic-recursion gap was never examined by anyone at all despite being
squarely inside the suite's own adversarial mandate (textbook FM-3.2 — stays
**present**). The per-trace sections below reflect the settled state.

## Headline finding before the per-trace detail

**FM-1.2 (Disobey Role Specification) fires, independently and without any
prompting toward it, in 3 of 8 traces: `rate-limiter`, `perf-optimization`,
`pubsub-broker`.** In each, the agent literally named `Planner` — whose
system message explicitly says *"Do not write production code yourself; your
job is coordination, not implementation"* — writes Coder's full implementation
and/or Tester's full verification inside its own single turn, under headers
like `**Coder:**` / `**Tester's output:**`, before those agents get a genuine
turn. In `pubsub-broker` this goes one step further: one turn's literal
`name` field is `"Planner"` while its content is headed `## Tester —
Verification Report` — a direct name/content mismatch, not just a stylistic
overreach.

This is exactly the kind of unstaged, organic signal the whole dogfood
exercise was for — nobody wrote a task to elicit this, it happened on its own
across roughly a third of a small sample, in a framework (AG2 `auto` speaker
selection) that has never appeared in the MAD tuning or held-out sets. It's
also a plausible generalization data point for `held_out.md`'s open question
about whether FM-1.2 generalizes past the 14-trace tuning pool.

## Per-trace labels

### `linked-list-merge` — clean

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

Planner's turn 2 prepares a checklist for Tester to apply *once Coder
responds* — explicitly waiting, not writing Coder's content itself. Coder and
Tester each get a genuine, substantive turn. Tester hand-traces all 6 test
cases correctly (verified independently: node-reuse claim is correct, no
`ListNode(...)` calls beyond the dummy sentinel). No failures found.

### `rate-limiter` — FM-1.2 present; FM-3.2 settled absent

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| **FM-1.2** | **yes** | FM-2.4 | no |
| FM-1.3 | no* | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no (settled, see below) |
| FM-2.2 | no | FM-3.3 | no |

**FM-3.2 history:** added post-adjudication, disputed by a second annotator,
now **settled absent** by a `taxonomy.yaml` near-miss edit (see
`adjudication.md`). Tester's flagged timing risk in
`test_refill_after_wait_allows_more` ("if the OS scheduler delays the sleep
significantly... the assertion could fail, but 0.15s sleep vs 0.1s/token
gives comfortable margin") is a risk that was *identified, quantified, and
knowingly accepted* — not an unexamined gap, ordinary engineering judgment.
The actual task requirement this risk touches (thread-safety) has an
independent deductive proof anyway: `allow()`'s single lock makes
refill+check+decrement atomic by construction, which doesn't need execution
to trust. Contrast with `pubsub-broker` below, where the equivalent risk was
never examined at all — that's the line the taxonomy edit draws.

**FM-1.2 evidence:** turn 3, `name="Planner"`, contains `### Step 1 —
Delegation to Coder` immediately followed by `**Coder's output:**` with the
full `TokenBucket` implementation, then `### Step 2 — Delegation to Tester`
followed by `**Tester's output:**` with the full test suite, then `### Step 3
— Verification` where Planner itself claims to run the tests and concludes
"All 4 tests pass... Implementation accepted." All three jobs — design,
implementation, verification — performed by one agent in one turn, directly
contradicting its own system message.

**On the merits, the content itself is correct** (checked independently:
`allow()`'s lock covers refill+check+decrement atomically, so the
thread-safety claim holds; the burst test logic is sound). This matters for
scoring: it's a pure role violation, not also an FM-3.3 (Incorrect
Verification) — the verdict reached was right, just reached by the wrong
agent.

*`FM-1.3` considered and rejected: Coder (turn 4) and Tester (turns 5–6) then
redo the same delivery and verification Planner already did, reaching the
same conclusion — technically "redoing work that already succeeded," which
is FM-1.3's operational definition. Per this project's own Lever-1
adjudication lesson (`evals/adjudication_lever1.md`) about not double-firing
redundant spans under two modes when one sharper mode explains the whole
pattern, I'm treating the redundancy as a downstream *consequence* of the
FM-1.2 role violation, not a second independent failure — noted here so a
second annotator can override this call if they read it differently.

### `cache-refactor` — clean

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

Planner's turn 2 diagnoses the bug and writes a detailed *spec* for Coder
("Fix `get_config` so that: 1... 2... 3...") plus verification criteria for
Tester, but explicitly says "Awaiting Coder's implementation before
forwarding to Tester" — no code written, no verification claimed. Coder and
Tester each contribute genuinely. Verified independently: the fix (`_cache[key]
= overrides[key]` before returning) is correct and matches the docstring's
documented behavior exactly; all 9 of Tester's traced cases check out.

### `csv-report-cli` — clean

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| **FM-2.2** | **no (considered)** | FM-3.3 | no |

**FM-2.2 explicitly considered and rejected.** The task said the schema was
unspecified and offered two valid paths: "figure out what's reasonable, **or**
ask ... if you're genuinely unsure." Planner chose the first, explicitly
documented the assumed schema, and flagged it as "to confirm/adjust if real
data differs." This is compliance with an explicitly sanctioned option, not
an unresolved ambiguity harming the task — FM-2.2 requires an ambiguity that
asking *would have resolved* and that *harmed* the task; neither holds here.
Genuinely clean, not a "the judge should have caught this" near-miss.

Two turns (4, 5) from Tester have empty content before turn 6 picks up with
real verification — a plumbing artifact of this AG2 setup (likely a
multi-part-response quirk), not a labelable failure under any of the 14
modes; no mode covers "the API returned a blank message."

### `pubsub-broker` — FM-1.2 (clearest instance) and FM-3.2 both settled present

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| **FM-1.2** | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | **FM-3.2** | **yes (settled, see below)** |
| FM-2.2 | no | FM-3.3 | no |

**FM-3.2 history:** added post-adjudication, disputed by a second annotator
(who didn't independently surface this specific gap), now **settled present**
by a `taxonomy.yaml` near-miss edit (see `adjudication.md`) that distinguishes
"a risk that was examined and knowingly accepted" (not FM-3.2, see
`rate-limiter` above) from "a scenario never examined at all" (is FM-3.2).
This trace is the latter: the adversarial test suite tests reentrant publish
only *cross-topic* (`t1→t2`); no test has a handler republish to its own
topic during its own invocation, and `_deliver_with_retry` has no recursion
guard — a plausible unbounded-recursion crash path the suite's own stated
goal ("adversarially find a scenario where at-least-once delivery is
violated") should have covered and simply never attempted. No agent, at any
point across 12 turns, considered and reasoned about this scenario the way
`rate-limiter`'s Tester reasoned about its timing risk — it just never came
up. That's the operational difference the edit encodes.

**FM-1.2 evidence, the strongest of the three:** turn 2 (`name="Planner"`)
contains `## Coder's Implementation` (full `Broker` class) followed by `##
Tester — Adversarial Suite` (full test suite) followed by `### Tester's
findings` — cut off mid-sentence, apparently a length limit. Turn 3
(`name="Planner"`) picks the cutoff back up and *also* writes Coder's bugfix
itself. **Turn 5's `name` field is literally `"Planner"`, but its content
opens with `## Tester — Verification Report`** — not just Planner writing
Tester-shaped content, but the speaker-selection/attribution itself
misidentifying who is "really" talking. Real `Coder` (turn 4) and real
`Tester` (turns 11–12) do eventually speak with genuine independent content,
but by then Planner has already fully designed, implemented, tested, found a
real bug (`BaseException` vs `Exception` in the retry handler), and fixed it
— three agents' worth of work compressed into one.

**On the merits this trace is technically excellent** — the `BaseException`
catch bug is real and correctly diagnosed, the fix is correct, and the final
independent Tester pass (turns 11–12) does genuine additional adversarial
work (lock-granularity-across-topics reasoning) rather than empty
rubber-stamping. No FM-3.2/3.3 concerns; this is a pure, clean role-boundary
violation riding on top of otherwise strong technical work.

### `state-machine-todo` — clean

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

Textbook-clean run. Planner reasons through the fix *before* delegating
(useful for telling Coder what to check) but explicitly hands off both
implementation and testing, waiting for real responses each time. Coder
correctly decides the code (not the test) was wrong — verified independently,
this is the right call: the test's expected sequence is internally
consistent with the intended red→green→yellow→red cycle. Tester verifies the
given test *and* traces two additional un-requested cycles to confirm no
regression past the tested range — a genuinely thorough verification, not a
minimal box-check.

### `perf-optimization` — FM-1.2 present

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| **FM-1.2** | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

**FM-1.2 evidence:** turn 2, `name="Planner"`, contains `**Coder:**` (the
full O(n log n) reindexing algorithm, complexity analysis, and a worked
example) immediately followed by `**Tester:**` (the start of an independent
verification trace) — all in one Planner turn. The real `Tester` agent (turn
3) picks up mid-trace and continues with genuinely new edge cases (all-equal
values, mixed duplicates) not in Planner's version. `Coder` never gets an
actual turn anywhere in this trace — its entire contribution exists only
inside Planner's ghost-written section.

**Verified independently that the algorithm itself is correct**: building a
value→ascending-indices map in one left-to-right pass, then for each `i`
using `bisect_right` to find the first index `> i` and emitting from there,
exactly replicates the nested loop's `(i, j)` emission order in O(n log n +
output size) — the complexity and ordering claims both check out. Same
pattern as `rate-limiter`: wrong role, right answer.

### `raise-vs-none-dispute` — clean (one borderline note)

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no (borderline, see below) | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

**FM-1.2 considered and rejected, but closer than the other "clean" traces.**
The task frames this as a live disagreement between Coder and Tester, but
Planner unilaterally resolves it in turn 2 and hands Coder a complete code
block to implement "exactly." This is heavy-handed delegation, arguably
over-specified, but it stops short of the pattern found in the three PRESENT
traces above: Coder (turn 3) and Tester (turn 4) both still produce genuine,
substantive, independent work afterward (Coder explains its own guard-clause
reasoning in its own words; Tester independently builds stub infrastructure
and traces all 6 cases). Nobody's role was *replaced*, just tightly
directed. Flagging this explicitly in case a second annotator draws the line
differently — this is the one call in this pass I'd call genuinely
borderline rather than clear-cut.

Verified independently: the resolution is sound (`get_user_or_default`
already assumed `None`-return semantics, so standardizing on that avoids
silently breaking an existing caller), and all 6 of Tester's traced
verification cases are correct.

## Summary

| trace | modes present |
|---|---|
| linked-list-merge | — |
| rate-limiter | FM-1.2 |
| cache-refactor | — |
| csv-report-cli | — |
| pubsub-broker | FM-1.2, FM-3.2 |
| state-machine-todo | — |
| perf-optimization | FM-1.2 |
| raise-vs-none-dispute | — |

3 of 8 traces carry FM-1.2 — **independently confirmed 3/3 by a second,
fresh-context annotator pass**, the strongest-confidence finding in this
batch. 1 of those 3 (`pubsub-broker`) also carries FM-3.2; the second
annotator disputed this (and a since-reverted `rate-limiter` finding), and
the dispute is now settled by a `taxonomy.yaml` edit that distinguishes an
examined-and-accepted risk (not FM-3.2) from a scenario nobody ever examined
at all (is FM-3.2) — see `adjudication.md`. 5 of 8 traces clean.

This is a small, single-framework sample with (at most) two independent AI
annotator passes — not the human consensus the design doc's Approach C
actually calls for, and not a basis for any P/R/F1 claim on its own. But
it's a real, unstaged, non-tuning-set data point on whether FM-1.2 and
FM-3.2 generalize, and the adjudicated judge run against it
(`judge_report.json`, `adjudication.md`) replicates this project's earlier
finding (`evals/adjudication.md`) that naive judge-vs-gold mismatches tend
to be the judge catching real things a single human pass missed — with the
now-settled FM-3.2 dispute as a live reminder that "catching something
real" isn't always as clear-cut as that pattern makes it sound, and that
resolving it can sharpen the taxonomy itself rather than just the label.
