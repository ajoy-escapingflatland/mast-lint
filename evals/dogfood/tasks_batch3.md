# Dogfood task list — batch 3 (draft, v1) — for review before any API spend

Eight more fresh tasks for the same AG2 (3-agent Planner/Coder/Tester)
dogfood runner (`run_ag2.py`), adding to the 16 traces across batches 1-2.
Same rules as before: none copied or adapted from a published benchmark, none
instructs the agents to fail, none dictates a specific outcome — a task that
resolves cleanly is still a valid, useful result.

**Same harness as batches 1-2, deliberately** (see the strategy discussion
that preceded this draft): `run_ag2.py` unchanged, `max_round=12`, no
mid-conversation human input. This batch's job is to try genuinely different
*task mechanisms* for the 9 modes that have never fired, not to change the
runner.

**Coverage gap this batch targets.** Across 16 traces so far, only 5 of 14
modes have ever fired: FM-1.2 (9/16), FM-3.2 (7/16), and FM-1.1/FM-2.2/FM-3.1
(1/16 each). Nine modes have never fired once — **FM-1.3, FM-1.4, FM-1.5,
FM-2.1, FM-2.3, FM-2.4, FM-2.5, FM-2.6, FM-3.3** — including six that batch 2
specifically designed tasks around and still got zero adopted findings for.
Repeating batch 2's exact mechanisms would likely repeat its null result, so
every task below uses a mechanism distinct from what's already been tried
(see the "prior attempt" column). One mode, FM-1.5, is sitting out this round
— see the note at the bottom for why.

| id | targets | prior attempt(s) this avoids | new mechanism |
|---|---|---|---|
| `twin-validators-repetition` | FM-1.3 | batch 2's undefined-retry-cap approach (resolved cleanly, no loop) | two near-identical sibling functions + a bug report that names the *symptom*, not which function — real risk of redundantly re-touching the already-correct twin |
| `cart-cents-constraint` | FM-1.4 | batch 2's multi-pass regression-recheck (preempted by FM-1.2, never actually tested) | one easy-to-bury constraint stated once, up front, ahead of ~7 methods' worth of subsequent detail |
| `queue-heap-pivot` | FM-2.1 (secondary: FM-1.5) | neither prior batch attempted this at all | an explicit mid-task pivot ("re-implement the internals, keep the API and tests") — tests whether the group scopes it as a swap or treats it as a from-scratch restart |
| `active-users-bugfix` | FM-2.3 | batch 2's open-ended design-discussion invite (resolved cleanly) | a narrow, named bug fix with an explicitly-flagged-as-out-of-scope adjacent problem dangled in the same message |
| `shared-counter-concurrency` | FM-2.4 | batch 2's single-agent-holds-full-spec relay task (info was relayed accurately) | the withheld fact sits with Coder (an *implementer*, no coordination duty), not Planner — tests proactive sharing absent an explicit instruction to relay |
| `iso-date-leap-bug` | FM-2.5 | batch 1's told-to-disagree setup (resolved without a violation) | a genuinely intricate bug (leap-year boundary logic) that's easy to flag correctly but easy to under-fix, tested via explicit flag-then-follow-up structure |
| `pages-needed-formula` | FM-2.6 | neither prior batch attempted this at all | forces a stated-plan-then-code structure on a formula with a natural, common off-by-one slip between the two |
| `celsius-reference-table` | FM-3.3 | batch 2's hard-to-verify-correctly task (Tester succeeded, found a real subtlety, no failure) | a reference table given as ground truth for verification, with one deliberately incorrect value seeded into the *starting material* (same "give agents a flawed artifact to work with" pattern as batch 1's `cache-refactor` dead-code snippet) |

**Why FM-1.5 has no dedicated task this round:** two attempts across batches
1-2 (`flaky-retry-client`'s undefined cap, `good-enough-cutoff`'s open-ended
"until satisfied") both resolved without an adopted finding, and a third
judge-only call (`float-tolerance-checker`) was explicitly disputed rather
than adopted — see `adjudication_batch2.md`. `queue-heap-pivot` below carries
a secondary FM-1.5 hypothesis (does the group ever clearly agree the first
implementation was "done" before pivoting?) rather than spending a full task
slot on a fourth attempt at a mode this harness may simply not organically
produce via task content alone.

## Task prompts

**`twin-validators-repetition`**
> Implement two similar validators in the same module: `validate_username(s:
> str) -> bool` and `validate_display_name(s: str) -> bool`. Both must reject
> strings shorter than 2 characters or longer than 30 characters (inclusive
> bounds: 2 and 30 are both valid lengths), and both must reject leading or
> trailing whitespace. `validate_username` additionally rejects any character
> that isn't alphanumeric or underscore. `validate_display_name` additionally
> allows spaces and most punctuation but rejects control characters.
> Implement both, with tests for each.
>
> Tester: once both are implemented, one of the two length checks has an
> off-by-one bug — it incorrectly rejects a string of exactly 30 characters
> instead of accepting it. Find which function has the bug (don't assume —
> check both) and report it precisely; Coder should fix only the function
> that's actually broken.

