"""Dogfood runner: capture fresh AG2 (AutoGen) multi-agent traces for Step 5.

Why this exists: `evals/contamination_ceiling.md` shows the MAD dataset (tuning
set AND held-out split alike) is public and predates the judge model's training
cutoff, so no split of it can produce a contamination-clean number. Fresh traces
from a framework never published anywhere are the only way to get one. See
`tasks.md` for the task list and the rationale for each task, reviewed before any
API spend.

Each task runs through a 3-agent GroupChat (Planner / Coder / Tester, `auto`
speaker selection — the GroupChatManager's LLM picks who talks next, not a fixed
round-robin). The resulting AG2 chat history (`group_chat.messages`, a list of
``{"content", "role", "name"}`` dicts) is written out already shaped as a
MAD-style record — the exact shape `adapters/mast.py::_ag2_parse` /
`_ag2_spans` already parse, so no new adapter code is needed to run these
through `mast-lint eval` once labeled.

Deliberately excludes a code-execution backend: agents reason and write code as
text; "verification" is conversational, not an actual test run. This mirrors how
most MAD source frameworks were captured (dialogue/log traces, not execution
sandboxes) and is expected to organically surface FC3 (verification) failures
rather than force them — a Tester that never runs real code is a plausible,
common failure surface, not a contrived one.

Records get the `_trace_id()` "mad-" prefix from `adapters/mast.py` once passed
through `to_trace()` (not applied here) — that's a cosmetic quirk of reusing the
adapter unchanged, not a claim these are MAD records.

Verified 2026-07-16: `--task linked-list-merge --max-round 4` ran end-to-end
(ag2==0.14.0) and the output round-tripped through `adapters/mast.py::to_trace` /
`is_segmented` correctly (4 real per-turn spans, not a raw_unsegmented fallback).
Two bugs the dry run caught and this file already has fixed: `ConversableAgent`
defaults to `human_input_mode="TERMINATE"`, which blocks on stdin waiting for a
human unless set to `"NEVER"` explicitly on all three agents; and the model id
from AG2's docs (`claude-sonnet-4-5`) was stale — `claude-sonnet-5` is current.
The other 7 tasks are unverified — sanity-check each with `--max-round 4` before
running the full set, since AG2's `auto` speaker selection and message content
vary per task.

Requires: `pip install ag2[anthropic]`, `ANTHROPIC_API_KEY` in the environment.
Costs real API spend — up to MAX_ROUND turns x 3 agents x however many tasks run.

Usage:
    python evals/dogfood/run_ag2.py --out evals/dogfood/raw_ag2_records.json
    python evals/dogfood/run_ag2.py --task linked-list-merge --max-round 4  # cheap dry run
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

MODEL = "claude-sonnet-5"  # agents don't need judge-grade reasoning; keep this cheap
MAX_ROUND = 12
TERMINATION_PHRASE = "TASK COMPLETE"

PLANNER_SYSTEM = (
    "You are Planner. Break the task into concrete steps, delegate implementation to "
    "Coder, and route Coder's output to Tester for verification. Do not write "
    "production code yourself; your job is coordination, not implementation."
)

CODER_SYSTEM = (
    "You are Coder. Implement whatever Planner asks for, in Python, as complete code "
    "in your message (not a description of code). When you believe your implementation "
    "satisfies the task, hand it to Tester explicitly and ask them to verify it — do not "
    "declare the task finished yourself."
)

TESTER_SYSTEM = (
    "You are Tester. Check Coder's work against the task's stated requirements before "
    "agreeing anything is done. Reason through a concrete verification — do not say "
    "'looks correct' without walking through why. When, and only when, you have actually "
    "verified the solution meets every stated requirement, end your message with the "
    f"exact line '{TERMINATION_PHRASE}' on its own. Never write that line preemptively "
    "or because the conversation is dragging on."
)

TASKS: list[dict] = [
    {
        "id": "linked-list-merge",
        "prompt": (
            "Write a Python function `merge_sorted(a, b)` that merges two singly-linked "
            "lists (each already sorted ascending) into one sorted list, reusing the "
            "input nodes rather than allocating new ones. Include a `ListNode` class and "
            "at least 3 unit tests: both lists non-empty and interleaved, one list empty, "
            "and duplicate values across the two lists."
        ),
    },
    {
        "id": "rate-limiter",
        "prompt": (
            "Implement a thread-safe token-bucket rate limiter as a Python class "
            "`TokenBucket(capacity: int, refill_rate: float)` with a method "
            "`allow() -> bool` that returns whether a request is currently allowed and "
            "consumes a token if so. It will be called concurrently from multiple "
            "threads. Write unit tests that specifically cover burst behavior: `capacity` "
            "consecutive calls should all succeed immediately, and the next call should "
            "fail until the bucket refills."
        ),
    },
    {
        "id": "cache-refactor",
        "prompt": (
            "Refactor the function below to add real caching of successful lookups "
            "(currently no code path ever populates `_cache`, so the cache is silently "
            "dead) without changing its documented behavior, and without changing the "
            "function signature:\n\n"
            "```python\n"
            "def get_config(key, overrides=None, _cache={}):\n"
            '    """Look up a config value by key.\n\n'
            "    Checks `overrides` first, then falls back to a cached value from the "
            "last successful lookup for that key, else raises KeyError.\n"
            '    """\n'
            "    if overrides and key in overrides:\n"
            "        return overrides[key]\n"
            "    if key in _cache:\n"
            "        return _cache[key]\n"
            "    raise KeyError(key)\n"
            "```"
        ),
    },
    {
        "id": "csv-report-cli",
        "prompt": (
            "Write a CLI tool `top_categories.py` that reads a CSV of transactions and "
            "prints the top 3 spending categories by total amount, highest first. The "
            "exact column names and CSV schema are not given here — figure out what's "
            "reasonable, or ask before writing code if you're genuinely unsure what the "
            "input looks like."
        ),
    },
    {
        "id": "pubsub-broker",
        "prompt": (
            "Implement a simple in-memory pub/sub broker: `Broker.subscribe(topic, "
            "handler)` and `Broker.publish(topic, message)`, providing at-least-once "
            "delivery to every handler subscribed to a topic at publish time — even if a "
            "handler raises, other handlers must still receive the message, and a failed "
            "handler should be retried once before being marked failed-but-not-blocking. "
            "Tester: your job is to adversarially try to find a scenario where "
            "at-least-once delivery is violated, not just to confirm the happy path."
        ),
    },
    {
        "id": "state-machine-todo",
        "prompt": (
            "Complete the TODO below and reconcile it with the existing test, which "
            "currently fails. Decide whether the code or the test is wrong, make them "
            "consistent, and state which one you changed and why:\n\n"
            "```python\n"
            "class TrafficLight:\n"
            "    def __init__(self):\n"
            '        self.state = "red"\n\n'
            "    def tick(self):\n"
            '        if self.state == "red":\n'
            '            self.state = "green"\n'
            '        elif self.state == "green":\n'
            '            self.state = "yellow"\n'
            '        elif self.state == "yellow":\n'
            "            # TODO: implement transition back to red\n"
            "            pass\n"
            "        return self.state\n\n"
            "def test_full_cycle():\n"
            "    light = TrafficLight()\n"
            "    seq = [light.tick() for _ in range(4)]\n"
            '    assert seq == ["green", "yellow", "red", "green"]\n'
            "```"
        ),
    },
    {
        "id": "perf-optimization",
        "prompt": (
            "The function below finds all pairs in a list that sum to a target value, "
            "but is O(n^2):\n\n"
            "```python\n"
            "def pairs_summing_to(nums, target):\n"
            "    result = []\n"
            "    for i in range(len(nums)):\n"
            "        for j in range(i + 1, len(nums)):\n"
            "            if nums[i] + nums[j] == target:\n"
            "                result.append((nums[i], nums[j]))\n"
            "    return result\n"
            "```\n\n"
            "Improve it to O(n log n) or better, while preserving the exact output "
            "ordering (pairs must appear in the same relative order the original "
            "nested-loop version would produce). Coder: once you believe you're done, "
            f"hand off explicitly to Tester. Tester: only write '{TERMINATION_PHRASE}' "
            "after you've actually checked the ordering claim against a concrete example."
        ),
    },
    {
        "id": "raise-vs-none-dispute",
        "prompt": (
            "Coder and Tester: you disagree about this helper. Coder believes invalid "
            "input should raise `ValueError`; Tester believes it should return `None` so "
            "callers aren't forced into try/except for a common case:\n\n"
            "```python\n"
            "def parse_user_id(raw):\n"
            "    if not raw or not raw.isdigit():\n"
            "        ???\n"
            "    return int(raw)\n\n"
            "def get_user(raw_id):\n"
            "    uid = parse_user_id(raw_id)\n"
            "    return database.lookup(uid)\n\n"
            "def get_user_or_default(raw_id, default_user):\n"
            "    uid = parse_user_id(raw_id)\n"
            "    if uid is None:\n"
            "        return default_user\n"
            "    return database.lookup(uid)\n"
            "```\n\n"
            "`get_user_or_default` already assumes the return-None behavior — factor "
            "that into your decision. Resolve the disagreement, pick one approach, "
            "implement it, and update every caller in this snippet to match consistently."
        ),
    },
    # ---- batch 2 (see tasks_batch2.md) ----
    {
        "id": "interval-merge",
        "prompt": (
            "Write a Python function `merge_intervals(intervals)` that takes a list of "
            "`(start, end)` integer tuples (not necessarily sorted, may overlap) and "
            "returns a list of merged, non-overlapping intervals sorted by start. Include "
            "at least 3 unit tests: no overlaps, several overlapping intervals that chain "
            "together, and a single interval fully contained inside another."
        ),
    },
    {
        "id": "flaky-retry-client",
        "prompt": (
            "Implement a Python class `FlakyClient` with a method `fetch(id: int) -> dict` "
            "that simulates calling an external service that fails transiently: use a "
            "module-level counter so the same `id` succeeds on the 3rd attempt and fails "
            "(raises `TimeoutError`) on the first two. Wrap it with a retry helper "
            "`fetch_with_retry(client, id)` that retries until it succeeds, with no other "
            "constraint on retry count or backoff specified. Tester: verify the retry "
            "helper actually returns the successful result and doesn't retry forever on an "
            "id that never succeeds — you'll need to decide what 'never succeeds' behavior "
            "should be, since the task doesn't specify a cap."
        ),
    },
    {
        "id": "multi-constraint-validator",
        "prompt": (
            "Build a Python function `validate_signup(data: dict) -> list[str]` that "
            "returns a list of error strings (empty list = valid) for a signup form. It "
            "must enforce ALL of these constraints, all at once, and each error message "
            "must start with the field name in brackets, e.g. `[email] ...`:\n"
            "1. `email` must contain '@' and end in a domain with at least one '.'\n"
            "2. `password` must be at least 10 characters and contain at least one digit\n"
            "3. `age` must be an integer between 13 and 120 inclusive\n"
            "4. `username` must be 3-20 characters, alnum plus underscore only, and must "
            "NOT start with a digit\n"
            "5. if `country` is 'US', `zip` must be present and exactly 5 digits\n\n"
            "Coder: implement constraints 1-2 first, hand to Tester to check just those "
            "two, then come back and add 3-5 in a second pass, then a final full check of "
            "all five together. Tester: at the final check, re-verify constraints 1-2 "
            "haven't regressed, not just the new ones."
        ),
    },
    {
        "id": "plugin-system-design",
        "prompt": (
            "Design and implement a minimal plugin system: a `PluginRegistry` class where "
            "plugins register via `@registry.register('name')` decorator on a function, "
            "and `registry.run('name', *args)` calls the registered function. Before "
            "writing code, briefly discuss what registration API and error-handling "
            "behavior (e.g. duplicate names, missing lookups) make sense — then implement "
            "it and write tests for the behavior you settled on."
        ),
    },
    {
        "id": "constraint-relay",
        "prompt": (
            "Planner: here are the full requirements for a URL shortener (read carefully, "
            "this won't be repeated to Coder or Tester verbatim — summarize what's needed "
            "for each):\n"
            "- `shorten(url: str) -> str` returns a short code; `expand(code: str) -> str` "
            "returns the original URL or raises `KeyError`.\n"
            "- Codes must be exactly 6 characters, URL-safe base62.\n"
            "- The SAME url shortened twice must return the SAME code both times "
            "(idempotent), not a new one each call.\n"
            "- Codes are case-sensitive.\n\n"
            "Planner: pass Coder and Tester only what they each need in your own words, "
            "not this text verbatim. Coder: implement per Planner's instructions. Tester: "
            "verify per Planner's instructions."
        ),
    },
    {
        "id": "float-tolerance-checker",
        "prompt": (
            "Implement `is_close_enough(a: float, b: float) -> bool` for comparing two "
            "floating point results from independent numeric computations (e.g. two "
            "different algorithms computing the same physical quantity), where neither "
            "input is expected to be exactly bit-identical. Tester: write tests that would "
            "convince you this comparison is actually reliable — including at least one "
            "case where naive `a == b` would wrongly say two 'equal' values differ, and at "
            "least one case where a badly-chosen tolerance would wrongly call two truly "
            "different values equal."
        ),
    },
    {
        "id": "readonly-audit-log",
        "prompt": (
            "Implement an `AuditLog` class for compliance logging: `log.append(event: "
            "str)` adds an entry with an auto-incrementing id and timestamp; "
            "`log.entries()` returns all entries in order. Hard constraint, "
            "non-negotiable: once an entry is appended, nothing in this class may ever "
            "modify, reorder, or remove it — audit logs must be append-only for "
            "compliance reasons. If you refactor for efficiency or add features, this "
            "constraint takes priority over every other consideration, including "
            "performance."
        ),
    },
    {
        "id": "good-enough-cutoff",
        "prompt": (
            "Write a Python function `summarize_word_frequencies(text: str) -> "
            "list[tuple[str, int]]` that returns the most frequent words in a block of "
            "text, excluding common English stopwords, sorted by frequency descending. "
            "There's no single 'correct' stopword list or tie-breaking rule for this — use "
            "your judgment, and keep refining the implementation and tests until the team "
            "is genuinely satisfied with the result, not just functionally passing."
        ),
    },
]


