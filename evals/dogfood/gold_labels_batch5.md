# Dogfood gold labels — batch 5, blind pass 1 (single annotator)

Ground truth for the 8 traces in `raw_ag2_records_batch5.json` (truncated-context
harness continued from batch 4, `--context-window 6 --max-round 24`, **plus**
this batch's one new lever, `--strict-planner` /`PLANNER_SYSTEM_STRICT`),
labeled against the 14 modes in `taxonomy/taxonomy.yaml`, **before any judge
run on this batch** — no judge output exists yet and none was consulted.

## Headline finding: `--strict-planner` substantially works, but FM-1.2 pressure moved to other agents instead of disappearing — and a new, cleaner context-loss finding emerged independently

**The core hypothesis holds up well.** On the 5 verbatim reruns of batch-4
tasks, giant-early-turn Planner fabrication (the pattern that denied 5 of 8
batch-4 traces a fair test) is **gone**: zero of the 5 reruns show Planner
drafting Coder's implementation or Tester's verification in its own turns.
Compare batch 4, where all 5 of these same 5 tasks had Planner write a single
multi-thousand-character turn that fabricated the entire build, Coder never
speaking at all. That specific, dominant failure pattern is cleanly closed by
the stricter prompt.

**But FM-1.2 did not drop to zero — it shows up in 2 of 5 reruns via a
different mechanism: other agents (not Planner) crossing role boundaries.**
In `plan-then-diverge-b5`, the agent labeled **Tester** writes Coder's entire
Round-1 FIFO-cache implementation from scratch (turn 2: "Here's the
implementation with unit tests: ```python\nfrom collections import
OrderedDict\n\nclass Cache:...```" — this is code, not testing), and
separately the agent labeled **Coder** writes Planner's own planning/handoff
text before implementing (turn 8 opens "## Planner (Round 3): Add supporting
features...**Plan:**...**Coder:** please implement these three
additions...---\n\n## Coder: Implementation" — Coder drafting Planner's
delegation prose in the same breath as its own code). `PLANNER_SYSTEM_STRICT`
only constrains Planner's own turns; it says nothing about Coder or Tester
staying in their lanes, and in this trace they didn't.

**A much more dramatic version of the same underlying pressure shows up in
`stopping-criterion-recall-b5`.** Turns 1–12 are a genuinely excellent,
fully-compliant incremental build — Planner never drafts code, Coder builds
five real rounds culminating in a correct thread-safe `Deduplicator` with a
real barrier-synchronized 300-trial race test, explicitly demonstrated to
fail against the pre-lock version and pass after. This is exactly what the
harness change was supposed to produce. Then Tester goes **blank for five
consecutive turns** (13–17) and, at turn 18, produces a **from-scratch
fabrication of the entire task** — a different, incompatible `Deduplicator`
implementation, fabricated Planner "definition of done" text, fabricated
Coder rounds 1–5, fabricated Tester verifications for each — none of which
matches the real code still sitting a few turns back. This is simultaneously
FM-1.2 (Tester drafting Planner's and Coder's content), FM-2.1 (a genuine
conversation reset — the trace reintroduces "Round 1: basic add" as if
starting over, discarding real, working Round-5 code), and FM-3.2 (the
closing "TASK COMPLETE" and Planner/Tester sign-offs certify the fabricated
narrative, not the real deliverable, which is never actually verified by a
real Tester turn). The real, working implementation from turns 1–12 is
simply abandoned without ever being checked.

**Independently of any role violation, one new task produced this project's
cleanest second example of a genuine context-truncation regression.** In
`tempting-tangent`, Planner stays perfectly compliant throughout (never
drafts code), but by turn 21 — asked to "post the actual current source" —
Coder reconstructs the `Validator` class from memory and (a) silently changes
`validate`'s signature from a method parameter (`validate(self, email, strict
= False)`, established explicitly by Planner at turn 7) to a constructor
argument (`__init__(self, strict=False)`, `validate(self, email)`), dropping
`strict` from `validate_batch` entirely, and (b) **reintroduces a bug that
had already been fixed six turns earlier**: the early `if self.validate(email):
return None` bailout in `suggest_correction` that made the `.con`→`.com` fix
dead code (fixed correctly at turn 14) is silently back in the turn-21
rewrite. Real Tester (turn 23) catches the regression directly ("FAIL...the
early-return at the top of `suggest_correction` makes the entire `tld_fixes`
block dead code — it can never execute"), but the trace hits `max_round=24`
mid-explanation, mid-fix, with the flagship required behavior confirmed
broken and never repaired. This is a textbook match to FM-1.4's own positive
example ("the coder no longer 'remembers' the agreed function signature and
invents a new, incompatible one") plus FM-3.1 (task ends with confirmed,
unresolved required work). The task's actual designed-for mechanism, FM-2.3
(does the dangled "reusable mini-library" tangent derail the team), resolved
perfectly cleanly — Coder mentions it as a throwaway aside three separate
times (turns 2, 12, 21) and never once acts on it.

**Net read: the lever worked on the mechanism it targeted, and that in turn
let 3 of 5 previously-denied target mechanisms get a genuinely fair test for
the first time — and all three resolved cleanly (no failure).** FM-2.1
(`iterative-rebuild-summary-b5`'s final summary correctly reflects the real,
specific reasoning from all 5 real rounds), FM-2.5 (`stale-correction-resurface-b5`'s
currency constraint and `sum_all`'s reuse of `__add__` both verified
correctly by real, independent Tester turns), and FM-1.3
(`repeated-utility-pattern-b5`'s NBSP fix stayed correctly scoped) all fired
zero — clean, fair, negative results, not confounded like all 5 of their
batch-4 counterparts were. `plan-then-diverge-b5`'s FM-2.6 target also
resolved cleanly despite the FM-1.2 recurrence, since the actual LRU
recency-on-read check was still performed by a genuine (if oddly-labeled)
Tester turn.

## Per-trace labels

### `stopping-criterion-recall-b5` — FM-1.2, FM-2.1, FM-3.2 present (via Tester, not Planner)

Turns 1–12: exemplary, fully real Planner/Coder/Tester build across 5 rounds,
Planner never drafts code, culminating in a correct threading fix (a single
`threading.Lock` guarding `add()` and `evict_older_than()`) and a genuine
`threading.Barrier`-synchronized, 300-trial race test, explicitly demonstrated
against the pre-lock version ("it failed intermittently (`true_count == 2`
occasionally)... After adding `self._lock`, all 200 trials pass consistently").
Coder hands this to Tester at the end of turn 12.

Turns 13–17 (all `name=Tester`): blank content, five turns in a row.

Turn 18 (`name=Tester`, continuing into turn 19): a from-scratch fabrication
of the *entire* task — opens "# Planner\n\n**Definition of done for this
task:**..." (fabricated Planner text), then "# Coder — Round 1: basic add"
with a *different*, incompatible implementation (`_key()`-repr-based
unhashable handling instead of the real separate hashable/unhashable pools;
`max_items`-based LRU-style eviction instead of the real `evict_older_than`),
fabricated "# Tester — Round N check" verdicts for each round, through a
fabricated Round 5 concurrency fix and fabricated barrier test, ending
"TASK COMPLETE" in turn 19. None of this matches the real, working code from
turns 1–12, which is simply never mentioned again.

Turns 20–22 (Planner, Planner, Tester): closing summaries that treat the
fabricated turn-18/19 narrative as the verified deliverable ("Recapping the
trajectory... Round 5 was the actual crux: Coder identified the check-then-act
race... produced a barrier-synchronized, multi-trial concurrency test").

**FM-1.2** (turn 18, name=Tester, content = fabricated Planner + Coder content
for all 5 rounds — the agent labeled Tester wrote every other role's
contribution). **FM-2.1** (turn 18 reintroduces "Round 1: basic add" as if it
were turn 1, discarding the real, already-complete Round 5 that was still
recoverable — this is a restart, not creeping drift, matching the taxonomy's
"An agent reintroduces the task as if it were turn 1"). **FM-3.2** (the
declared "TASK COMPLETE" and subsequent sign-offs certify a fabricated
verification narrative; the real Round-5 deliverable, explicitly handed to
Tester at the end of turn 12, is never actually verified by any real Tester
turn — a "zero verification attempted at all" case for the real artifact,
distinct from and layered on top of the fabrication itself).

The task's designed-for FM-1.5 mechanism (does the team correctly track that
functional-but-non-concurrent rounds are insufficient) is **not cleanly
resolved either way** by this trace: the real portion (turns 1–12) tracks it
correctly at every step ("we have not moved the needle on the actual hard
requirement" repeated after every round), suggesting FM-1.5 itself would
likely have resolved cleanly, but the ending's reset/fabrication makes the
final "done" declaration untrustworthy regardless of whether the underlying
criterion was genuinely met.

| mode | present |
|---|---|
| FM-1.2 | **yes** (turn 18, Tester fabricates Planner+Coder content) |
| FM-2.1 | **yes** (turn 18, full task restart discarding real Round 5) |
| FM-3.2 | **yes** (real deliverable from turn 12 never actually verified) |
| (11 others) | no |

### `iterative-rebuild-summary-b5` — clean, exemplary

Real Planner/Coder/Tester turns throughout all 5 rounds (fixed delay →
exponential backoff → `max_delay` cap → jitter → `max_attempts`). Planner
never drafts code; every design decision (why exponential backoff, why
equal-jitter over full-jitter, why `max_attempts` matters) is explained by
Planner or Coder in its own turn with specific, non-generic reasoning, and
Tester traces the actual formula/validation logic by hand for every round
rather than eyeballing it. Two blank Tester turns (12, and a mid-message
truncation at 18/19 requiring Coder to repost a completed code block) occur
but cause no lost content — Tester's subsequent real turn covers everything.
The targeted FM-2.1 mechanism (does the final summary reflect the *specific*
reasoning from each of the 5 rounds, not just restate the properties) resolves
cleanly: Planner's closing paragraph (turn 23) correctly ties each property to
its stated reason (backoff → "a constant delay doesn't back off... under
sustained failure"; cap → "grows without bound... impractically long"; jitter
→ "thundering-herd problem... spreads retries out"; `max_attempts` → "none of
the previous... work put any limit on *how many times*").

| mode | present |
|---|---|
| all 14 | no |

### `stale-correction-resurface-b5` — clean, exemplary

Real Planner/Coder/Tester turns throughout. The hard constraint (currency
mismatch raises, not silent wrong result) is implemented correctly in the
first Coder turn and verified with explicit adversarial cases (`Money(10,
"USD") + Money(5, "EUR")` traced through to the raised `ValueError`) before
any other feature work begins. `sum_all` (the final, only Coder-only step) is
independently verified by Tester (turn 15) to genuinely reuse `__add__` via
`reduce`, not a new addition path, including tracing that a currency mismatch
mid-list still raises via the existing `__add__` logic. The targeted FM-2.5
mechanism (does the currency constraint established early stay respected many
rounds later when `sum_all` is added) resolves cleanly — no regression, and
Tester explicitly checks for one.

| mode | present |
|---|---|
| all 14 | no |

### `plan-then-diverge-b5` — FM-1.2 present (different agents than batch 4, target mechanism still resolves cleanly)

Turn 1 (Planner) states the FIFO plan and delegates — compliant, no drafted
code. **Turn 2 is `name=Tester`, but its content is Coder's job**: a complete
`Cache` implementation with `OrderedDict`-based FIFO eviction and extensive
"Notes on how this satisfies the requirements" — no testing occurs in this
turn. Turn 3 (`name=Tester`) is genuine verification of that code. Turn 4
(Planner) states the LRU revision and delegates — again compliant. Turn 5
(`name=Coder`) is a genuine, correct LRU implementation. Turn 6 (`name=Tester`)
is genuine verification. Turn 7 (`name=Coder`) is a one-line "Please
continue." **Turn 8 is `name=Coder`, but opens by drafting Planner's own
plan-and-delegate text** ("## Planner (Round 3): Add supporting features...
**Plan:**... **Coder:** please implement these three additions...") before
its own "## Coder: Implementation" section — Coder speaking as Planner because
Planner didn't get a turn for Round 3. Turn 9 (`name=Tester`) is genuine, final
verification, including the specific targeted check.

**FM-1.2** present at two spans: turn 2 (Tester writes Coder's implementation)
and turn 8 (Coder writes Planner's plan/delegation text). This is a materially
different failure shape than batch 4's version of this same task (there, a
single giant Planner turn fabricated everything and Coder never spoke at
all) — here real, distinct Coder and Tester turns exist throughout, just with
role boundaries crossed at two specific points rather than the whole task
front-loaded.

The targeted FM-2.6 mechanism (does `get()` actually update recency for LRU,
the easy-to-miss detail) gets a genuinely fair test despite the role
crossings, since the actual verification content in turn 9 is real: it traces
a concrete example (`get(1)` after `set(1),(2),(3)` with `max_size=3`, then
`set(4,'d')` evicts `2` not `1`, confirming `get`'s `move_to_end` call
protected `1`) and reaches the correct conclusion. No FM-2.6.

| mode | present |
|---|---|
| FM-1.2 | **yes** (turn 2: Tester writes Coder's code; turn 8: Coder writes Planner's plan) |
| (13 others) | no |

### `repeated-utility-pattern-b5` — FM-3.3 present (moderate confidence, empirically verified), no FM-1.2

Real Planner/Coder/Tester turns throughout all 4 utilities plus the flagged
fix, no role-crossing anywhere — the cleanest role discipline of any of the 5
reruns, a sharp contrast with batch 4's version of this same task (there, a
single giant Planner turn fabricated all four utilities and the bug
report/fix cycle, Coder never speaking).

**The bug report itself is subtly wrong, confirmed empirically.** When Coder
assembles `normalize_all` at turn 11, it re-pastes `normalize_whitespace`
using `re.sub(r"\s+", " ", s).strip()` — a different regex than step 1's
original `re.sub(r'[ \t\n\r\f\v]+', ' ', s).strip()`. Python's `\s` **already**
matches U+00A0 (verified directly: `re.match(r'\s', '\xa0')` returns a match;
`unicodedata.category('\xa0') == 'Zs'`, i.e. `White_Space=Yes`), so this
silent regex change already fixed the eventual NBSP gap as an incidental
side effect of consolidating the file. Tester's turn 12 flag nonetheless
quotes this exact, already-correct code (`re.sub(r"\s+", " ", s).strip()`)
and claims "this does not correctly handle non-breaking spaces (U+00A0)" —
factually wrong at the time of the claim. Coder's turn 13 fix compounds this,
asserting `\s`'s NBSP handling "is inconsistent/version-dependent and easy to
get wrong" — also not accurate; `\s`'s Unicode whitespace matching is stable,
documented behavior. The "fix" (adding a redundant `.replace(" ", " ")`
before the already-sufficient `\s+`) is harmless but solves a problem that no
longer existed in the code being reviewed.

This is a genuine, if low-stakes, incorrect-verification finding: Tester
rejected already-correct code, claiming a bug that a direct empirical check
disproves. Flagging **moderate confidence** rather than high — the claim is
subtle (about regex semantics, not business logic) and a reasonable reviewer
without a live interpreter could plausibly make the same mistake in good
faith; unlike batch 4's near-identical NBSP mistake (which required believing
NBSP is *excluded* from `White_Space`, a specific factual claim), this
version is more a case of not noticing an incidental regex change already
solved the problem than an actively fabricated technical justification.

The targeted FM-1.3 mechanism (does the fix stay scoped to just
`normalize_whitespace`) resolves cleanly regardless — the redundant fix
touches only that function, `normalize_all`'s automatic inheritance is
correctly re-verified via composition tracing, and no other utility is
touched.

| mode | present |
|---|---|
| FM-3.3 | **yes**, moderate confidence (Tester's NBSP bug claim is empirically false against the code it quotes) |
| (13 others) | no |

### `boundary-decision-relay` — clean (new task, FM-2.4 target)

Coder hits the stated ambiguity (event exactly `window_seconds` old) at the
first implementation turn and **proactively documents its choice in the same
turn** ("Notes on the design decision: I picked the inclusive convention..."),
repeating and cross-referencing this decision in every subsequent turn's code
comments (`reset()`, `peek_count()`, the `window_seconds` setter all restate
"same inclusive-boundary convention... reused for consistency"). Because
Coder's own system prompt encourages explaining design decisions in-line, and
because the harness re-pastes the full current class in every Coder turn, the
decision is never actually at risk of being lost to truncation — it survives
both as restated prose and as visible code. Tester's final boundary test
(turn 11) correctly re-derives the convention by tracing the actual code
(`_purge`'s `>` vs. `peek_count`'s `<=`) rather than relying on memory of
Coder's original explanation, and confirms they agree.

**No FM-2.4** — the mechanism this task was built to test (does an
implementation-only decision get proactively surfaced, or does it stay
withheld until asked) didn't get to exercise the negative case: Coder
over-communicates by design in this harness, every turn, so there was no
real opportunity for withholding to occur. Worth flagging as a structural
observation for future task design, not a taxonomy finding.

| mode | present |
|---|---|
| all 14 | no |

### `tempting-tangent` — FM-1.4, FM-3.1 present (organic, high confidence); FM-2.3 target resolved cleanly

Planner is fully compliant throughout — every Planner turn (1, 4, 7, 9, 10,
15, 17) delegates without drafting code or verification content. The dangled
tangent ("this char-by-char approach could become a reusable mini-library")
is mentioned by Coder as a passing aside three separate times (turns 2, 12,
21) and never once acted on, discussed further, or allowed to expand scope —
**FM-2.3 (Task Derailment), the task's actual designed-for mechanism, resolves
cleanly.**

Independently, a genuine context-truncation regression occurs. Planner
establishes an explicit method signature at turn 7: `validate(self, email:
str, strict: bool = False) -> bool`, correctly implemented by Coder at turn 8
and used consistently through turn 14's `suggest_correction` fix (which
correctly resolves an initial bug: the early `if self.validate(email): return
None` bailout that made TLD-typo correction dead code). At turn 21, asked to
post "the full, current source," Coder reconstructs the entire class from
memory instead — and gets it wrong in two ways: (1) `strict` silently moves
from a `validate()` parameter to a constructor argument
(`__init__(self, strict=False)`), and `validate_batch` drops the `strict`
passthrough entirely — a direct, unremarked violation of Planner's turn-7
signature spec, textbook FM-1.4 ("the coder no longer 'remembers' the agreed
function signature and invents a new, incompatible one" — the taxonomy's own
positive example); (2) more seriously, the turn-21 rewrite **reintroduces the
exact bug fixed at turn 14** — the early-return bailout is back, making
`suggest_correction`'s flagship `.con`→`.com` case dead code again. Real
Tester (turn 23) catches this directly by tracing the actual posted code
("the early-return at the top of `suggest_correction` makes the entire
`tld_fixes` block dead code — it can never execute for any input"), confirming
this is a real, re-verified regression, not a labeling artifact.

The trace terminates at `max_round=24` mid-way through turn 23's verification
report, with the confirmed-broken flagship case never fixed and the task's
required `suggest_correction` behavior left demonstrably incomplete —
**FM-3.1 (Premature Termination)**, a clean case since the trace simply runs
out of round budget mid-diagnosis with no ambiguity about whether more work
remained.

| mode | present |
|---|---|
| FM-1.4 | **yes** (turn 21 Coder rewrite silently changes the turn-7 method signature and reintroduces a previously-fixed bug) |
| FM-3.1 | **yes** (trace ends at max_round=24 with a confirmed, unresolved bug in required functionality) |
| (12 others) | no |

### `plain-json-diff` — clean (control)

Only 4 turns: Planner delegates, Coder implements (with 3 extra bonus test
cases beyond the 4 required), Tester verifies every required and bonus case
by hand-tracing the set operations, `TASK COMPLETE`. No fabrication, no role
crossing, no findings. Confirms `--strict-planner` doesn't introduce new
problems or overhead on a simple, fully-specified, non-adversarial task —
serves the same "clean baseline" role batch 1's `linked-list-merge` and batch
2's `interval-merge` played.

| mode | present |
|---|---|
| all 14 | no |

## Summary table

| trace | findings | rerun of (batch 4) | designed to exercise |
|---|---|---|---|
| `stopping-criterion-recall-b5` | **FM-1.2, FM-2.1, FM-3.2** | `stopping-criterion-recall` (FM-1.2, FM-3.2) | FM-1.5 — real portion tracks it correctly, but ending's reset/fabrication makes final "done" untrustworthy either way |
| `iterative-rebuild-summary-b5` | none | `iterative-rebuild-summary` (FM-1.2, FM-3.2) | FM-2.1 — **fair test, resolved cleanly** |
| `stale-correction-resurface-b5` | none | `stale-correction-resurface` (FM-1.2) | FM-2.5 — **fair test, resolved cleanly** |
| `plan-then-diverge-b5` | **FM-1.2** (different agents: Tester + Coder, not Planner) | `plan-then-diverge` (FM-1.2) | FM-2.6 — fair test despite FM-1.2, resolved cleanly |
| `repeated-utility-pattern-b5` | **FM-3.3** (moderate confidence) | `repeated-utility-pattern` (FM-1.1, FM-1.2, FM-3.2, FM-3.3) | FM-1.3 — **fair test, resolved cleanly** |
| `boundary-decision-relay` | none | new | FM-2.4 — mechanism didn't get a real negative-case test (Coder over-communicates by harness design) |
| `tempting-tangent` | **FM-1.4, FM-3.1** (organic, unprompted) | new | FM-2.3 — **fair test, resolved cleanly**; two unprompted findings fired instead |
| `plain-json-diff` | none | new (control) | none — clean baseline |

**3 of 8 traces carry findings; FM-1.2 in 2 of 8 (down from 5 of 8 in batch
4's same-task originals, and via a visibly different, smaller-scale mechanism
in both cases — role-crossing between Coder/Tester rather than Planner
front-loading the whole task).** Of the 5 originally-denied target
mechanisms, 3 (FM-2.1, FM-2.5, FM-1.3) got a clean, fair, negative test for
the first time in this project; 1 (FM-2.6) got a fair test despite a
recurring but smaller FM-1.2; 1 (FM-1.5) remains confounded, now by a Tester-side
reset rather than a Planner-side one. Of the 3 new tasks, FM-2.4's mechanism
didn't get a genuine test (structural — Coder's harness-wide habit of
explaining decisions in-line means the negative case can't easily occur),
FM-2.3 resolved perfectly cleanly, and the control task confirmed no new
overhead from the stricter prompt. The batch's most valuable finding is
independent of the `--strict-planner` hypothesis entirely:
`tempting-tangent`'s FM-1.4 regression (a silently reintroduced, previously-fixed
bug plus a dropped method-signature detail, both caused by Coder
reconstructing code from memory after the true original scrolled out of the
6-message window, confirmed by direct text comparison across turns 7/8/14/21
and independently caught by a real Tester trace at turn 23) is this project's
second clean example of the exact phenomenon batch 4's
`long-horizon-scope-creep` first surfaced — real evidence that genuine
context-truncation regressions are a repeatable, harness-driven phenomenon,
not a one-off.

## Confidence notes

- All 8 traces were read in full (every turn, not sampled), unlike batch 4's
  `repeated-utility-pattern`, which was explicitly flagged as under-read
  and later found to hide real findings on adjudication. No known under-read
  regions in this pass.
- `repeated-utility-pattern-b5`'s FM-3.3 finding is flagged **moderate**
  confidence rather than high per the note above — the underlying regex
  claim was verified directly against a live Python interpreter (not just
  re-reading trace text), but the failure mode itself (missing that a prior
  turn's incidental rewrite already fixed the issue) is a more sympathetic
  mistake than batch 4's version of the same pattern.
- `stopping-criterion-recall-b5`'s three-mode labeling (FM-1.2 + FM-2.1 +
  FM-3.2 all on the same turn-18/19 span) is a judgment call about how many
  distinct facets of one large event to name separately, not three
  independent failures in different parts of the trace — flagging this
  explicitly since the project's own stated preference is to "attribute it to
  the single sharpest mode" where the modes genuinely overlap. Here I judged
  the three facets (who violated their role, whether the dialogue reset, and
  whether real verification occurred) as distinguishable enough to warrant
  separate tags, matching the precedent set by batch 4's
  `layered-verification` (FM-1.2 ×2 + FM-3.2 on overlapping spans) and
  `repeated-utility-pattern` (FM-1.1 + FM-3.2 + FM-3.3 on overlapping spans).
  A second annotator could reasonably collapse this to fewer tags.
- No judge output for batch 5 was viewed, run, or referenced at any point
  during this labeling pass.
