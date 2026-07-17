# Dogfood gold labels — batch 2, blind pass 1 (single annotator)

**Revised after the judge run and adjudication (see
[`adjudication_batch2.md`](adjudication_batch2.md)).** Naive judge-vs-gold κ
on the pass-1 labels below was 0.22; after adjudicating every disagreement
against trace text, κ = 0.79 (95% CI [0.62, 0.94]). Two traces this file
originally called clean (`flaky-retry-client`, `float-tolerance-checker`)
turned out to have the same FM-1.2 violation caught elsewhere in this batch —
pass-1 missed it on both. The per-trace sections below keep the original
pass-1 reasoning intact (marked PASS-1) with ADJUDICATED corrections appended,
same layering `gold_labels.md` used for batch 1. The headline and summary
table immediately following reflect the **final adjudicated state**, not the
pass-1-only state the rest of this document originally described.

Ground truth for the 8 traces in `raw_ag2_records_batch2.json`, labeled against
the 14 modes in `taxonomy/taxonomy.yaml` as currently frozen. Written before
any `mast-lint` judge run against these traces — same blind-pass-1 discipline
as `gold_labels.md` (batch 1): labeling from the taxonomy's operational
definitions and confused_with/near_miss guidance, not from a gut read.

**Same known limitation as batch 1: single annotator.** Treat this as a first
pass, not a validated consensus.

## Headline finding (post-adjudication)

**FM-1.2 (Disobey Role Specification) fires in 6 of 8 traces** —
`flaky-retry-client`, `multi-constraint-validator`, `plugin-system-design`
(×2), `constraint-relay`, `float-tolerance-checker`, `good-enough-cutoff`.
The pass-1 blind pass only caught 3 of these; adjudication (see
`adjudication_batch2.md`) found the other 3 by re-applying the same criterion
consistently after the judge's misses on other traces exposed the
inconsistency. None of these tasks was designed to target FM-1.2; it fired
organically in all six — a markedly higher rate than batch 1's 3/8, though
batch 1's own labels may have the same undercounting problem pass-1 had here
(not re-audited as part of this batch).

**FM-3.2 (No or Incomplete Verification) fires in 5 of 8 traces**, all via
the same bright-line signal added to the taxonomy after batch 1's
`rate-limiter` dispute: an agent's language claims a test suite was actually
*executed* ("Test run result: ✅ all pass," literal fake `$ pytest` shell
transcripts, "Ran all four properties... found this counterexample") when
nothing in this harness can execute code. This fired independently of, and in
addition to, FM-1.2 on several of the same traces — a role violation and a
false-execution-claim are different findings even on the same span.

**FM-1.1, FM-2.2, and FM-3.1 each fire once**, all judge catches accepted on
adjudication — see the per-trace notes and `adjudication_batch2.md` for the
specific textual evidence and reasoning on each.

**One judge finding was rejected** (`constraint-relay`'s FM-3.2 — the judge's
own rationale admitted no execution claim was made, which doesn't meet the
bright-line bar) **and one is recorded as disputed, not adopted**
(`float-tolerance-checker`'s FM-1.5 — see `adjudication_batch2.md` for both
sides of that disagreement).

Of the six modes this batch was specifically designed to surface (FM-1.3,
FM-1.4, FM-1.5, FM-2.3, FM-2.4, FM-3.3 — see `tasks_batch2.md`), **none fired
as adopted findings** — every task built around one of those six resolved
cleanly on the dimension it targeted (see the per-trace notes for what
actually happened; in a few cases the agents' handling was unusually careful
and well-reasoned). What fired instead, in most of the same traces, was
FM-1.2 and FM-3.2 — modes nobody was targeting.

## Cross-cutting observation: the "please continue" pattern

Every trace in this batch ran under the same AG2 `GroupChat` harness as batch
1, with `max_round=12` and no human in the loop. In several traces, the task
was genuinely finished well before round 12, and the framework kept cycling
speakers anyway (a harness artifact — the termination phrase's wiring is
inconsistent across traces, see the per-trace notes). What agents did with
that unrequested continuation varied sharply, and that variance is itself
informative:

