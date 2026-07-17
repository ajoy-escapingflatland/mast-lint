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

## FM-1.2 recall gap — investigated (2026-07-16)

Not a gold-label disagreement (gold and the judge agree these cells are real
positives) — a judge-sensitivity question, investigated separately.

**Structural asymmetry, found for free by comparing spans:** `pubsub-broker`
has a span where the literal `agent=` metadata says `Planner` while the
content itself opens `## Tester — Verification Report` — a bare
metadata/content contradiction the judge can cite without inference. In
`rate-limiter` and `perf-optimization`, the same underlying violation (Planner
ghost-writing Coder's/Tester's turns) only shows up as inline markdown
sub-headers within one Planner span (`**Coder:**` / `**Tester:**`) — no span
carries a self-contradicting `agent=` label. Two rules in
`prompts/judge_system.md` plausibly make that difference decisive: Rule 2
("prefer precision over recall — report a mode only when the trace clearly
exhibits it") and Rule 4 ("one finding per distinct failure... choose the
most specific mode"), which in `rate-limiter`'s case seems to have pointed
the judge at FM-3.2 instead of also firing FM-1.2 for the same span.

**Tested against single-run luck, not just inferred:** 5 additional paid runs
(`claude-opus-4-8`, `evals/dogfood/raw_recall_check.run{1..5}.json`) against
just these two traces, reusing `evals.aggregate_runs` per this project's
established multi-run-verification practice
(`evals/adjudication_lever1.md`).

| trace | FM-1.2 fired |
|---|---|
| `rate-limiter` | 1/5 runs |
| `perf-optimization` | 0/5 runs |

**`perf-optimization` (0/5) is the stronger result — not just "usually
missed," never caught across 5 independent stochastic draws.** It's also the
structurally hardest case: `Coder` never gets a real turn anywhere in this
trace, so there's no independent Coder-authored span to compare against
Planner's ghost-written version and notice near-duplication — the only
available signal is "an agent named Coder never spoke at all," which nothing
in the prompt surfaces as a checkable fact (the judge sees per-span `agent=`
labels, not a roster of who was expected to participate).

**`rate-limiter`'s one hit (run 2, confidence 0.4)** is real signal the
judge *can* find this pattern without a metadata tell, just rarely and
weakly — its rationale independently reconstructs the same evidence I did:
*"the Planner's message (s2) embeds fully-formed 'Coder's output' code and
'Tester's output' tests and a completed verification step itself... before
those agents actually respond."* Confidence 0.4 is well below that same
run's FM-3.2 confidence (0.55) on the same trace — consistent with the
judge treating it as the weaker, more inferential call.

**Conclusion:** the gap is a real, mechanism-level detection weakness, not
this run's bad luck — the judge is systematically better at catching FM-1.2
when there's a hard structural tell (name/content mismatch) than when it
requires inferring role-impersonation from content duplication alone,
independent of whether a competing finding (FM-3.2) is available to explain
the anomaly instead. If this generalizes, it's a concrete, testable taxonomy
lever: `taxonomy.yaml`'s FM-1.2 `signals` list doesn't currently mention
"content near-identical to a later turn attributed to a different agent" or
"an agent implied by the task never produces an independent turn" as
detection cues — both are exactly what a second annotator or a taxonomy edit
could sharpen, the same kind of disambiguation lever Lever-1 used for
FM-1.1/FM-1.3.

## Taxonomy edit applied and verified (2026-07-16)

Added exactly those two signals to FM-1.2 in `taxonomy.yaml` (no version bump,
matching how the Lever-1 edits handled it; framework-agnostic wording, no
"Planner/Coder/Tester" naming, per the taxonomy's neutral-schema contract).
Fair game under `held_out.md`'s freeze rule — this data was never part of the
AppWorld/GAIA held-out set.

Re-ran the same 5-run check (`raw_recall_check_post_edit.run{1..5}.json`)
against the updated taxonomy to verify the edit actually helped rather than
just asserting it should:

| trace | FM-1.2 fired, pre-edit | FM-1.2 fired, post-edit |
|---|---|---|
| `rate-limiter` | 1/5 | **5/5** |
| `perf-optimization` | 0/5 | **2/5** |

Local mean recall over these two traces' full label universe (3 gold-positive
cells per run: `rate-limiter`/FM-1.2, `rate-limiter`/FM-3.2,
`perf-optimization`/FM-1.2) rose 0.40 → 0.80, mean κ 0.53 → 0.87 — **and
precision stayed 1.00 in every run, before and after: zero new false
positives introduced.** `rate-limiter` went from barely-detected to reliably
caught every run. `perf-optimization` improved from complete blindness to
2/5 — still imperfect, consistent with the structural read above (no
near-duplicate-content tell available there, only "expected speaker never
appeared," a weaker signal by construction), but a real, validated gain, not
an assumed one.

**Still a single-annotator adjudication** — the same limitation `gold_labels.md`
already states applies here too. A second annotator re-checking these same 3
cells independently, blind to this writeup's verdicts, is the honest next
step before citing the adjudicated 0.65 anywhere.

## Second annotator pass (2026-07-16) — FM-3.2 now disputed

A true second human annotator (the design doc's actual Approach C ask) isn't
available. As a real, if partial, substitute for independence: a fresh
subagent with **no memory of this conversation or any prior labeling
session** was given only `taxonomy.yaml`, the three agents' system messages,
and the raw transcripts of the 3 FM-1.2-present traces (`rate-limiter`,
`pubsub-broker`, `perf-optimization`) — explicitly instructed not to read
`gold_labels.md`, `gold_labels.json`, this file, or run `git log` on the
repo, to avoid seeing any prior conclusion. This is a genuinely independent
read (no shared memory, no exposure to prior verdicts), but it is still an AI
annotator, not the human second annotator Approach C calls for — stated
plainly, not conflated.

**FM-1.2: full agreement, 3/3.** The second pass independently found the same
role violation in all three traces, with evidence chains matching or
exceeding what's documented above — e.g. for `pubsub-broker` it additionally
noted Planner "signed off" on the task as final at least three times (turns
3, 5, 6) before Tester spoke a substantive word, and independently caught
turn 5's name/content mismatch. This meaningfully strengthens confidence in
FM-1.2 and the taxonomy edit built on it (see below).

**FM-3.2: disagreement, 0/2 — now DISPUTED, not resolved either direction.**
The second pass independently rejected both FM-3.2 findings this file upheld:

- `rate-limiter`: read Tester's acknowledged-but-dismissed timing-flakiness
  risk as legitimate verification reasoning ("a reasonable, non-flaky
  judgment call"), not an unexamined gap, and attributed the earlier shallow
  Planner-authored "verification" to the FM-1.2 violation rather than
  double-counting it as a separate failure.
- `pubsub-broker`: called the adversarial suite "genuinely thorough
  regardless of who nominally authored it" and reported no missed bug — it
  did not independently surface the same-topic-reentrant-publish gap this
  file's adjudication is built on.

**Why this isn't being resolved by picking a side:** the FM-3.2 adjudication
above was a single pass by one annotator (me) reasoning toward "the judge
caught something real" — exactly the kind of motivated-reasoning risk
`evals/adjudication.md`'s original methodology built an *adversarial* second
pass to guard against, and no adversarial check was run against my own
FM-3.2 reasoning before this. The second annotator's counter-arguments are
specific and evidence-based, not lazy dismissals — this is a genuine,
defensible disagreement between two single AI passes, not one side being
sloppy. Arbitrarily picking a winner would launder that uncertainty into a
false-confidence number.

**Decision (2026-07-16):** leave `rate-limiter`/FM-3.2 and
`pubsub-broker`/FM-3.2 marked **present** in `gold_labels.json` (i.e. the
adjudicated 0.65 κ figure above is NOT rescored down), but flag both cells
as **disputed** everywhere they're cited. Rationale: reverting to absent
would just substitute one single-annotator's judgment (the fresh pass) for
another's (mine) with no more claim to authority — neither is the human
consensus this really needs. The honest state is "contested," not "resolved
in favor of whichever pass ran last." A true tie-breaker needs either a real
second human annotator, or — better — the underlying ambiguity itself needs
resolving in `taxonomy.yaml`: is "verification that identifies and then
reasons away a risk without empirically resolving it" FM-3.2 by definition,
or a legitimate judgment call? That's a definitional question this project
hasn't had to answer before now, not something one more annotation pass will
settle by majority vote of two.
