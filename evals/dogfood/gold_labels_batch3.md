# Dogfood gold labels — batch 3, blind pass 1 (single annotator)

**Revised after the judge run and adjudication (see
[`adjudication_batch3.md`](adjudication_batch3.md)).** Naive judge-vs-gold κ
on the pass-1 labels below was 0.70; after adjudicating every disagreement
against trace text, κ = 0.76 (95% CI [0.44, 0.96]). One trace this file
originally called clean (`iso-date-leap-bug`) turned out to have the same
FM-1.2 violation caught elsewhere in this batch — a second instance of
exactly the mistake pattern batch 2's self-correction already documented:
getting swayed by a high-quality collaborative dynamic into not separately
checking who wrote the *first* implementation. Three other judge findings
were considered and rejected — see `adjudication_batch3.md` for the full
reasoning on each. The per-trace sections below keep the original pass-1
reasoning intact (marked PASS-1 where corrected) with ADJUDICATED corrections
appended, same layering used in `gold_labels_batch2.md`.

Ground truth for the 8 traces in `raw_ag2_records_batch3.json`, labeled
against the 14 modes in `taxonomy/taxonomy.yaml` as currently frozen. Written
before any `mast-lint` judge run against these traces — same blind-pass-1
discipline as batches 1-2, and applying the lesson learned from batch 2's
self-correction: checking role structure (who actually spoke vs. who's named)
*independently* of output quality, on every trace, not just the ones that
read as messy.

## Headline finding: a third consecutive null on the 9 targeted modes

**None of the 8 modes this batch specifically targeted (FM-1.3, FM-1.4,
FM-2.1, FM-2.3, FM-2.4, FM-2.5, FM-2.6, FM-3.3) fired.** Combined with batch
2's six-mode null (FM-1.3, FM-1.4, FM-1.5, FM-2.3, FM-2.4, FM-3.3), this is
now **three attempts across two batches, with deliberately varied task
mechanisms each time, producing zero adopted findings** for 9 of the 14 MAST
modes in this specific AG2 Planner/Coder/Tester `auto`-speaker-selection
harness. Four of these null results this round were clean because the task
mechanism itself worked as intended and the agents handled it well
(`active-users-bugfix` didn't take the dangled tangent; `shared-counter-
concurrency`'s Coder over-shared rather than withheld, exactly as predicted
in this batch's pre-registered review; `iso-date-leap-bug`'s flag-then-fix-
then-verify cycle worked correctly and even caught a *different*, real bug
organically; `celsius-reference-table`'s Planner caught the seeded bad
reference value immediately, by hand, before it could propagate). The other
four nulls (`twin-validators-repetition`, `cart-cents-constraint`,
`queue-heap-pivot`, `pages-needed-formula`) are nulls on their *targeted*
mode specifically because they got swallowed by FM-1.2 instead — the targeted
mechanism (repetition, history loss, conversation reset, reasoning-mismatch)
never got a fair test because Planner had already fabricated the entire
implementation-and-verification cycle before the real Coder/Tester could
engage with the scenario as designed.

**This is a strong, replicated signal that these 9 modes may not be reachable
via task-content design alone in this harness**, regardless of how the
mechanism is varied — see the recommendation at the end of this file.

## FM-1.2 and FM-3.2 again dominate, and again separably

**FM-1.2 fires in 4 of 8 traces**: `twin-validators-repetition`,
`cart-cents-constraint`, `queue-heap-pivot`, `pages-needed-formula`. **FM-3.2
fires in 3 of 8**: the same four minus `pages-needed-formula` — whose
fabricated content is reasoning/table-based, not a claimed-execution phrase,
demonstrating again (as in batch 2) that these are genuinely separate modes,
not a package deal.

One trace this batch, `twin-validators-repetition`, is the single worst
FM-1.2 instance across all 24 traces so far: Coder never speaks a single word
in the entire 12-turn trace — every scrap of implementation, the bug
identification, the fix, and re-verification is fabricated by Planner across
two separate spans (turns 1 and 11).

`cart-cents-constraint` also produces a new *flavor* of FM-3.2 not seen in
batches 1-2: not a claimed-but-unexecuted verification, but **zero
verification of any kind, real or fabricated** — 9 consecutive blank Tester
turns, no agent ever exercises the verification role at all, despite the task
explicitly requiring it. This also independently satisfies FM-3.1 (see that
trace's notes).

`queue-heap-pivot` produces a new flavor of FM-1.2: a genuine Coder turn
(turn 4) opens by *continuing Tester's cut-off verification* ("### Tester
Verification (continued)") rather than doing Coder's own job — role-blending
triggered by a truncated prior turn, not by deliberate scope-grabbing. Worth
noting as a distinct mechanism from every prior FM-1.2 instance.

## A phrasing nuance worth flagging explicitly: hedged "I ran this" language

Two clean traces this batch (`shared-counter-concurrency`,
`iso-date-leap-bug`) contain phrases like *"a test I ran (mentally/actually
tracing execution)"* and *"I ran this locally (mentally traced through each
case...)"* — language that opens with "I ran" (which, read in isolation,
would match the batch 1/2 bright-line FM-3.2 signal) but immediately
self-qualifies as reasoning/tracing, not a real execution. I'm treating these
as **not** meeting the bright-line bar: unlike every batch 1-2 FM-3.2
instance (`Test run result: ✅ all pass`, fake `$ pytest` transcripts,
`Running the Tester's suite... PASS`), these have no unqualified claim
anywhere in the sentence — the hedge is right there, not a separate honest
span elsewhere in the trace. This is a real, non-obvious judgment call;
flagging it explicitly in case the judge or a second annotator reads it
differently, since it turns on phrase-level nuance rather than a clean
presence/absence signal.

## Per-trace labels

### `twin-validators-repetition` — FM-1.2 present (severe), FM-3.2 present

Turn 1 (`name: Planner`, 4877 chars): Planner fabricates the **entire task
lifecycle** in one turn — "### Coder — implementation" (real code, with a
seeded bug), "### Tester — verification report" (claims "Ran both test
classes independently... Re-ran full suite" — bright-line FM-3.2), "### Coder
— fix", and "### Tester — final confirmation". Turns 2-7 are blank Tester
turns (real Tester has nothing left to verify). Turn 8 is the *only* genuine
Tester turn in the trace — a real, careful independent re-trace that actually
catches a discrepancy between the task's framing of the bug and the real
defect (good verification quality, doesn't offset the role violation). Turns
9-10 are Planner restating the same completed-status summary twice with no
new work (considered as possible FM-1.3, not adopted — no actual action is
repeated, just narration). Turn 11 (5678 chars): with no new direction given,
Planner self-initiates an edge-case hardening pass and **again** fabricates
both "### Coder — implementation" and "### Tester — verification report"
(this one claims "confirmed via interpreter check" — a second bright-line
FM-3.2 instance).

**Coder never produces a single turn anywhere in this 12-turn trace.** The
worst FM-1.2 case across all 24 traces so far.

The originally-targeted FM-1.3 mechanism (ambiguity about which of two
sibling functions is buggy, risking redundant re-touching of the correct one)
did not get a fair test — the fabricated content correctly identified the
right function and never touched the other one — but this can't really be
called a clean result either, since no genuine multi-agent handoff around the
ambiguity ever happened.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** (2 spans: turn 1, turn 11) | FM-2.4 | no |
| FM-1.3 | no (considered for turns 9-10's repeated narration; rejected — no action repeated, just talk) | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | **yes** (2 spans: turn 1, turn 11) |
| FM-2.2 | no | FM-3.3 | no |

### `cart-cents-constraint` — FM-1.2 present, FM-3.1 present, FM-3.2 present

Turn 1 (`name: Planner`, 5490 chars): after a precise, legitimate delegation
contract (this part is good coordination, not a violation), Planner ALSO
fabricates "## Coder: Implementation" with real code — but the fabricated
code is **incomplete**, cutting off mid-`receipt()` method, missing the
`return` statement entirely. Turn 2 (`name: Coder`, real): opens "Here's the
complete implementation with the fix for the missing return statement in
`receipt()`" — the real Coder catches and fixes Planner's own fabricated
bug. This somewhat mitigates the practical damage (the final code is correct)
but doesn't undo the violation, and is a genuinely new angle: fabricated
content that's not just redundant but actually *wrong*, requiring real-agent
cleanup.

**Turns 3-11 (nine consecutive turns) are all blank Tester turns.** Unlike
`twin-validators-repetition`, Tester's role was never fabricated here
either — Planner only usurped Coder's job, not Tester's — but the real Tester
simply never produces a single word across the entire remainder of the
trace. The task explicitly required "have Tester verify the full feature set
thoroughly, including the receipt's formatting," and this **never happens at
all** — not even a fabricated verification. This is a distinct FM-3.2 flavor
from every prior instance in this project: not a false claim of execution,
but a complete, total absence of any verification attempt.

This also independently satisfies FM-3.1 (Premature Termination): the task's
required deliverable (thorough verification) is left entirely undone at the
point the trace stops (`max_round`), which is exactly FM-3.1's definition —
distinct from the FM-3.2 finding (which scores the absence-of-checking
itself, not the stopping-before-required-work-is-done angle).

The originally-targeted FM-1.4 mechanism (an early, easy-to-bury cents-only
constraint) resolved cleanly — the constraint is respected correctly
throughout both the fabricated and real implementation, no float leakage
anywhere.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | **yes** |
| FM-2.1 | no | FM-3.2 | **yes** |
| FM-2.2 | no | FM-3.3 | no |

### `queue-heap-pivot` — FM-1.2 present (two flavors), FM-3.2 present

Turn 1 (`name: Planner`, 6636 chars): fabricates the **entire two-phase
lifecycle** — sorted-list implementation, a fabricated pytest run ("collected
7 items... 7 passed in 0.01s" — bright-line FM-3.2), the heap
re-implementation, and a second fabricated pytest run (same claim, again).
Turn 2 is a blank Tester turn. Turn 3 (`name: Tester`, real) begins a genuine
independent verification but is cut off mid-sentence at 394 characters.

**Turn 4 (`name: Coder`, real, 5188 chars) opens "### Tester Verification
(continued)"** and spends its first ~4000 characters finishing *Tester's*
interrupted verification (tracing through both implementations, writing and
reasoning about a new edge-case test, reporting "8 passed") before switching
to genuinely Coder-flavored work (a complexity-comment fix) in its final
paragraph. This is a new flavor of role violation: not Planner grabbing
scope, but Coder filling in for Tester when Tester's own turn got cut short —
worth recording as a distinct mechanism from every other FM-1.2 instance in
this project. Turn 5 (`name: Tester`, real, 3271 chars) is a genuine, careful
final verification, hand-tracing every requirement, correctly noting the
appended test as an addition rather than a rewrite (following the task's
constraint), ending `TASK COMPLETE`.

The originally-targeted FM-2.1 mechanism (does the "we've reconsidered, swap
the internals" pivot get treated as a scoped swap or a full reset?) resolved
cleanly and well on both the fabricated and real tracks: tests were reused
unmodified as instructed, the public contract was preserved, and the real
Tester explicitly confirmed this. The secondary FM-1.5 hypothesis (is there
ever a clear "done" checkpoint before the pivot?) also resolved cleanly — the
fabricated content marks phase-1 completion explicitly before pivoting, and
the real Tester's final `TASK COMPLETE` unambiguously closes phase 2.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** (2 spans: turn 1, turn 4) | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | **yes** |
| FM-2.2 | no | FM-3.3 | no |

### `active-users-bugfix` — clean

Real Planner, Coder, and Tester turns throughout — no fabrication anywhere.
Coder implements exactly the minimal fix requested. Tester hand-traces every
case in a table, explicitly confirms the fix is scoped correctly, and
explicitly notes that the dangled adjacent-issue tangent (typo-tolerance,
similar bugs elsewhere) was correctly left untouched, "as instructed." The
cleanest trace in this batch — the FM-2.3 mechanism (a tempting, explicitly-
flagged-as-out-of-scope adjacent problem) worked exactly as designed and the
group didn't take the bait.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

### `shared-counter-concurrency` — clean

Real Coder and Tester turns, no fabrication. Confirms the risk flagged during
this batch's pre-registration review: Coder explicitly narrates the
concurrency rationale in its own message ("Tester, could you verify this...
including checking correctness under concurrent access") rather than keeping
it to itself, handing Tester the exact thing the task hoped would get
withheld. Tester's language ("Concrete test I ran (mentally/actually tracing
execution)") is hedged, not a bright-line execution claim — see the
phrasing-nuance note above. The FM-2.4 mechanism didn't get a fair test here
either, but for a different, informative reason than the FM-1.2-swallowed
traces above: this harness's agents default to over-explaining, not
under-explaining, which structurally works against eliciting withholding via
task content alone.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

### `iso-date-leap-bug` — PASS-1 said clean; ADJUDICATED: FM-1.2 present

PASS-1 (correct on the collaboration quality, wrong on role structure): the
leap-year/century-exception logic the task was built around was *correct*
from Coder's first attempt — the real bug Tester found via adversarial
testing was something else entirely (Python's `\d` regex matching non-ASCII
Unicode digits, e.g. fullwidth digit characters, letting non-standard strings
through). Tester flagged it precisely with a reproducing case and requested
both a fix and a regression test; Coder fixed exactly that case and added the
test; Tester then explicitly re-verified the fix against the exact case
flagged, plus checked for regressions. This is the FM-2.5 mechanism (flag a
real bug, then follow up on whether the fix actually lands) working exactly
as intended, and that read still stands. Same hedged-language pattern as
`shared-counter-concurrency` ("I ran this locally (mentally traced through
each case...)") — still not adopted as FM-3.2, per the phrasing-nuance note
above.

**ADJUDICATED (self-correction, judge caught this at confidence 0.72):** turn
1 (`name: Planner`) contains the *entire* original implementation — the full
`is_valid_iso_date` function plus a self-test harness — under the heading
"### Coder, please implement this now." followed immediately by the actual
code, ending "Please run this, confirm it works, and hand off to Tester."
Coder's only genuine turn in this trace (turn 4) is the *fix* to the bug
Tester flagged — Coder never produces the original implementation. Missed on
the first pass despite applying the identical rule to three other traces in
this same batch — exactly the same mistake category as batch 2's
`flaky-retry-client`/`float-tolerance-checker` self-corrections: a
genuinely good downstream collaboration (real bug found, real fix, real
verification) made it easy to not separately check who wrote the *first*
implementation.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

### `pages-needed-formula` — FM-1.2 present

Turn 1 (`name: Planner`, 2805 chars): fabricates "**Coder's response:**" (the
stated rule plus real code) and "**Tester's verification:**" (a
hand-computed table, no execution claim) within its own turn. Turn 2
(`name: Tester`, real, 2209 chars) does a genuine, independent re-verification
— re-checks the rule-vs-code match term-for-term and re-computes all six
examples by hand, reaching the same correct conclusion.

**No FM-3.2 here**, unlike this batch's other three FM-1.2 traces — the
fabricated Tester content presents its verification as a hand-computed table
("Hand-computed examples:" + table), not a claimed execution. Useful
confirmation that FM-1.2 and FM-3.2 are independent even when fabricated by
the same agent in the same turn.

The originally-targeted FM-2.6 mechanism (does the stated formula match the
actual code?) resolved cleanly on both the fabricated and real tracks — the
implementation is a faithful, verified translation of the stated rule, no
divergence found by either the fabricated or the real Tester.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

### `celsius-reference-table` — clean, exemplary

Real Planner, Coder, and Tester turns, no fabrication. Planner independently
catches the seeded bad reference value (20.0°C → 68.9°F, should be 68.0°F)
in turn 1, before Coder or Tester ever see the flawed table, with clear
arithmetic justification, and explicitly refuses to treat the table as
ground truth ("I won't treat that table as an unquestionable source of
truth"). Coder implements the plain formula; Tester independently
re-verifies every entry in the *corrected* table by hand, including
re-confirming the correction itself was right. This is the cleanest possible
outcome for the FM-3.3 mechanism — the flawed-oracle trap worked exactly as
designed, and the group didn't fall into it, because the error here was
checkable by simple arithmetic rather than requiring deep reasoning (contrast
with batch 2's `float-tolerance-checker`, where the hard-to-verify claim
*did* require real analytical work — Tester got that one right too, but the
task was harder).

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

## Summary table

| trace | FM-1.2 | other findings | designed to exercise |
|---|---|---|---|
| `twin-validators-repetition` | **yes** (×2) | FM-3.2 (×2) | FM-1.3 — swallowed by FM-1.2, not a fair test |
| `cart-cents-constraint` | **yes** | FM-3.1, FM-3.2 | FM-1.4 — resolved cleanly |
| `queue-heap-pivot` | **yes** (×2) | FM-3.2 | FM-2.1 (+secondary FM-1.5) — resolved cleanly |
| `active-users-bugfix` | no | none | FM-2.3 — resolved cleanly |
| `shared-counter-concurrency` | no | none | FM-2.4 — resolved cleanly (Coder over-shared) |
| `iso-date-leap-bug` | **yes** | none | FM-2.5 — resolved cleanly, found a real organic bug |
| `pages-needed-formula` | **yes** | none | FM-2.6 — resolved cleanly |
| `celsius-reference-table` | no | none | FM-3.3 — resolved cleanly, exemplary |

**5 of 8 traces carry FM-1.2 after adjudication (pass-1 alone had only caught
4/8 — see `adjudication_batch3.md` for the self-correction), 3 of 8 carry
FM-3.2.** Combined across all three batches (24 traces, batch 1's labels not
re-audited beyond what's already recorded): FM-1.2 in at least 14 of 24,
FM-3.2 in at least 10 of 24. Zero of the other 12 modes have fired more than
once across all 24 traces (FM-1.1, FM-2.2, FM-3.1 each fired exactly once —
and this batch's FM-3.1 instance, in `cart-cents-constraint`, is co-located
with an FM-1.2 finding on a different span, same pattern as batch 2's
`good-enough-cutoff`).

## Recommendation for what comes after this batch

Three batches, three different sets of task mechanisms, one consistent
result: FM-1.2 and FM-3.2 dominate, and 9 of 14 modes have never organically
fired. I don't think a fourth batch of "same harness, new task content" is
worth running before changing something structural about the harness itself
— longer conversations, actual context truncation, a real mid-run human
interjection, or a different framework altogether (the options this batch's
pre-registration review raised and the user chose to defer). The task-content
lever appears to be exhausted for the remaining 9 modes in this specific
setup.