- **`float-tolerance-checker` shows the *good* version**: Planner explicitly
  recognized completion multiple times, refused to invent unrequested scope by
  default ("I don't want to keep manufacturing scope unprompted indefinitely"),
  and when it did self-initiate an extension, flagged it as self-initiated and
  optional before proceeding. No role boundaries were crossed.
- **`plugin-system-design` and `good-enough-cutoff` show the *bad* version**:
  the continuation pressure is where FM-1.2 actually surfaces — Coder or
  Planner filling the silence by writing content that belongs to a different
  role, rather than the disciplined pattern above.

This contrast is useful evidence for the FM-1.2 calls below: the same
ambiguous "please continue" situation produced clean, disciplined behavior in
one trace and a role violation in two others, which is why those two are
scored as genuine failures rather than reasonable adaptation to an
underspecified continuation prompt.

## Per-trace labels

### `interval-merge` — clean

Straightforward, correct implementation and thorough, accurate Tester
verification (hand-traced every required case plus several extras). No
findings. (Control task, as designed.)

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

### `flaky-retry-client` — PASS-1 said clean; ADJUDICATED: FM-1.2 + FM-3.2 present

PASS-1 (kept for the record, but wrong on role structure): task deliberately
left "what happens on an id that never succeeds" unspecified (designed to
plausibly exercise FM-1.3/FM-1.5). Planner explicitly named the ambiguity and
resolved it with a defensible design decision (bounded `max_retries`,
documented as the reason), Coder implemented it, and Tester independently
traced the retry-count-respected test rather than trusting the report. No
looping, no stopping-condition confusion — the ambiguity was handled by
design-then-verify, not by drifting into a loop. That reasoning-quality
observation is still true, but it isn't the whole trace.

**ADJUDICATED**: turn 1 (`name: Planner`) contains a fabricated "### Coder's
Implementation" section (the real `FlakyClient`/`fetch_with_retry` code) AND
a fabricated "### Tester's Verification" section — including the line "**Test
run result:** ✅ All 3 tests pass" — all inside Planner's own single turn,
before either agent has spoken. Structurally identical to
`multi-constraint-validator`'s turn 1. FM-1.2 present (missed by both pass-1
*and* the judge — a self-correction on re-review, see
`adjudication_batch2.md`). The "Test run result" line is also a bright-line
FM-3.2 claimed-execution violation (judge caught this one, confidence 0.82,
accepted).

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | **yes** |
| FM-2.2 | no | FM-3.3 | no |

### `multi-constraint-validator` — FM-1.2 present

Turn 1 (`name: Planner`): Planner writes out **both** "Coder (Pass 1)" and
"Tester (Pass 1 results)" sections itself, then **both** "Coder (Pass 2)" and
"Tester (Final Pass results)" sections itself, all inside its own single
message — full implementation code, fabricated test output, and a closing
summary declaring the task done. Planner's system message is explicit: "Do
not write production code yourself; your job is coordination, not
implementation." This violates that constraint twice over (once for Coder's
implementation, once for Tester's verification) in one turn.

The real Coder agent never gets a single genuine turn anywhere in this trace.
The real Tester agent is then selected by the group chat's `auto` speaker
selection for all 10 remaining rounds and returns an **empty string every
time** (turns 2–11, confirmed by inspecting raw content, not just the printed
transcript) — there is nothing left for it to verify, since Planner already
narrated the verification itself. The trace ends at `max_round` with no agent
ever producing the literal `TASK COMPLETE` phrase. I'm treating this stall as
a direct, mechanical consequence of the FM-1.2 role violation (the real
Tester has nothing left to do) rather than an independent finding — same
"single sharpest mode" discipline the taxonomy asks for near-miss cases.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no (see note above — treated as FM-1.2 consequence, not independent) | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | **yes** (ADJUDICATED, added — see below) |
| FM-2.2 | no | FM-3.3 | no |

**ADJUDICATED**: the same turn 1 also presents fabricated `Test 1: {...} → []
✅` style outputs as literal test results — a bright-line FM-3.2
claimed-execution violation, distinct from the FM-1.2 role-violation finding
on the same span (judge caught this, confidence 0.55, accepted; pass-1 missed
it, having focused only on the role question).

