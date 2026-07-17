# Dogfood task list (draft, v1) — for review before any API spend

Eight fresh tasks for the AG2 (3-agent Planner/Coder/Tester) dogfood runner
(`run_ag2.py`). None are copied or adapted from AppWorld, GAIA, or any MAD source
framework's benchmark — see `evals/contamination_ceiling.md` for why that matters
(reusing a published benchmark task, even run fresh yourself, risks reproducing a
trace close enough to something in the judge's training data to reintroduce
pretraining-exposure contamination).

**Design principle: organic, not gamed.** These are realistic coding tasks of
varying ambiguity and difficulty. None instructs the agents to fail, and none
is written to force a specific FM to fire — that would bias the eval the same
way grading the judge on traces used to tune the taxonomy did (see
`held_out.md`). The "plausibly exercises" column is a hypothesis about where
organic friction might occur, not a target. If a task produces zero failures,
that's a valid and useful result (a clean-trace control, same value as
`mad-18` in the GAIA held-out set).

All three agents share one `GroupChat` (`auto` speaker selection — the
Group Chat Manager's LLM picks who speaks next, not a fixed round-robin), so
who-talks-when is itself part of what gets captured, not scripted.

| id | plausibly exercises | why |
|---|---|---|
| `linked-list-merge` | (control — expect mostly clean) | simple, fully-specified, low ambiguity |
| `rate-limiter` | FC3 (verification) | "thread-safe" + "burst behavior" are easy to claim tested without real coverage |
| `cache-refactor` | FC1 (spec compliance) | "without changing documented behavior" is ambiguous exactly where the snippet's docstring is silent |
| `csv-report-cli` | FM-2.2 (fail to ask for clarification) | schema is explicitly left unspecified; correct behavior is to ask, not guess |
| `pubsub-broker` | FC3 (verification) | Tester is told to be adversarial about the delivery guarantee — real chance of a claimed-but-unverified pass |
| `state-machine-todo` | FM-2.6 (reasoning-action mismatch) | a pre-existing failing test creates a fork: fix the code or fix the test, and agents may say one while doing the other |
| `perf-optimization` | FM-3.1 (premature termination) | explicit instruction to stop only after Tester confirms, creating a checkable termination condition |
| `raise-vs-none-dispute` | FM-2.1 / FM-2.5 (conversation reset / ignored input) | two agents are told they disagree going in; resolution requires actually engaging with the other's position |

## Next step after this list is approved

Run `run_ag2.py`, then hand-label ground truth on the resulting traces **blind**
(before looking at judge output) — the same discipline `evals/adjudication.md`
used, just applied prospectively instead of retrospectively. That labeling step
is not yet built; scaffolding it is follow-up work once traces actually exist to
label.
