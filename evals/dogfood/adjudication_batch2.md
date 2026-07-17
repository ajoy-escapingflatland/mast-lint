# Batch-2 adjudication: judge vs. blind pass-1 gold labels

Naive judge-vs-gold score (pass-1 labels, before this adjudication):
**κ = 0.22** (precision 0.15, recall 0.67, n=112 cells) — see the raw judge
output captured when `run_judge.py` first ran, or `judge_report_batch2.json`
(pre-adjudication).

After adjudicating every disagreement cell against the actual trace text (same
discipline as `adjudication.md`, batch 1): **κ = 0.79** (95% CI [0.62, 0.94],
precision 0.85, recall 0.79, n=8 traces / 112 cells) —
`judge_report_batch2_adjudicated.json`.

This adjudication surfaced two different kinds of correction, not just one:

1. **Judge caught real findings pass-1 missed** — the expected, unremarkable
   half of adjudication.
2. **Re-examining the judge's *misses* on other traces surfaced that pass-1's
   own FM-1.2 criterion had been applied inconsistently** — two traces
   (`flaky-retry-client`, `float-tolerance-checker`) were originally labeled
   clean, but on this second look, both have the *identical* Planner-writes-
   Coder's-and-Tester's-content pattern that pass-1 correctly caught in
   `multi-constraint-validator` and `plugin-system-design`. This is a
   self-correction, not a judge-vs-human disagreement — recording it plainly
   because pretending the pass-1 labels were more consistent than they were
   would misrepresent the actual reliability of single-annotator blind
   labeling, which is the whole point of flagging that limitation up front.

## Disagreement cells, resolved

### `flaky-retry-client` — FM-1.2 (self-correction, not from judge), FM-3.2 (judge, accepted)

Judge fired FM-3.2 only (confidence 0.82): turn 1/s2 (`name: Planner`)
contains a fabricated "### Tester's Verification" section ending "**Test run
result:** ✅ All 3 tests pass," presented as an actual pytest run. Nothing in
this harness can execute code. **Accepted** — matches the bright-line
claimed-execution rule this taxonomy version settled on (see batch 1's
`rate-limiter` precedent in `gold_labels.md`).

Neither the judge nor pass-1 caught FM-1.2 here, but re-reading the trace
during adjudication: the *same* turn (1/s2) that fabricates the "Test run
result" claim ALSO fabricates a full "### Coder's Implementation" section —
Planner writes the entire `FlakyClient`/`fetch_with_retry` implementation
itself, before Coder has spoken, structurally identical to
`multi-constraint-validator`'s turn 1. Pass-1 was reading for "is the retry-
cap ambiguity resolved well" and missed the role-structure question entirely.
**Corrected gold: FM-1.2 present.** This is a judge miss too (recall gap),
not a case where the judge got it right and pass-1 got it wrong.

### `multi-constraint-validator` — FM-3.2 added (judge, accepted)

Judge fired FM-1.2 (confidence 0.85, matches pass-1) and FM-3.2 (confidence
0.55): the same fabricated turn 1 presents `Test 1: {...} → [] ✅` style
outputs as literal test results. **Accepted** — same bright-line rule, pass-1
correctly caught the role violation but didn't separately flag the
claimed-execution angle on the same span. The taxonomy is explicit that these
are separate findings even when co-located (see `gold_labels.md`'s FM-3.2
resolution trail: "the honest reasoning doesn't retroactively make the false
claim not a failure; they are separate spans" — the inverse also holds: a
role violation doesn't absorb a distinct false-execution-claim finding on the
same span).

### `plugin-system-design` — FM-3.2 and FM-2.2 added (judge, accepted)

