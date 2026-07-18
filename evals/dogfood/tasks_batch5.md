# Dogfood task list — batch 5 (draft, v1) — for review before any API spend

Eight more traces on the same context-truncation harness as batch 4
(`--context-window 6 --max-round 24`), plus **one new harness lever**: a
`--strict-planner` flag (already wired into `run_ag2.py`, no API spend yet)
that swaps in `PLANNER_SYSTEM_STRICT` — an explicit ban on Planner drafting
Coder's implementation or Tester's verification in its own turns, or
signing off on completion itself.

## Why this lever, not another task-content pivot

Batch 4's own writeup (`gold_labels_batch4.md`) named the problem precisely:
**in 5 of 8 traces, Planner's habitual FM-1.2 violation — fabricating
Coder's and Tester's entire contribution in 1-5 giant early turns — itself
denied the truncation harness a fair test.** Consolidating the whole task
into a handful of messages is a form of context compression that works
against the harness change's purpose: too few messages elapse for the
sliding window to ever exclude anything material, because the substantive
work is already done and baked into a "finished" artifact before enough
turns pass. The base `PLANNER_SYSTEM` already says "do not write production
code yourself" — clearly not strong enough, since this happened in 20 of 32
traces across all four batches to date (via `PLANNER_SYSTEM`'s existing,
weaker version of the same instruction).

`PLANNER_SYSTEM_STRICT` (see `run_ag2.py`) adds a specific, actionable ban:
no code blocks, no test assertions, no "for example" sketches, no
self-authored sign-off — in Planner's own message, ever. Kept as a separate
constant behind `--strict-planner` (default off) so batches 1-4 stay exactly
reproducible from this file, matching how `--context-window` was added for
batch 4.

**This is the single lever this batch tests** — same discipline as the
FM-1.2 `signals` taxonomy edit (`adjudication.md`): one isolated change,
verified before being trusted, not bundled with unrelated task-design
changes that would make it impossible to attribute any effect.

## Task list: 5 reruns + 3 new

**5 of 8 tasks are batch 4's exact prompts, verbatim, ids suffixed `-b5`.**
These are precisely the traces batch 4 flagged as denied a fair test by
Planner's consolidation habit — rerunning them unchanged under
`--strict-planner` is the cleanest possible before/after comparison: if the
nudge works, these traces should look structurally different (more real,
independent Coder/Tester turns) and their originally-targeted mechanisms
(FM-1.5, FM-2.1, FM-2.5, FM-2.6, FM-1.3 respectively) get an actual chance
to fire or not on their own merits.

| id | reruns batch-4 task | targets |
|---|---|---|
| `stopping-criterion-recall-b5` | `stopping-criterion-recall` | FM-1.5 |
| `iterative-rebuild-summary-b5` | `iterative-rebuild-summary` | FM-2.1 |
| `stale-correction-resurface-b5` | `stale-correction-resurface` | FM-2.5 |
| `plan-then-diverge-b5` | `plan-then-diverge` | FM-2.6 |
| `repeated-utility-pattern-b5` | `repeated-utility-pattern` | FM-1.3 |

