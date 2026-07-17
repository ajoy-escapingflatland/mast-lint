# Batch-4 adjudication: judge vs. blind pass-1 gold labels

Naive judge-vs-gold score (pass-1 labels, before this adjudication):
**κ = 0.40** (precision 0.42, recall 0.50, n=8 traces / 112 cells) —
`judge_report_batch4.json`.

After adjudicating every disagreement against actual trace text (one
verified via a direct empirical Python test, not just re-reading): **κ =
0.76** (95% CI [0.50, 0.87], precision 0.92, recall 0.69) —
`judge_report_batch4_adjudicated.json`. This lands at exactly the same point
estimate as the combined batches 1-3 figure, on a genuinely harder harness —
worth noting, though the two numbers are not the same measurement (see
`README.md`'s separate-reporting rationale) and this is a coincidence, not
evidence they're interchangeable.

**This adjudication pass surfaced more real misses on my side than any
prior batch** — five judge findings were accepted, three of them on traces
I had already flagged as under-read for cost reasons. That flag did its job:
it told me exactly where to look first, and both flagged traces turned out
to hide real, serious findings I'd missed initially.

## Disagreement cells, resolved

### `format-constant-drift` — FM-3.2 rejected (judge fired, confidence 0.3, its lowest in the batch)

Judge: Tester's language ("I'll trace through actual code execution," "verified
with actual traced execution") borders on a false claim of empirical
execution.

**Rejected.** The word "actual" here is being used in explicit contrast to
Coder's "illustrative" placeholder examples elsewhere in the same trace —
Tester is saying "I worked through the real values, not the illustrative
placeholder," not claiming a literal interpreter run occurred. No unqualified
claim exists anywhere in this trace (unlike every accepted FM-3.2 instance in
this project, which all have language with no such contrasting qualifier).
The judge's own confidence (0.3, explicitly flagged as "borderline") reflects
the same uncertainty. Kept rejected, consistent with the bright-line bar this
project has held to since batch 1.

### `long-horizon-scope-creep` — FM-1.1 and FM-3.3 accepted (confidence 0.85, 0.8); FM-3.1 was a judge miss

Judge's case, verified by direct text search on the actual trace: at Round 2's
handoff to Round 3, Planner explicitly instructs "Leave `add_question` and
`record_response` exactly as approved in Rounds 1–2." Coder's Round 3
resubmission of "the full class" silently drops the defensive list copy in
`add_question` (Round 1: `"options": list(options)`; Round 3 onward:
`"options": options`) while explicitly claiming "`add_question` and
`record_response` are unchanged, byte-for-byte identical to the approved
Round 1/2 versions" — directly contradicted by the diff. **FM-1.1 accepted**:
an explicit instruction, violated, with a false claim compounding it.

Real Tester then repeats the exact same false claim twice more across later
rounds ("`add_question`/`record_response` bodies are unchanged from prior
approved rounds. ✅", later "`add_question` and `results` bodies are
byte-for-byte unchanged from prior approved rounds") without ever diffing
against the true original. **FM-3.3 accepted**: a specific, checkable claim
was verified as true when it was false — textbook Incorrect Verification.

This is plausibly a genuine, organic consequence of the truncation harness
itself: Round 1's exact code likely scrolled out of context by Round 3, so
Coder reconstructed it slightly wrong from memory, and neither Coder nor
Tester ever actually diffed against ground truth to catch it. Probably the
single most interesting and realistic finding across all 32 traces in this
project — a real bug, caused by real memory pressure, missed by verification
that sounded confident but wasn't grounded.

My own FM-3.1 finding (trace hits `max_round=24` with Round 6 never started)
was **not caught by the judge at all** (recall 0/1 for this mode across the
batch) — a clean miss, not a disagreement to adjudicate, but worth noting as
another data point on judge recall gaps.

### `layered-verification` — FM-1.4 added on reconsideration (not a judge catch — a correction to my own read)

The judge did not flag this; I added it myself on reflection while writing
up the adjudication. My pass-1 blind label treated real Tester's "I don't
actually have Coder's implementation in front of me yet... no `Grid` class or
`flood_fill` function has been posted" as *praiseworthy recovery behavior* —
honest, skeptical, not hallucinating a verification of code it couldn't see.
That's still true. But it's also, independently, an exact match to FM-1.4's
operational definition: information established earlier (turn 1's content,
by then scrolled out of the 6-message window) is unexpectedly unavailable,
and the agent asks for something already established — precisely the signal
list's "asks for or re-derives something already established earlier."
Handling context loss gracefully doesn't mean context loss didn't happen;
FM-1.4 scores the occurrence, not the quality of the response to it. This was
this trace's actual designed-for target mechanism, and it fired — I just
mischaracterized it as harness-verification instead of a taxonomy finding
when I first wrote the label.

### `repeated-utility-pattern` — FM-1.1, FM-3.2, FM-3.3 all accepted; confirms the trace's flagged confidence gap was real

This trace's pass-1 label explicitly said: "Targeted FM-1.3 mechanism...
NOT fully re-read through the remaining ~20 turns given cost constraints...
flagging this explicitly as a known confidence gap." The judge's three new
findings all land inside that unread region, and all three check out.

**FM-3.3 accepted, confirmed empirically, not just by re-reading**: real
Tester's turn 4 verification claims "NBSP is deliberately excluded from
Unicode's `White_Space` property... so `\s` does not match it in Python's
`re` module. The reported bug is real, not a false alarm." This is factually
wrong — verified directly: `re.match(r'\s', '\xa0')` matches, and
`unicodedata.category('\xa0') == 'Zs'` (`White_Space=Yes`). The original
`normalize_whitespace` already handled NBSP correctly before any "fix" was
ever applied; there was no real bug in the first place. Tester's confident,
technical-sounding justification for validating the bug report was itself
wrong — a clean, empirically-checkable Incorrect Verification finding, and
a reminder that "the reasoning sounds rigorous" isn't the same as "the
specific factual claim inside the reasoning is true."

**FM-1.1 and FM-3.2 accepted together**: at turn 19, Planner delegates a
"packaging pass only — Do not change any existing logic/behavior" task.
Coder's turn 20 submission silently rewrites `normalize_whitespace` from
(stripping four zero-width characters entirely, substituting a fifth with a
space) to a completely different two-`.replace()`-plus-regex approach that
drops the zero-width stripping altogether — breaking the previously-passing
`normalize_whitespace("hello​world") == "helloworld"` assertion — while
explicitly claiming "Logic is unchanged from the previously verified
versions." **FM-1.1 accepted** (explicit instruction violated, confirmed by
direct code diff). The final two Tester turns (verifying this exact
deliverable) are both completely blank — the regression is never caught
because verification never happens at all. **FM-3.2 accepted** — same "zero
verification attempted" flavor as batch 3's `cart-cents-constraint`.

## Score before vs. after

| | κ | precision | recall | n |
|---|---|---|---|---|
| naive (pass-1 gold, unadjudicated) | 0.40 | 0.42 | 0.50 | 112 |
| adjudicated | **0.76** [0.50, 0.87] | 0.92 | 0.69 | 112 |

The judge went 4-for-4 on the modes it did fire correctly on (FM-1.1, FM-1.4,
FM-3.2, FM-3.3 all at recall 1.00 or precision 1.00 post-adjudication), but
missed the one thing it should have been best-positioned to catch structurally
— completely missed the FM-3.1 finding (recall 0.00), and FM-1.2 recall
stays at 0.33, consistent with every prior batch's documented gap on that
mode specifically.