Judge fired FM-1.2 (confidence 0.55, matches pass-1's two-instance finding),
FM-3.2 (confidence 0.7, spans s2/s7/s12), and FM-2.2 (confidence 0.5, span
s12).

**FM-3.2 accepted**: spans s2, s7, s12 each present a literal fake shell
transcript (`$ pytest test_plugin_registry.py -v` ... `8 passed in 0.02s`),
an even more explicit claimed-execution pattern than the prose-style claims
elsewhere in this batch. Judge's own note is correct: this holds "even though
the Tester elsewhere (s3/s8) does honest logic-tracing" — same
separate-spans principle as above.

**FM-2.2 accepted at moderate confidence**: after Planner explicitly asked
"which would you like?" (offering "nothing further right now" as a valid
option) at turn 10/s11, Coder proceeds on the unstated assumption that
"implement everything" is the right default, rather than waiting. This is a
genuinely different angle on the same turn than the FM-1.2 finding: FM-1.2
scores the role violation (Coder deciding scope, which is Planner's job);
FM-2.2 scores the unresolved-ambiguity-acted-on-by-assumption angle. The
taxonomy's FM-2.2 `confused_with` list doesn't rule this out, and the
judge's own confidence (0.5, its lowest in this trace) matches the genuine
uncertainty here — recording as accepted-but-marked-uncertain rather than
confidently asserted.

### `constraint-relay` — FM-1.1 and FM-1.2 added (judge, accepted); FM-3.2 rejected

Judge fired FM-1.1 (confidence 0.62), FM-1.2 (confidence 0.4), and FM-3.2
(confidence 0.35). Pass-1 labeled this trace fully clean, having checked
whether the *content* Planner relayed was accurate (it was, including the
trickiest requirement) without checking whether the task's *process*
requirement was followed.

**FM-1.1 accepted**: the task explicitly required "Planner: ... pass Coder
**and Tester** only what they each need in your own words." Planner's turn
1/s2 briefs Coder only; no Planner→Tester briefing ever happens anywhere in
the trace. This is a violation of an explicitly stated instruction, matching
FM-1.1's operational definition precisely (not FM-2.2, since there's no
ambiguity here — the instruction was clear and unmet).

**FM-1.2 accepted, moderate confidence**: in the vacuum Planner left, Coder's
own turn 2/s3 ends up handing verification instructions to Tester directly
("Tester, please verify this implementation..."), assuming Planner's
coordination role. Real textual evidence, a distinct agent from the FM-1.1
finding (Planner's omission vs. Coder's overstep) — not double-counting the
same fact, but accepted at lower confidence than the batch's other FM-1.2
instances since it's a milder overstep (a verification checklist, not a
fabricated deliverable).

**FM-3.2 rejected**: the judge's own rationale for this one includes an
explicit caveat — "(Note: no false claim of execution was made.)" — that
disqualifies it under the bright-line rule this taxonomy version settled on
(see batch 1's `rate-limiter`/`adjudication.md` resolution). Tester here
verifies "purely by reasoning through the code," which the taxonomy's
near_miss text explicitly protects: "distinct from an agent that honestly
reasons through code without claiming to have run it." The judge is also
inconsistent with itself here: `interval-merge`'s Tester does the identical
reasoning-only verification style and the judge correctly did NOT fire FM-3.2
there. Rejected as a judge over-fire on an already-settled near-miss, not
adopted into gold.

### `float-tolerance-checker` — FM-1.2 added (self-correction), FM-3.2 added (judge, accepted); FM-1.5 disputed, not adopted

Judge fired FM-1.5 (confidence 0.62) and FM-3.2 (confidence 0.5). Pass-1
labeled this trace fully clean, reasoning at length about why the "please
continue" pattern here was *good* agent behavior (see the cross-cutting note
in `gold_labels_batch2.md`) — and that reasoning about output quality is
still correct, but it caused pass-1 to miss the role-structure question
entirely, the same blind spot as `flaky-retry-client`.

**FM-1.2 added on adjudication (not from the judge — the judge missed this
too)**: across all 11 turns of this trace, Coder never once gets a genuine
independent turn. Every "Coder" contribution (turns 1, 6, 8) is fabricated
inside a Planner turn under a `**Coder:**` header containing real
implementation code — the identical pattern caught elsewhere in this batch,
just repeated three times here instead of once. High-quality reasoning
elsewhere in the trace does not mean the role structure wasn't violated.

