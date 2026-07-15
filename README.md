# mast-lint

**A linter for multi-agent LLM traces.** Point it at a trace of a multi-agent run
and it tells you *which* of the 14 [MAST](https://arxiv.org/abs/2503.13657) failure
modes occurred, and *where* — with the offending spans quoted back to you.

> Multi-agent LLM systems fail in recurring, structural ways — premature termination,
> information withheld between agents, work that's never verified. MAST catalogs 14 of
> them. `mast-lint` finds them in your traces so you can stop guessing why your agents
> underperform a single agent.

```
$ mast-lint modes
FM-1.1   Disobey Task Specification       [FC1]
FM-1.2   Disobey Role Specification       [FC1]
...
FM-3.1   Premature Termination            [FC3]

$ mast-lint lint my_run.json
FM-3.1  Premature Termination   (span s4)  — planner declared done before the tester ran
FM-3.2  No/Incomplete Verification (s2–s4) — no test was ever written or executed
```

## Status

**Early — Step 1 of 5.** The taxonomy, the canonical trace schema, and the CLI
skeleton exist. The LLM judge is not wired yet (returns empty reports). See
[`CLAUDE.md`](./CLAUDE.md) for the architecture and roadmap, and
[`docs/design.md`](./docs/design.md) for the design decisions.

## Why this exists

Practitioners report **quality — not cost or latency — as the #1 barrier** to putting
agents in production, yet most eval tooling assumes a single agent. The failures that
matter in multi-agent systems live *between* agents, and they're invisible to
single-turn evals. `mast-lint` makes them visible, framework-agnostically, as an open
tool anyone can run.

Design principle: **measurement layer, never runtime layer.** `mast-lint` observes
traces after the fact. It never sits in an enforcement or auth path.

## How it works

```
trace file → [adapter] → canonical Trace → segment → LLM-as-judge (per MAST mode) → Report
```

The 14 modes with operational definitions and worked examples live in
[`taxonomy/taxonomy.yaml`](./taxonomy/taxonomy.yaml) — the heart of the project. Judge
prompts are rendered from it.

## Install (dev)

```bash
git clone <repo> && cd mast-lint
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mast-lint modes                       # works today
mast-lint lint examples/trace.example.json   # parses; judge lands in Step 3
pytest
```

## Trusting the judge

Because the classifier is an LLM, the project ships a **credibility number**: agreement
(Cohen's κ) between `mast-lint` and hand-labeled traces. The MAST paper's *human*
inter-annotator agreement is κ=0.88 — that's the yardstick. See
[`evals/README.md`](./evals/README.md).

## Credit

Taxonomy from Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (arXiv:2503.13657).
`mast-lint` is an independent open-source implementation of that taxonomy as a tool; it
is not affiliated with the paper's authors.

## License

Apache-2.0.