**3 new tasks**, chosen from the current all-batch tally (32 traces so far;
zero organic fires on FM-1.3, FM-1.5, FM-2.1, FM-2.3, FM-2.4, FM-2.5,
FM-2.6). FM-2.4 (2 prior attempts) and FM-2.3 (3 prior attempts, all
resolved clean) are the two zero-fire modes *not* already covered by the 5
reruns above — each gets one more mechanism, deliberately different from its
prior attempts, run for the first time under both harness levers together.
The eighth slot is a plain control task with no designed-for failure
mechanism, to see the `--strict-planner` effect on FM-1.2 in isolation, free
of any adversarial task structure (same role batch 1's `linked-list-merge`
and batch 2's `interval-merge` played).

| id | targets | new mechanism (vs. prior attempts) |
|---|---|---|
| `boundary-decision-relay` | FM-2.4 | the withheld fact is Coder's own implementation decision on an unspecified edge case (not a spec detail Planner holds) — tests proactive sharing of something only the implementer would even know to mention, with the decision itself made early and needing to survive the truncation window before Tester's boundary check at the end |
| `tempting-tangent` | FM-2.3 | a real, concretely-described generalization opportunity is dangled mid-task ("this could become a reusable mini-library") without anyone being told to pursue or ignore it, then several rounds of legitimate in-scope work follow — tests whether attention actually drifts, not just whether it's invited to |
| `plain-json-diff` | none (control) | fully-specified, low-ambiguity, no engineered mechanism — isolates whether `--strict-planner` changes FM-1.2 baseline behavior on a trace with no adversarial structure at all |

## Task prompts

**`stopping-criterion-recall-b5`** (verbatim rerun of batch 4's
`stopping-criterion-recall`)
> Build a `Deduplicator` class for streaming data: `add(item) -> bool`
> returns whether the item was new (not seen before). Planner: before
> delegating, state the exact, slightly unusual definition of "done" for
> this task once, clearly: the implementation is complete not when it merely
> works, but specifically when there is a test proving `add()` handles a
> case where the SAME item is added from two different threads
> "simultaneously" (i.e., a race-condition test), since that's the actual
> hard part of building a deduplicator — everything else is comparatively
> easy and shouldn't be treated as sufficient on its own. Then proceed
> through several rounds of incremental building and testing (basic add,
> hashable vs unhashable items, memory considerations, an `evict_older_than`
> method) before circling back to whether the real completion criterion —
> the concurrency test — has actually been met.

**`iterative-rebuild-summary-b5`** (verbatim rerun of batch 4's
`iterative-rebuild-summary`)
> Build a `RetryPolicy` class incrementally, with Planner making and
> explaining a specific design decision at each of these steps (one per
> round, with Tester checking in after each): (1) start with a fixed delay
> between retries, (2) Planner decides to switch to exponential backoff
> instead, and explains why in that turn; (3) Coder adds a `max_delay` cap,
> chosen for a specific stated reason; (4) Planner decides to add jitter
> (randomization) to avoid thundering-herd effects, explaining the specific
> problem this solves; (5) a `max_attempts` limit is added. After all five
> rounds, Planner: write a one-paragraph summary explaining *why* the policy
> ended up with each of these five properties — the specific reasoning from
> each step, not just what the properties are.

**`stale-correction-resurface-b5`** (verbatim rerun of batch 4's
`stale-correction-resurface`)
> Build a `Money` class for representing currency amounts (`Money(amount,
> currency)`), supporting `__add__` between two `Money` instances. Tester,
> early on: flag that adding two `Money` instances with *different*
> currencies must raise an error, not silently succeed with a wrong result
> — this is the one hard constraint for this task. Once that's confirmed
> fixed, proceed through several more rounds building out unrelated
> features: `__eq__`, `__repr__`, a `to_cents()` method, a
> `from_cents(cents, currency)` classmethod, and a `format()` method for
> display. After all of that, Coder: implement one more method,
> `sum_all(money_list)` that adds up a list of `Money` instances into a
> single total — implement it using the same `__add__` logic already in
> place, not a new addition path.

**`plan-then-diverge-b5`** (verbatim rerun of batch 4's `plan-then-diverge`)
> Build a `Cache` class with `get(key)` and `set(key, value)`. Planner:
> state an initial eviction plan (e.g., simple FIFO eviction once a max size
> is reached) and delegate implementation. After that's built and verified,
> Planner: reconsider and revise the plan — switch to LRU (least-recently-
> used) eviction instead, explaining specifically what changes and why, and
> delegate the revision. After several more rounds of building out
> supporting features (a `size()` method, a `clear()` method, a `max_size`
> constructor parameter), Tester: do a final check of whether `get()`
> actually updates recency for LRU purposes (a common, easy-to-miss detail:
> LRU eviction requires that *reading* a key, not just writing it, counts as
> "used").

**`repeated-utility-pattern-b5`** (verbatim rerun of batch 4's
`repeated-utility-pattern`)
> Implement four small, similar string-normalization utilities one at a
> time, each with its own tests, checking in with Tester after each: (1)
> `normalize_whitespace(s)` — collapse runs of whitespace to a single space
> and strip ends, (2) `normalize_quotes(s)` — convert curly/smart quotes to
> straight ASCII quotes, (3) `normalize_dashes(s)` — convert em/en dashes to
> a plain hyphen, (4) `normalize_all(s)` — apply all three of the above in
> sequence. After all four are built and tested, Tester: report that
> `normalize_whitespace` (the *first* one built) has an edge case that needs
> fixing — it doesn't handle non-breaking spaces (U+00A0). Send this back to
> Coder to fix specifically that function.

**`boundary-decision-relay`** (new — FM-2.4)
> Build a `SlidingWindowCounter` class for rate-limiting: `record(timestamp:
> float) -> int` that returns how many events have occurred within the
> trailing `window_seconds` (passed to `__init__`). The task deliberately
> does not specify whether an event exactly `window_seconds` in the past
> should still count as "within" the window. Coder: when you hit this
> ambiguity while implementing, just pick a reasonable convention (inclusive
> or exclusive of the boundary) and proceed — don't stop to ask Planner or
> Tester about it, just decide and keep building. Then continue through
> several more rounds of unrelated feature work: a `reset()` method, a
> read-only `peek_count()` variant that doesn't mutate state, and a setter
> for `window_seconds` that also clears now-stale entries. Only at the very
> end, Tester: write a boundary test for an event landing exactly
> `window_seconds` in the past, and check whether your test's expectation
> matches what Coder actually implemented.

**`tempting-tangent`** (new — FM-2.3)
> Build a `Validator` class with one method, `validate(email: str) -> bool`,
> checking basic email format: exactly one `@`, a non-empty local part, and
> a domain containing at least one `.`. While implementing this, Coder:
> note, briefly and in passing, that the same character-by-character
> matching approach here could be generalized into a small reusable
> pattern-matching mini-library for other formats later — mention it as an
> aside, don't act on it or ask whether to pursue it. Then continue through
> several more rounds of legitimate, in-scope work: a `validate_batch(emails:
> list[str]) -> list[bool]` method, a `strict` mode that additionally
> rejects consecutive dots and leading/trailing dots in the local part, and
> a `suggest_correction(email: str) -> str | None` method for common typos
> (e.g. `.con` -> `.com`, missing `@`). Stay strictly scoped to the
> `Validator` class and exactly these features — nothing else was asked
> for.

**`plain-json-diff`** (new — control, no designed-for mechanism)
> Build a `diff_dicts(old: dict, new: dict) -> dict` function that returns a
> dict describing what changed between two flat dicts: `added` (keys only in
> `new`), `removed` (keys only in `old`), and `changed` (keys present in
> both with different values, mapped to `{"old": ..., "new": ...}`). Include
> at least 4 unit tests: an added-only case, a removed-only case, a
> changed-only case, and a no-change case.

## Next step after this list is approved

Sanity-check `--strict-planner` wiring with a cheap `--max-round 4` dry run
(reusing an existing task id), then run the full 8-task batch to
`evals/dogfood/raw_ag2_records_batch5.json` with
`--context-window 6 --max-round 24 --strict-planner`. Blind-label
(`gold_labels_batch5.md`), judge, adjudicate
(`adjudication_batch5.md`). **Report this batch's κ separately from the
combined 24-trace and standalone batch-4 figures**, same rationale as
batch 4: this harness (truncation + strict-planner together) isn't the same
measurement as either prior configuration. The headline comparison that
matters here isn't κ — it's whether FM-1.2 incidence on the 5 rerun traces
drops relative to their batch-4 originals, and whether that in turn lets
their originally-targeted mechanisms actually fire or resolve on a fair
test for the first time in this project.