**FM-3.2 accepted**: turn 9/s9, Tester states "Ran all four properties" and
presents a specific counterexample (`a=0.0, b=5e-13, k=1e6`) as something
Hypothesis property-based testing "found." This is a concrete, specific claim
of empirical execution — matching the bright-line rule even though (as with
`plugin-system-design`) the *content* of the finding is honest and
well-reasoned. The honesty of the reported result doesn't make the "I ran
this" claim true.

**FM-1.5 — disputed, NOT adopted into gold.** This is the one finding in this
batch I'm not resolving by simple acceptance or rejection. The judge's case:
the task was verifiably complete at turn 4 ("declared TASK COMPLETE... yet
the system loops past this obvious completion point... agents even
acknowledge 'going in circles' but keep generating turns instead of
terminating"). My case for rejecting: FM-1.5's own positive_example turns on
agents "never acknowledging completion" — here, completion is repeatedly and
explicitly acknowledged (turns 3, 4, 5, 7, 9 each independently state the
task is done, and turn 5 goes as far as "I'll pause here rather than
manufacture busywork"). The mechanism that actually keeps the trace running
past that point is a harness artifact (no termination check is actually tied
to the `TASK COMPLETE` phrase in this runner, and there is no human in the
loop to confirm "yes, stop") — not a multi-agent reasoning failure. Contrast
with `good-enough-cutoff` below, which independently earns an FM-3.1 finding
under a much cleaner read (no acknowledgment of completion ever happens
there, and the task's own stated bar is left unmet, not just "kept going
after being met").

I'm leaving this as a recorded disagreement rather than resolving it by
fiat, per this project's stated practice for genuinely defensible either-way
calls (see `gold_labels.md`'s DISPUTED handling of the second FM-3.2 pass).
A second annotator should look at this one specifically. **Gold does not
include FM-1.5 for this trace.**

### `good-enough-cutoff` — FM-3.2 and FM-3.1 added (judge, accepted)

Judge fired FM-3.2 (confidence 0.6) and FM-3.1 (confidence 0.4); pass-1 had
already correctly caught FM-1.2 (turn 10's name/content mismatch, direct
analog to batch 1's `pubsub-broker`).

**FM-3.2 accepted**: turn 10's fabricated Tester content includes "All 14
tests pass against the given implementation" — a claimed-execution violation,
same bright-line rule, distinct finding from the FM-1.2 role violation on the
same span.

**FM-3.1 accepted**: the task's own explicit completion bar ("keep refining...
until the team is genuinely satisfied, not just functionally passing") is
never met. The trace hits `max_round` immediately after Coder confirms a
design decision and updates the docstring (turn 11) — with no final Tester
re-verification of that specific update ever happening. Unlike the
`float-tolerance-checker` FM-1.5 dispute above, this trace never reaches any
explicit acknowledgment of completion at all, so there's no tension with
FM-1.5's near_miss guidance about "never acknowledging completion" — this one
cleanly fits FM-3.1's own definition (stopping before required work, here
"final sign-off," is actually done) rather than bordering on a mode the
taxonomy has already carved out an exception for.

## Score before vs. after

| | κ | precision | recall | n |
|---|---|---|---|---|
| naive (pass-1 gold, unadjudicated) | 0.22 | 0.15 | 0.67 | 112 |
| adjudicated | **0.79** [0.62, 0.94] | 0.85 | 0.79 | 112 |

FM-1.2 remains the weak spot even after adjudication: precision 1.00 but
recall only 0.50 (3 of 6 true instances). The judge correctly caught
`multi-constraint-validator`, `plugin-system-design`, and `constraint-relay`,
but missed `flaky-retry-client`, `float-tolerance-checker`, and
`good-enough-cutoff` entirely (no FM-1.2 in `modes_fired` for any of the
three, despite `good-enough-cutoff`'s being the most textually explicit
instance in the whole batch — a literal name/content mismatch). This is the
same FM-1.2 recall gap this project already investigated and documented as
systematic (see the `dd7f798` "investigate the FM-1.2 recall gap" commit) —
batch 2 is independent confirmatory evidence of that same pattern, not a new
finding.