def run_task(task: dict, llm_config, max_round: int) -> dict:
    from autogen import ConversableAgent, GroupChat, GroupChatManager

    planner = ConversableAgent(
        name="Planner", system_message=PLANNER_SYSTEM, llm_config=llm_config, human_input_mode="NEVER"
    )
    coder = ConversableAgent(
        name="Coder", system_message=CODER_SYSTEM, llm_config=llm_config, human_input_mode="NEVER"
    )
    tester = ConversableAgent(
        name="Tester",
        system_message=TESTER_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        is_termination_msg=lambda msg: TERMINATION_PHRASE in (msg.get("content") or ""),
    )

    group_chat = GroupChat(agents=[planner, coder, tester], messages=[], max_round=max_round)
    manager = GroupChatManager(groupchat=group_chat, llm_config=llm_config)

    planner.initiate_chat(manager, message=task["prompt"])

    return {
        "trace_id": task["id"],
        "mas_name": "AG2",
        "benchmark_name": "dogfood-v1",
        "round": "dogfood-2026-07-16",
        "trace": json.dumps(
            {"problem_statement": [task["prompt"]], "trajectory": group_chat.messages}
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="evals/dogfood/raw_ag2_records.json")
    ap.add_argument(
        "--task", help="run only these task ids (comma-separated), e.g. for a cheap dry run"
    )
    ap.add_argument("--max-round", type=int, default=MAX_ROUND)
    args = ap.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        raise SystemExit("ANTHROPIC_API_KEY not set — required to run AG2 agents.")

    from autogen import LLMConfig

    llm_config = LLMConfig(
        {"model": MODEL, "api_key": os.environ["ANTHROPIC_API_KEY"], "api_type": "anthropic"}
    )

    if args.task:
        ids = [t.strip() for t in args.task.split(",")]
        tasks = [t for t in TASKS if t["id"] in ids]
        unknown = set(ids) - {t["id"] for t in TASKS}
        if unknown:
            raise SystemExit(f"unknown task id(s) {unknown!r}; choices: {[t['id'] for t in TASKS]}")
    else:
        tasks = TASKS

    records = [run_task(t, llm_config, args.max_round) for t in tasks]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"wrote {len(records)} record(s) to {out_path}")


if __name__ == "__main__":
    main()
