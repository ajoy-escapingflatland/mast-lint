# Design decisions & open forks

The code is the easy part. These four decisions determine whether `mast-lint` is
credible and adoptable. Fork 1 and the credibility question are the ones to get right.

## Fork 1 — What is a "trace"? (the input contract) — DECIDED

**Decision: the canonical internal format is OTel-GenAI-shaped and framework-agnostic
(`schema.py`). Frameworks are supported via thin adapters that translate INTO it.**

Alternatives considered:
- *Framework-native inputs (LangGraph/CrewAI/AutoGen each parsed directly).* Rejected
  as the primary format: N parsers, N sources of churn, and no shared vocabulary for
  the judge.
- *OpenTelemetry GenAI semantic conventions as canonical.* Chosen. It's framework-
  neutral, it's where the ecosystem is heading, and — importantly — it composes with
  the separate "trace-context propagation spec" play: the format `mast-lint` consumes
  is the one worth pushing OTel to standardize. Cost: an adapter per framework.

Consequence: **do one adapter end-to-end first** (Step 2), for whichever framework has
the most public traces / loudest pain. Universal-from-day-one is the trap that stalls
weekend projects.

## Fork 2 — How does classification work?

**Leaning: LLM-as-judge is the core.** The failure modes are semantic ("information
withholding", "reasoning-action mismatch") — no regex detects them. A few modes have
cheap structural pre-checks that can raise precision or pre-filter (e.g. FM-1.3 Step
Repetition ≈ near-duplicate spans; FM-3.2 No Verification ≈ absence of any
test/review span). Use those as hints to the judge, not as the classifier.

Open sub-question: one judge call over the whole trace vs. one call per mode vs. per
window. Start with the whole trace + all modes in one pass; split only if accuracy or
context limits force it.

## Fork 3 — Who evaluates the evaluator? (the credibility moat) — MUST-DO

An LLM judge with no validation is a toy. The differentiator is a published agreement
number: label 30–50 real traces by hand, measure Cohen's κ (and per-mode
precision/recall) between `mast-lint` and those labels. Human κ in the MAST paper is
0.88 — the yardstick, not the target. This number goes in the README and the launch
essay. Honesty about weak modes is the credibility, not a caveat to hide. See
`evals/README.md`.

## Fork 4 — Offline first, integrations later — DECIDED

v0 is an offline CLI over exported traces. No live/CI/production hooks until the judge
is trustworthy. A Langfuse/OTel-backend reader and a CI mode are post-v0, demand-driven.

## Explicit non-goals

- Not a runtime guard, firewall, router, or policy enforcer. Measurement only.
- Not an observability *backend* (that fight is funded and incumbent-held). `mast-lint`
  reads traces; it doesn't store or visualize them at scale.
- Not a live leaderboard to babysit. Benchmarks ship as annually versioned releases.
- Nothing touching agent content-ops or commerce (keeps the project clear of the
  maintainer's employer's domain).

## Naming

`mast-lint` is a working name (MAST + "linter for agent traces"). Fine to rename before
a public launch; if so, rename the package `mastlint` and the `mast-lint` CLI entry
point together.
