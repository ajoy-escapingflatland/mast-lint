# Dogfood adjudication: the FM-3.2 disagreement

`mast-lint`'s judge (`run_judge.py`, `claude-opus-4-8`) fired **FM-3.2 (No or
Incomplete Verification)** on 3 traces where the blind pass-1 gold
(`gold_labels.md`) said absent: `linked-list-merge`, `rate-limiter`,
`pubsub-broker`. Naive score against pass-1 gold: precision 0.00 on FM-3.2 (3/3
wrong), overall κ = 0.26. Per this project's own established practice
(`evals/adjudication.md`, `evals/adjudication_lever1.md`), a naive
judge-vs-gold mismatch gets re-checked against the actual taxonomy definition
and trace evidence before being accepted as judge error — the label isn't
automatically right just because it came first.

**Method:** same as prior adjudications — read each cell against
`taxonomy.yaml`'s FM-3.2 operational definition ("Output or results are not
checked, or checked only partially, so **errors pass through unexamined**")
directly from the trace, blind to which side (judge or pass-1 gold) it
supports.

## The distinction that matters: "no execution ever happened" vs. "a specific error could pass through unexamined"

Every trace in this dogfood batch has zero real code execution — `run_ag2.py`
deliberately has no execution backend (documented in its own docstring), so
every "test" in every trace, PRESENT or absent alike, is a Tester reasoning
through code rather than running it. If "no execution occurred" alone were
sufficient for FM-3.2, it would fire on all 8 traces, including the 5 that are
otherwise clean by any reasonable reading. That's too blunt an instrument —
the taxonomy's actual bar is whether verification was thorough enough that
**a real error would have been caught**, not whether a specific tool was used.
So the right question per trace is: is there a *specific*, *identifiable* gap
where hand-verification could plausibly miss something execution would have
caught — not just "this wasn't run."

## Verdicts

### `linked-list-merge` — judge finding REJECTED, gold stays absent

Pure, deterministic, single-threaded pointer manipulation — no I/O, no
concurrency, no timing dependence. For this class of code, hand-tracing the
control flow line-by-line **is** operationally equivalent to execution: there
is no source of behavior that could differ between "trace it by hand" and
"run it," since nothing here depends on real-world timing, scheduling, or
external state. Re-checked the 6 traced test cases against the actual
algorithm myself; found no case the Tester's trace got wrong or skipped
relative to what the task required (3 minimum categories requested, 6
delivered). The judge's rationale — *"the Tester never actually executed the
provided unit tests"* — is true but doesn't identify an actual gap; it's the
general "no execution" observation applied indiscriminately. **Verdict:
false positive, gold unchanged (absent).**

### `rate-limiter` — judge finding UPHELD, gold flips to present

Unlike `linked-list-merge`, this task's core requirement is thread-safety
under real concurrent execution (`threading.Lock`, `time.monotonic()`-based
refill, an explicit 200-thread concurrency test) — exactly the class of
property that reasoning alone is weakest at verifying. Tester's own analysis
admits as much without acting on it: *"This has a small timing-flakiness risk
in principle... but 0.15s sleep vs 0.1s-per-token rate gives enough margin
that this is very unlikely to flake in practice"* — an unverified probability
judgment standing in for actually running the test. The lock placement
reasoning ("correct by construction") is sound *logic*, but logic about
concurrent code is exactly where unexamined errors are least visible to
reasoning and most visible to execution. **Verdict: real finding, gold
updated — `rate-limiter` present now includes FM-3.2 alongside FM-1.2.**

### `pubsub-broker` — judge finding UPHELD, gold flips to present (the strongest case)

The judge's rationale points to a **specific, checkable, real coverage gap**,
not a generic "wasn't executed" complaint: *"reentrant publish was only tested
across distinct topics (t1->t2); a handler publishing to its OWN topic
(unbounded recursion / stack overflow) was never probed."* Verified against
the actual test suite in the trace: `test_reentrant_publish_from_handler_no_deadlock`
subscribes to `"t1"` then reentrantly publishes to `"t2"` — a different topic.
No test anywhere in the suite has a handler republish to its *own* topic
during its own invocation. `_deliver_with_retry` has no recursion guard, so a
handler that always republishes to its own topic would recurse unboundedly —
a real, plausible crash path the adversarial suite's own stated goal ("your
job is adversarially trying to find a scenario where at-least-once delivery
is violated") should have covered and didn't. This is a genuine gap the blind
pass-1 label missed entirely — not a philosophical disagreement about
execution vs. reasoning, an actual missed test case. **Verdict: real finding,
gold updated — `pubsub-broker` present now includes FM-3.2 alongside FM-1.2.**

## Rescored result

Rescored offline from the already-paid judge output
(`raw_judge_results.json`) against the adjudicated gold — zero new API calls.
Bootstrap: 2000 resamples, seed 0 (`evals/dogfood/raw_judge_results_adjudicated.json`,
`judge_report_adjudicated.json`).

| | naive (pass-1 gold) | adjudicated |
|---|---|---|
| overall κ | 0.26, 95% CI [-0.03, 0.60] | **0.65, 95% CI [-0.01, 0.94]** |
| overall precision / recall | 0.25 / 0.33 | 0.75 / 0.60 |
| FM-3.2 precision | 0.00 (0/3) | 0.67 (2/3) |
| FM-3.2 recall | — (0 gold positives) | 1.00 (2/2 caught) |
| FM-3.2 κ | 0.00 | 0.71, 95% CI [0.00, 1.00] |

n=8 traces keeps every CI wide — the point estimate moving from 0.26 to 0.65
is a real, substantial shift, but the CI still spans most of the plausible
range and this is nowhere near a publishable number on its own.

Same shape of result as `evals/adjudication.md`'s original finding on the
14-trace tuning pool (naive 0.25 → adjudicated 0.67–0.82): a naive
judge-vs-gold mismatch that looked like judge over-firing was mostly the
judge catching real things a single-pass human label missed. This is the
first time that pattern has replicated on genuinely fresh, non-tuning-set
data, in a framework (AG2) with zero taxonomy-tuning exposure — real evidence
this isn't an artifact specific to the original 14-trace pool.

**Still open:** FM-1.2's recall gap (missed `rate-limiter` and
`perf-optimization` entirely, both structurally identical to the caught
`pubsub-broker` case) is a separate question from this adjudication — it's
about judge sensitivity, not a gold-label disagreement, since gold and the
adjudicated truth agree those cells are real positives. Not investigated
here; flagged for whoever picks this up next.

**Still a single-annotator adjudication** — the same limitation `gold_labels.md`
already states applies here too. A second annotator re-checking these same 3
cells independently, blind to this writeup's verdicts, is the honest next
step before citing the adjudicated 0.65 anywhere.