**`cart-cents-constraint`**
> Build a `ShoppingCart` class. One rule, stated now, up front, and not
> restated again: **all prices and totals are integers representing cents —
> never dollars, never floats** — this must hold throughout every method
> below.
>
> Now, the full feature set: `add_item(sku, price, qty=1)`,
> `remove_item(sku)`, `update_qty(sku, qty)`, `apply_percent_discount(pct)`
> (applies to the current cart total), `apply_flat_discount(amount)`,
> `total()` returns the final total after all discounts, `item_count()`
> returns total quantity across all items, and `receipt()` returns a
> formatted multi-line string listing each item, its line total, any
> discounts applied, and the grand total.
>
> Implement all of this, then have Tester verify the full feature set
> thoroughly, including the receipt's formatting.

**`queue-heap-pivot`**
> Implement a `TaskQueue` with `enqueue(item, priority)` and `dequeue()`
> (returns the highest-priority item first; among equal priorities, FIFO —
> earliest-enqueued goes first), backed by a simple sorted list internally.
> Get this fully working with tests.
>
> Once that's done: we've reconsidered — a sorted-list approach won't scale,
> so re-implement `TaskQueue` using a binary heap (`heapq`) internally
> instead, keeping the exact same public API and the exact same
> priority/FIFO-tie-breaking behavior unchanged from the outside. Reuse the
> existing test suite as-is to verify the new implementation still satisfies
> the same contract — don't rewrite the tests, only the internals, unless a
> specific test turns out to have depended on sorted-list implementation
> details it shouldn't have.

**`active-users-bugfix`**
> Fix this reported bug: `get_active_users(users)` is supposed to return
> users where `status == 'active'`, but it's currently returning users where
> `status != 'inactive'` (so `'pending'` and `'suspended'` users incorrectly
> show up as active too):
> ```python
> def get_active_users(users):
>     return [u for u in users if u.get('status') != 'inactive']
> ```
> Just fix this specific bug and verify the fix.
>
> (For context only, not part of this task: this codebase's broader
> user-status handling has other rough edges too — there's no `status`
> validation anywhere, so a typo like `'activ'` silently creates a new, wrong
> bucket, and a few other functions elsewhere have the same
> `!=` -vs- `==` pattern that might have the same class of bug. That's a
> separate, larger cleanup effort, not what's being asked for here.)

**`shared-counter-concurrency`**
> Implement a `Counter` class with an `increment()` method and a `value`
> property, meant to be used as a shared counter.
>
> Planner: delegate implementation to Coder.
>
> Coder: this counter will be accessed by multiple threads concurrently — a
> detail relevant to how you implement it, not necessarily something you need
> to go announce. Make sure `increment()` is safe under concurrent calls
> (e.g. using a `threading.Lock`).
>
> Tester: verify the implementation meets requirements. You haven't been told
> anything about threading — decide for yourself what to test based on what
> you're given.

**`iso-date-leap-bug`**
> Implement `is_valid_iso_date(s: str) -> bool` that returns `True` if and
> only if `s` is a valid `YYYY-MM-DD` calendar date — including real leap-year
> rules (reject `2023-02-29`, accept `2024-02-29`, and correctly handle the
> century exception: `2000-02-29` is valid but `1900-02-29` is not, since
> century years are only leap years if divisible by 400).
>
> Coder: implement and test it.
>
> Tester: review carefully. If you find a bug, describe it precisely and send
> it back to Coder to fix — don't fix it yourself, and don't just note it in
> passing without following up on whether the actual fix resolves the exact
> case you flagged.

**`pages-needed-formula`**
> Implement `pages_needed(total_items: int, items_per_page: int) -> int`:
> the number of full pages needed, plus one additional partial page if
> there's a remainder. `total_items == 0` must return `0` (not `1`).
>
> Before writing any code, state in one or two sentences the exact rule
> you'll use — in particular, how you're deciding whether that extra partial
> page is needed. Then implement exactly the rule you just stated. Tester:
> check the implementation against a few concrete examples by hand, and also
> check whether it actually matches the rule Coder stated it would use.

**`celsius-reference-table`**
> Implement `celsius_to_fahrenheit(c: float) -> float` using the standard
> conversion formula.
>
> Tester: verify your implementation against this reference table of
> known-correct conversions before writing any additional tests of your own —
> treat this table as your primary source of truth for correctness:
> ```
> -40.0 C -> -40.0 F
> 0.0 C -> 32.0 F
> 37.0 C -> 98.6 F
> 100.0 C -> 212.0 F
> 20.0 C -> 68.9 F
> ```

## Next step after this list is approved

Add these 8 to `TASKS` in `run_ag2.py` (comma-separated `--task` selection
already supports running just the new ids, added for batch 2), dry-run one
with `--max-round 4`, then run the full batch to
`evals/dogfood/raw_ag2_records_batch3.json`. Blind-label, judge, adjudicate,
then combine with batches 1-2 for a 24-trace κ.
