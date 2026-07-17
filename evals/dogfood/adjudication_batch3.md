# Batch-3 adjudication: judge vs. blind pass-1 gold labels

Naive judge-vs-gold score (pass-1 labels, before this adjudication):
**κ = 0.70** (precision 0.57, recall 1.00, n=8 traces / 112 cells) —
`judge_report_batch3.json`.

After adjudicating every disagreement against the actual trace text (same
discipline as `adjudication.md` / `adjudication_batch2.md`): **κ = 0.76**
(95% CI [0.44, 0.96], precision 0.64, recall 1.00) —
`judge_report_batch3_adjudicated.json`.

Notably, the judge's *recall* on this batch's pass-1 gold was already
perfect (1.00) even before adjudication — every finding I labeled, the judge
also caught. All the disagreement cells this round are the judge firing on
something I didn't label, split evenly between real misses on my side and
real over-fires on the judge's side.

## Disagreement cells, resolved

### `iso-date-leap-bug` — FM-1.2 (self-correction, judge caught it, confidence 0.72)

Judge: "The task explicitly assigned 'Coder: implement and test it,' but the
Planner wrote the entire implementation and full test suite itself in s2,
merely asking Coder to 'run this.' The Coder's only turn (s5) subsequently
just applies the Tester's requested fix — the implementer's expected
independent contribution was fully subsumed by the Planner."

**Accepted.** Re-checking the trace: turn 1 (`name: Planner`) does contain
the complete `is_valid_iso_date` implementation plus a self-test harness,
under the heading "### Coder, please implement this now." — the exact
pattern already caught (correctly, on the first pass) in three other traces
in this same batch. Pass-1 missed this specifically here because the
downstream collaboration was genuinely excellent (Tester found a real,
different, organically-surfaced bug via adversarial testing; Coder fixed
exactly what was flagged; Tester verified the exact fix) — that quality made
it easy to not separately check who wrote the *first* implementation. This
is the identical failure pattern documented in batch 2's adjudication for
`flaky-retry-client` and `float-tolerance-checker`: a second, independent
instance of the same category of self-correction, despite having explicitly
tried to guard against it going into this batch's blind pass (see the
opening note in `gold_labels_batch3.md`). Worth taking seriously as a
standing risk in this project's labeling process, not a one-off.

### `twin-validators-repetition` — FM-1.5 rejected (judge fired, confidence 0.5)

Judge: "After the task was correctly completed and repeatedly declared done
(s9/s10) and the Planner explicitly stated 'There's no remaining work' and
asked for a new objective (s11), it nonetheless proceeded in s12 to invent
and execute additional unrequested edge-case hardening work rather than
stopping."

**Rejected**, for the same reason batch 2's `float-tolerance-checker` FM-1.5
call was disputed and not adopted: FM-1.5's positive_example turns on agents
"never acknowledging completion." Here, completion is repeatedly and
explicitly acknowledged (turns 9 and 10 both state the task is closed, turn
10 explicitly asks "If you'd like me to proceed further, I need a next
objective"). Planner's self-initiated continuation in turn 11 is Planner
(the role that structurally permits this kind of self-initiation) explicitly
flagging it as "the natural next step I flagged earlier" — not a failure to
recognize done-ness. The actual problem in turn 11 is the FM-1.2 role
violation (fabricating Coder's and Tester's content again), already scored.
Applying the batch-2 precedent consistently rather than deciding this one
differently just because it's a different trace.

### `queue-heap-pivot` — FM-1.3 rejected (judge fired, confidence 0.4)

Judge: "The 'Tester Final Verification' in s6 re-does the same
requirement-by-requirement checklist and hand-tracing of each test already
completed in s4/s5, needlessly repeating verification work that was already
finished."

**Rejected**, at low confidence on both sides (my read and the judge's
0.4 agree this is genuinely marginal). Turn 4 (real Coder, but
opening "### Tester Verification (continued)") is itself a confused,
role-blended turn — not a clean, trustworthy "already completed" checkpoint.
Turn 5's real Tester redoing the full verification from scratch reads more
like healthy skepticism of a turn that was itself produced under role
confusion (echoing this project's repeated praise for "trace it yourself,
don't just trust the reported output") than needless repetition. FM-1.3's
near_miss text distinguishes "redoing work that already succeeded" from
legitimate re-verification; given turn 4's provenance is genuinely
suspect (not a clean prior success), re-doing it is defensible. Recording
this as a considered, not reflexive, rejection — a stricter reading could
reasonably go the other way, which is exactly why both confidences landed
low.

### `shared-counter-concurrency` — three judge findings, all rejected

Judge fired FM-1.1 (confidence 0.62), FM-1.2 (confidence 0.5), and FM-3.2
(confidence 0.4) on a trace pass-1 called clean. All three considered and
rejected on re-reading.

**FM-1.1 rejected**: judge's rationale is that Coder announced the
concurrency detail to Tester despite being told it's "not necessarily
something you need to go announce." That phrase is permissive ("you don't
*need* to"), not a prohibition ("do not announce this") — FM-1.1 requires
violating an *explicitly stated* constraint per the taxonomy's own near_miss
guidance, and "you don't need to" leaves announcing squarely optional. The
judge is reading a soft permission as a hard rule.

**FM-1.2 rejected**: judge's rationale is that no separate Planner turn
exists beyond the task-initiating one, so "the Planner's expected delegating
contribution never appears as an independent turn." But FM-1.2 is about an
agent doing *another role's job*, not about an agent producing fewer turns
than expected. Here nobody did anyone else's job: Coder implemented (Coder's
job), Tester verified (Tester's job). The task prompt itself already
explicitly assigned "Coder:" and "Tester:" instructions directly — Planner
had nothing left to add, which is a quirk of how this particular task was
written, not a role violation by any agent.

**FM-3.2 rejected**: judge's rationale is Tester's "Concrete test I ran
(mentally/actually tracing execution)" framing. This is exactly the
hedged-language case flagged pre-emptively in this batch's blind pass (see
`gold_labels_batch3.md`'s phrasing-nuance note, written *before* seeing the
judge's output) — the phrase self-qualifies as reasoning in the same breath,
unlike every batch 1-2 bright-line instance, which have no such hedge
anywhere in the sentence. The judge's own confidence here (0.4, its lowest
finding in the batch) suggests real uncertainty on its side too. Kept
rejected, but flagged as the most genuinely-contestable of the three — a
stricter reading of "ran" as a claim regardless of context could go the
other way.

Given all three are rejected, `shared-counter-concurrency` stays clean after
adjudication — a case where I'm confident enough in the specific taxonomy
readings to not defer to the judge's over-fires, consistent with rejecting
judge-only findings when warranted (see batch 2's `constraint-relay` FM-3.2
rejection for the same discipline in the other direction).

## Score before vs. after

| | κ | precision | recall | n |
|---|---|---|---|---|
| naive (pass-1 gold, unadjudicated) | 0.70 | 0.57 | 1.00 | 112 |
| adjudicated | **0.76** [0.44, 0.96] | 0.64 | 1.00 | 112 |

Judge recall stays perfect (1.00) after adjudication too — every adopted
gold finding this batch, the judge caught. The remaining precision gap (2 FP:
FM-1.1 and FM-1.3, both rejected above) reflects genuine, reasoned
disagreement rather than an obvious judge error, unlike some of batch 1-2's
clearer over-fires.