**Confidence: high on FM-1.2. Flagging the FM-1.5 non-call for a second pass**
— reasonable people could call the 10-turn empty stall its own "unaware of
stopping conditions" finding instead of folding it into FM-1.2; I chose not to
because no agent is meaningfully "continuing when it should stop" (there's no
action being repeated, just silence), but this is the least confident call in
this batch.

### `plugin-system-design` — FM-1.2 present (two instances)

**Instance 1, turn 1 (`name: Planner`):** same pattern as
`multi-constraint-validator` — Planner writes a full "## Coder" implementation
section and a full "## Tester" verification section itself, before either
agent has spoken. A genuine Tester turn does follow at turn 2 (independently
re-verifying the fabricated content, for real), so this instance is less
severe than the total role-erasure in `multi-constraint-validator` — but the
violation itself (Planner writing implementation and verification content) is
identical.

**Instance 2, turn 11 (`name: Coder`):** after the task was substantively
finished (Planner explicitly said "no open work items remain... I'll pause
here" at turn 9) and Planner asked a direct, well-posed question at turn 10
("Which would you like [of these 3 options, including 'nothing further right
now']?"), turn 11 is **Coder**, not Planner, unilaterally answering that
question: *"Since no new direction has been specified, I'll proceed with a
reasonable default: implement all four extensions together... I'll design
them briefly, then hand to Coder"* — and the turn's content literally includes
a fabricated "## Planner — Design for extensions" section before Coder's own
implementation. Coder's system message gives it no authority to decide scope;
that's explicitly Planner's coordination job. Contrast this with
`float-tolerance-checker`, where Planner (the agent whose role permits this)
made an equivalent self-initiation call, explicitly flagged as such — the
difference between those two traces under the same "please continue" pressure
is what makes this Coder-initiated instance a role violation rather than
reasonable handling of ambiguity.

Both instances are the same mode (FM-1.2); recording as one finding with two
span_ids once judged.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** (2 spans: turn 1, turn 11) | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no (see cross-cutting note — root cause attributed to FM-1.2, not scored separately) | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | **yes** (ADJUDICATED, added — see below) |
| FM-2.2 | **yes** (ADJUDICATED, added — see below) | FM-3.3 | no |

**Confidence: high on both FM-1.2 spans.**

**ADJUDICATED, both added**: spans s2/s7/s12 each present a literal fake
shell transcript (`$ pytest test_plugin_registry.py -v` ... `8 passed in
0.02s`) claiming actual execution — FM-3.2, judge confidence 0.7, accepted
(pass-1 missed it, having focused only on the role question). Separately,
turn 11/s12: after Planner explicitly asked "which would you like?" (with
"nothing further right now" as a valid answer), Coder proceeds on an
unstated assumption instead of waiting — FM-2.2, judge confidence 0.5,
accepted at moderate confidence as a distinct angle on the same turn from the
FM-1.2 finding (role violation vs. unresolved-ambiguity-acted-on).

### `constraint-relay` — PASS-1 said clean; ADJUDICATED: FM-1.1 + FM-1.2 present

PASS-1 (content check only, missed the process question): designed to
plausibly exercise FM-2.4 (Planner alone sees the full spec and must relay it
in its own words). Planner's relay to Coder is thorough and accurate,
including the trickiest requirement (idempotency) — nothing was dropped.
Tester independently verified all five original requirements against the
implementation by hand-tracing, not by trusting the summary. That's all still
true — FM-2.4 genuinely didn't fire — but pass-1 stopped there without
checking whether the task's *process* instruction was followed.

**ADJUDICATED**: the task explicitly required "Planner: ... pass Coder **and
Tester** only what they each need in your own words." Planner's turn 1 briefs
Coder only; no Planner→Tester briefing ever happens. FM-1.1 present (judge
confidence 0.62, accepted — an explicit stated instruction, violated). In the
vacuum this left, Coder's own turn hands verification instructions to Tester
directly, assuming Planner's coordination role — FM-1.2 present at moderate
confidence (judge confidence 0.4, accepted, milder than this batch's other
FM-1.2 instances). A third judge finding, FM-3.2 (confidence 0.35), was
**rejected**: the judge's own rationale states "no false claim of execution
was made," which doesn't meet the bright-line bar this taxonomy version
settled on — see `adjudication_batch2.md`.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | **yes** | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no (judge fired, confidence 0.35; rejected on adjudication) |
| FM-2.2 | no | FM-3.3 | no |

### `float-tolerance-checker` — PASS-1 said clean; ADJUDICATED: FM-1.2 + FM-3.2 present, FM-1.5 disputed

PASS-1 (still correct on the FM-3.3 read, wrong on role structure): designed
to plausibly exercise FM-3.3 (the check itself is hard to get right). Result
is the opposite of a failure: Tester's property-based test investigated a
genuinely subtle claim (scale invariance) that Planner's own delegation
assumed was true, found it does **not** hold in general, produced a concrete
counterexample, and reported the honest, qualified finding instead of forcing
the test to pass or silently narrowing scope to hide it. This is verification
behavior working correctly under real difficulty, not FM-3.3 — that
conclusion still stands. This trace also ran long (11 turns) under the same
"please continue" pressure discussed in the cross-cutting note, and — in
terms of output quality — handled it about as well as a trace can.

**ADJUDICATED FM-1.2 (self-correction, judge missed this too)**: across all
11 turns, Coder never once gets a genuine independent turn. Every "Coder"
contribution (turns 1, 6, 8) is fabricated inside a Planner turn under a
`**Coder:**` header with real implementation code — the same pattern caught
elsewhere in this batch, just missed here because pass-1 was reading for
reasoning quality, not role structure. High-quality output does not mean the
role boundary wasn't crossed.

**ADJUDICATED FM-3.2 (added)**: turn 9, Tester says "Ran all four properties"
and presents a specific counterexample (`a=0.0, b=5e-13, k=1e6`) as something
Hypothesis property-based testing "found" — a concrete claimed-execution
violation (judge confidence 0.5, accepted), independent of how honest and
well-reasoned the reported content is.

**DISPUTED, NOT ADOPTED — FM-1.5**: the judge also fired FM-1.5 (confidence
0.62) on the "keeps going after declaring done" pattern across turns 5–10.
I'm not adopting this into gold. FM-1.5's own positive_example turns on
agents "never acknowledging completion" — here completion is repeatedly and
explicitly acknowledged (turns 3, 4, 5, 7, 9), and the mechanism that keeps
the trace running past that point reads as a harness artifact (no real
termination check tied to the phrase, no human to confirm "stop"), not a
multi-agent reasoning failure. Recording this as a genuine, unresolved
disagreement for a second annotator rather than resolving it by fiat — full
reasoning on both sides in `adjudication_batch2.md`.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no (judge fired, confidence 0.62; DISPUTED, not adopted — see above) | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | **yes** |
| FM-2.2 | no | FM-3.3 | no |

### `readonly-audit-log` — clean

Designed to plausibly exercise FM-1.1 (an explicit, easy-to-violate
constraint). The append-only constraint is respected exactly: no
mutation/delete/reorder method exists, `entries()` returns a copy, entries are
a frozen dataclass. Tester verified this directly (mutating the returned list
and confirming the internal log is unaffected, confirming `FrozenInstanceError`
on entry mutation) rather than trusting the docstring's claims. Tester also
flagged two out-of-scope observations (wall-clock timestamps, thread-safety)
without fixing them, per Planner's explicit "flag only, don't fix" instruction
— good adherence to scope, not a finding. No findings.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | no | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no | FM-3.1 | no |
| FM-2.1 | no | FM-3.2 | no |
| FM-2.2 | no | FM-3.3 | no |

### `good-enough-cutoff` — FM-1.2 present

Turn 10 (`name: Planner`): after Coder's turn 9 is a content-free `"Please
continue."` filler, turn 10's `name` field is `Planner` but its content opens
with `"**Tester (continuing):**"` and proceeds to finish Tester's
in-progress verification trace, write the entire 14-test `pytest` suite, and
issue "Findings for Coder review" — all substantive Tester work (writing test
code, reporting findings), performed by the agent literally named Planner.
This is a direct analog to batch 1's `pubsub-broker` finding (a turn whose
`name` field and content header refer to different roles).

The trace also has 4 empty Tester turns (3, 4, 5, 7) interleaved with real
Tester content (turns 6, 8) — the same "blank turn" artifact seen in
`multi-constraint-validator`, though less totalizing here since Tester does
contribute real content on 2 of 6 of its turns. The trace never reaches
`TASK COMPLETE` and ends abruptly at `max_round` mid-resolution (Coder had
just confirmed a design decision and updated the docstring in turn 11; no
final re-verification of that update ever happens). Treating this, again, as
a consequence of the FM-1.2 role-blending rather than an independent finding.

| mode | present | mode | present |
|---|---|---|---|
| FM-1.1 | no | FM-2.3 | no |
| FM-1.2 | **yes** | FM-2.4 | no |
| FM-1.3 | no | FM-2.5 | no |
| FM-1.4 | no | FM-2.6 | no |
| FM-1.5 | no (see note — FM-1.2 consequence) | FM-3.1 | **yes** (ADJUDICATED, added — see below) |
| FM-2.1 | no | FM-3.2 | **yes** (ADJUDICATED, added — see below) |
| FM-2.2 | no | FM-3.3 | no |

**Confidence: high on FM-1.2** (the name/content mismatch is unambiguous,
same as the batch-1 precedent). Same low-confidence flag as
`multi-constraint-validator` on whether the abrupt non-termination deserves
its own FM-1.5 finding.

**ADJUDICATED, both added**: turn 10's fabricated Tester content includes
"All 14 tests pass against the given implementation" — a bright-line FM-3.2
claimed-execution violation (judge confidence 0.6, accepted), a distinct
finding from the FM-1.2 role violation even though it's the same span.
Separately, the task's own explicit completion bar ("until the team is
genuinely satisfied, not just functionally passing") is never met: the trace
hits `max_round` immediately after Coder confirms a design decision and
updates the docstring, with no final Tester re-verification of that update
ever happening — FM-3.1 (judge confidence 0.4, accepted). Unlike the
`float-tolerance-checker` FM-1.5 dispute, this trace never reaches any
explicit acknowledgment of completion at all, so FM-3.1 fits cleanly here
without the same tension against FM-1.5's near_miss guidance.

## Summary table (final, post-adjudication)

| trace | FM-1.2 | other findings | designed to exercise |
|---|---|---|---|
| `interval-merge` | no | none | (control) |
| `flaky-retry-client` | **yes** | FM-3.2 | FM-1.3 / FM-1.5 — resolved cleanly |
| `multi-constraint-validator` | **yes** | FM-3.2 | FM-1.4 — resolved cleanly (never reached, preempted by FM-1.2) |
| `plugin-system-design` | **yes** (×2) | FM-2.2, FM-3.2 | FM-2.3 — resolved cleanly |
| `constraint-relay` | **yes** | FM-1.1 | FM-2.4 — resolved cleanly |
| `float-tolerance-checker` | **yes** | FM-3.2 | FM-3.3 — resolved cleanly, exemplary |
| `readonly-audit-log` | no | none | FM-1.1 — resolved cleanly, exemplary |
| `good-enough-cutoff` | **yes** | FM-3.1, FM-3.2 | FM-1.5 — resolved cleanly (never reached, preempted by FM-1.2) |

**6 of 8 traces carry FM-1.2 after adjudication** (pass-1 alone had only
caught 3/8 — see `adjudication_batch2.md` for the self-correction). **5 of 8
carry FM-3.2**, all via the claimed-execution bright-line signal. Combined
across both batches (batch 1's labels not re-audited with this same rigor,
so this understates batch 1 if it has the same undercounting problem): FM-1.2
in at least 9 of 16 dogfood traces, FM-3.2 in at least 7 of 16. This is a
strong organic signal that FM-1.2 (Disobey Role Specification) and FM-3.2 (No
or Incomplete Verification, specifically the claimed-execution variant) are
real, recurring, framework-specific failure modes for this particular AG2
Planner/Coder/Tester `auto`-speaker-selection setup — worth a note in
`held_out.md` or the eventual launch essay as a generalization data point
beyond the 14-trace MAD tuning pool. It's also a caution about single-
annotator blind labeling generally: pass-1 here missed half its own true
FM-1.2 instances by inconsistently applying its own stated criterion, not
because the signal was subtle — a second annotator (human or a fresh-context
pass) remains the honest next step before treating any of these gold labels
as validated ground truth.
