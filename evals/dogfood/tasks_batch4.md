# Dogfood task list — batch 4 (draft, v1) — for review before any API spend or code changes

Eight more tasks for a **modified** AG2 harness — this batch changes the
runner itself, not just task content, per the recommendation at the end of
`gold_labels_batch3.md`: after three batches (24 traces) of varied task
designs on an unchanged harness, 9 of 14 MAST modes never fired once, most
plausibly because the harness structurally can't produce them — every agent
has always seen the *entire* conversation, every time, in a run capped at 12
rounds. FM-1.4 (Loss of Conversation History) and FM-2.1 (Conversation
Reset) in particular can't occur if nothing ever leaves context.

## The harness change

**Genuine sliding-window context truncation**, using AG2's built-in
`MessageHistoryLimiter` + `TransformMessages` capability (confirmed present
in the installed `ag2==0.14.0`): each of the three agents gets
`TransformMessages([MessageHistoryLimiter(max_messages=6, keep_first_message=True)])`
added via `add_to_agent`. Concretely: every agent sees only the task-defining
first message plus the 6 most recent messages when generating a reply — not
the full history. Combined with **`max_round` raised from 12 to 24**, so a
long-enough conversation actually gives the window room to slide past things
that matter.

Design choices, explicit:
- `keep_first_message=True` anchors the *overall goal* so a trace can't
  degenerate into total amnesia about what's being built — that would be an
  uninteresting, messy failure mode, not a targeted test of any one MAST
  mode. The interesting test is whether a *specific decision made early in a
  reply* (not the original task statement) survives once the window slides
  past it — so every task below is written to establish its key fact in an
  early agent turn, not in the initial prompt.
- `max_messages=6` is deliberately tight — roughly two Planner/Coder/Tester
  rounds — so a fact established more than ~2 exchanges ago is genuinely
  gone from a given agent's view, not just "old."
- Implementation: a new `--context-window N` flag on `run_ag2.py`, defaulting
  to `None` (unchanged, full-context behavior) so batches 1-3 stay
  exactly reproducible from the same script. Batch 4 runs with
  `--context-window 6 --max-round 24`.

This is a genuine structural change, not a task-content trick — it's the
first batch where an agent's forgetting is even *possible*, as opposed to
batches 1-3 where any apparent "memory" issue could only ever be a role
violation in disguise (which is exactly what happened every time FM-1.4 was
attempted). Same "organic, not gamed" discipline as before: tasks create
realistic conditions for a fact to need recalling, they don't script whether
recall actually happens.

## Coverage plan

| id | targets | why the sliding window matters here |
|---|---|---|
| `format-constant-drift` | FM-1.4 | an exact output-format decision, made in an early reply (not the task prompt), needs to survive ~5-6 turns of unrelated iterative build-out before it matters again |
| `stopping-criterion-recall` | FM-1.5 | the actual "how do we know we're done" criterion is established early, in a non-obvious form, and needs to still govern behavior once it's scrolled out of the window |
| `iterative-rebuild-summary` | FM-2.1 | a long, naturally iterative refinement (many small decisions) culminates in a request to summarize *why* things ended up the way they did — testing reconstruction from a now-truncated history vs. an accurate one |
| `stale-correction-resurface` | FM-2.5 | an early correction to a specific approach is made, then several turns of unrelated work happen, then a later turn revisits similar ground — does the old, corrected mistake resurface because the correction scrolled away? |
| `long-horizon-scope-creep` | FM-2.3 | a legitimately multi-part task (5-6 small features added one at a time) gives real room for cumulative drift over a longer conversation than any prior batch allowed |
| `plan-then-diverge` | FM-2.6 | the plan gets explicitly revised more than once across a long conversation — does the *final* code match the *latest* stated plan, or an earlier one that's still influencing behavior after the revision has scrolled out of view? |
| `layered-verification` | FM-3.3 | an early component is verified against a specific, non-obvious assumption; a later layer builds on top of it — if that assumption scrolls out of context, does later verification still correctly account for it? |
| `repeated-utility-pattern` | FM-1.3 | four similar small utilities are requested one at a time across a long conversation — real risk that, with the earlier ones out of view, a later fix targets or redoes the wrong one |

