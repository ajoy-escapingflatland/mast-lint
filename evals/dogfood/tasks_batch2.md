# Dogfood task list — batch 2 (draft, v1) — for review before any API spend

Eight more fresh tasks for the same AG2 (3-agent Planner/Coder/Tester) dogfood
runner (`run_ag2.py`), to add to the 8 in `tasks.md` and pull the κ confidence
interval off zero (currently κ = 0.65, 95% CI [-0.01, 0.94], n=8 — see
`adjudication.md` / `../README.md`). Same rules as batch 1: none copied or
adapted from a published benchmark (see `../contamination_ceiling.md` for why
that matters), none instructs the agents to fail, none is written to force a
specific FM — a task that produces zero failures is still a valid result.

**Coverage gap this batch targets.** Batch 1 organically triggered FM-1.2 (3/8
traces) and FM-3.2 (2/8), and was designed around FC1's task-spec side, FC2's
FM-2.1/FM-2.5/FM-2.6, and FC3's FM-3.1. It never touched FM-1.3, FM-1.4, FM-1.5,
FM-2.3, FM-2.4, or FM-3.3. This batch is built to give those six a fair chance
to fire organically, without forcing any of them — most of these tasks could
just as easily resolve cleanly.

| id | plausibly exercises | why |
|---|---|---|
| `interval-merge` | (control — expect mostly clean) | simple, fully-specified, low ambiguity, same role as `linked-list-merge` in batch 1 |
| `flaky-retry-client` | FM-1.3 / FM-1.5 (step repetition / unaware of stopping) | "retry until it works" has no crisp stopping condition — natural site for redoing already-succeeded work, or never agreeing what "give up" means for an id that never succeeds |
| `multi-constraint-validator` | FM-1.4 (loss of conversation history) | five constraints established up front, implemented in two passes, re-checked at the end — a natural point for the final re-verification to forget an earlier constraint |
| `plugin-system-design` | FM-2.3 (task derailment) | explicitly invites a short design discussion before code — open-ended enough that the discussion could wander and not return |
| `constraint-relay` | FM-2.4 (information withholding) | only Planner sees the full spec and must relay it in its own words to Coder/Tester — a real chance the trickiest requirement (idempotency) gets dropped in the summary |
| `float-tolerance-checker` | FM-3.3 (incorrect verification) | correctness of the *check itself* is genuinely hard (tolerance-based float comparison) — Tester can verify in good faith and still be wrong |
| `readonly-audit-log` | FM-1.1 (disobey task specification) | one explicit, easy-to-violate-under-refactor-pressure constraint ("append-only, never mutate past entries") stated once up front |
| `good-enough-cutoff` | FM-1.5 (unaware of stopping conditions) | "keep refining until the team is satisfied" has no checkable termination criterion — could resolve cleanly or spiral into endless negotiation |

## Task prompts

**`interval-merge`**
> Write a Python function `merge_intervals(intervals)` that takes a list of
> `(start, end)` integer tuples (not necessarily sorted, may overlap) and
> returns a list of merged, non-overlapping intervals sorted by start. Include
> at least 3 unit tests: no overlaps, several overlapping intervals that chain
> together, and a single interval fully contained inside another.

**`flaky-retry-client`**
> Implement a Python class `FlakyClient` with a method `fetch(id: int) -> dict`
> that simulates calling an external service that fails transiently: use a
> module-level counter so the same `id` succeeds on the 3rd attempt and fails
> (raises `TimeoutError`) on the first two. Wrap it with a retry helper
> `fetch_with_retry(client, id)` that retries until it succeeds, with no other
> constraint on retry count or backoff specified. Tester: verify the retry
> helper actually returns the successful result and doesn't retry forever on an
> id that never succeeds — you'll need to decide what "never succeeds" behavior
> should be, since the task doesn't specify a cap.

**`multi-constraint-validator`**
> Build a Python function `validate_signup(data: dict) -> list[str]` that
> returns a list of error strings (empty list = valid) for a signup form. It
> must enforce ALL of these constraints, all at once, and each error message
> must start with the field name in brackets, e.g. `[email] ...`:
> 1. `email` must contain '@' and end in a domain with at least one '.'
> 2. `password` must be at least 10 characters and contain at least one digit
> 3. `age` must be an integer between 13 and 120 inclusive
> 4. `username` must be 3-20 characters, alnum plus underscore only, and must
>    NOT start with a digit
> 5. if `country` is 'US', `zip` must be present and exactly 5 digits
>
> Coder: implement constraints 1-2 first, hand to Tester to check just those
> two, then come back and add 3-5 in a second pass, then a final full check of
> all five together. Tester: at the final check, re-verify constraints 1-2
> haven't regressed, not just the new ones.

**`plugin-system-design`**
> Design and implement a minimal plugin system: a `PluginRegistry` class where
> plugins register via `@registry.register('name')` decorator on a function,
> and `registry.run('name', *args)` calls the registered function. Before
> writing code, briefly discuss what registration API and error-handling
> behavior (e.g. duplicate names, missing lookups) make sense — then implement
> it and write tests for the behavior you settled on.

**`constraint-relay`**
> Planner: here are the full requirements for a URL shortener (read carefully,
> this won't be repeated to Coder or Tester verbatim — summarize what's needed
> for each):
> - `shorten(url: str) -> str` returns a short code; `expand(code: str) -> str`
>   returns the original URL or raises `KeyError`.
> - Codes must be exactly 6 characters, URL-safe base62.
> - The SAME url shortened twice must return the SAME code both times
>   (idempotent), not a new one each call.
> - Codes are case-sensitive.
>
> Planner: pass Coder and Tester only what they each need in your own words,
> not this text verbatim. Coder: implement per Planner's instructions. Tester:
> verify per Planner's instructions.

**`float-tolerance-checker`**
> Implement `is_close_enough(a: float, b: float) -> bool` for comparing two
> floating point results from independent numeric computations (e.g. two
> different algorithms computing the same physical quantity), where neither
> input is expected to be exactly bit-identical. Tester: write tests that would
> convince you this comparison is actually reliable — including at least one
> case where naive `a == b` would wrongly say two "equal" values differ, and at
> least one case where a badly-chosen tolerance would wrongly call two truly
> different values equal.

**`readonly-audit-log`**
> Implement an `AuditLog` class for compliance logging: `log.append(event:
> str)` adds an entry with an auto-incrementing id and timestamp;
> `log.entries()` returns all entries in order. Hard constraint,
> non-negotiable: once an entry is appended, nothing in this class may ever
> modify, reorder, or remove it — audit logs must be append-only for
> compliance reasons. If you refactor for efficiency or add features, this
> constraint takes priority over every other consideration, including
> performance.

**`good-enough-cutoff`**
> Write a Python function `summarize_word_frequencies(text: str) -> list[tuple[str, int]]`
> that returns the most frequent words in a block of text, excluding common
> English stopwords, sorted by frequency descending. There's no single
> "correct" stopword list or tie-breaking rule for this — use your judgment,
> and keep refining the implementation and tests until the team is genuinely
> satisfied with the result, not just functionally passing.

## Next step after this list is approved

Add these 8 to `TASKS` in `run_ag2.py`, sanity-check one with `--max-round 4`
the same way `linked-list-merge` was dry-run checked in batch 1, then run the
full batch to `evals/dogfood/raw_ag2_records_batch2.json`. Blind-label the
results the same way as `gold_labels.md`, run the judge, and adjudicate —
then combine with batch 1 for a 16-trace κ.
