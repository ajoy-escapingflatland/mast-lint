# Evals — the credibility harness (Step 4)

The whole product hinges on one question: **why should anyone trust the judge?**
Answer it with a number.

## Plan
1. Collect 30–50 real multi-agent traces (start with your own agent-loop runs).
2. Hand-label each: which of the 14 MAST modes occurred, on which spans.
   Store as `labeled/<trace_id>.labels.json`.
3. Run mast-lint over the same traces.
4. Compute agreement between mast-lint and your labels (Cohen's kappa, per-mode
   precision/recall). The MAST paper's *human* inter-annotator kappa is 0.88 —
   that's the yardstick, not the target.
5. Publish the number in the README and the launch essay. Honesty about where the
   judge is weak is the reason a neutral OSS tool gets trusted.

`labeled/` holds ground-truth labels. `examples/trace.example.json` is the first
seed case (known labels: FM-3.1 + FM-3.2).