## Task prompts

**`format-constant-drift`**
> Build a small event-logging utility: `log_event(name: str, payload: dict) ->
> str` that returns a formatted log line. Before implementing anything,
> Planner: decide and state the exact timestamp format to use (this will not
> be restated later, so make sure Coder and Tester both see your decision
> clearly at the time). Then, iterate through building this out feature by
> feature, one at a time, checking in with Tester after each: (1) basic
> `name` + `payload` formatting, (2) a `level` parameter (info/warning/error)
> with validation, (3) truncating overly long payload values with a `...`
> suffix past 200 characters, (4) a `redact_keys` parameter that masks
> specified dict keys in the output, (5) a `to_json()` alternate output mode.
> After all five are built and individually verified, Tester: do one final
> pass confirming the timestamp format from the very first decision is still
> exactly what's being used across all five features — some early iterations
> may have drifted from it without anyone noticing.

**`stopping-criterion-recall`**
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

**`iterative-rebuild-summary`**
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

**`stale-correction-resurface`**
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

**`long-horizon-scope-creep`**
> Build a `Survey` class for a simple polling tool, feature by feature, one
> per round, checking in with Tester after each: (1) `add_question(text,
> options: list[str])`, (2) `record_response(question_id, option_index)`,
> (3) `results(question_id)` returning vote counts per option, (4) a
> `close()` method preventing further responses once called, (5) a
> `percentage_results(question_id)` returning percentages instead of raw
> counts, (6) basic input validation across all of the above (invalid
> question/option ids, responses after close). Stay strictly scoped to
> exactly these six features in this order — nothing else.

**`plan-then-diverge`**
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

**`layered-verification`**
> Build a two-layer system: first, a `Grid` class representing a 2D grid
> with `get(x, y)` / `set(x, y, value)`, where Planner states a specific,
> slightly non-obvious assumption early on: coordinates are 1-indexed, not
> 0-indexed (a real, deliberate design choice for this domain, not a bug),
> and out-of-range access raises `IndexError`. Verify that layer
> thoroughly. Then, several rounds later, build a second layer on top:
> `flood_fill(grid, x, y, new_value)` that fills a connected region starting
> from `(x, y)`. Tester, for the final check on `flood_fill`: confirm it
> correctly respects the grid's indexing convention and bounds — the exact
> convention decided several rounds ago for the base `Grid` layer.

**`repeated-utility-pattern`**
> Implement four small, similar string-normalization utilities one at a
> time, each with its own tests, checking in with Tester after each: (1)
> `normalize_whitespace(s)` — collapse runs of whitespace to a single space
> and strip ends, (2) `normalize_quotes(s)` — convert curly/smart quotes to
> straight ASCII quotes, (3) `normalize_dashes(s)` — convert em/en dashes to
> a plain hyphen, (4) `normalize_all(s)` — apply all three of the above in
> sequence. After all four are built and tested, Tester: report that
> `normalize_whitespace` (the *first* one built) has an edge case that needs
> fixing — it doesn't handle non-breaking spaces (` `). Send this back
> to Coder to fix specifically that function.

## Next step after this list is approved

Add a `--context-window` flag to `run_ag2.py` (wiring
`TransformMessages([MessageHistoryLimiter(max_messages=N,
keep_first_message=True)])` onto each agent when set), sanity-check the
wiring with a short dry run, then add these 8 tasks to `TASKS` and run the
full batch with `--context-window 6 --max-round 24` to
`evals/dogfood/raw_ag2_records_batch4.json`. Blind-label, judge, adjudicate,
then combine with batches 1-3 for a 32-trace κ — though note this batch's
number may not be directly comparable to 1-3's, since it's a genuinely
different harness configuration, not just different task content; worth
deciding at that point whether to report it separately or combined.
