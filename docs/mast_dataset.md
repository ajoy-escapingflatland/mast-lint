# The MAST human-labeled dataset & our adapter

`src/mastlint/adapters/mast.py` ingests the human-annotated traces released with
*Why Do Multi-Agent LLM Systems Fail?* (arXiv:2503.13657). These labels are the
**ground truth for the credibility moat** (roadmap Step 4): the judge's Cohen's κ
is measured against them.

## Getting the data

```bash
python scripts/fetch_mast_data.py     # -> data/MAD_human_labelled_dataset.json (2.6 MB)
```

Source: `mcemri/MAD` on the HuggingFace Hub. Not committed (public but not ours to
redistribute; kept in git-ignored `data/`). A 3-record slice lives in
`tests/fixtures/mad_human_sample.json` for the test suite.

## Record shape

The file is a JSON list of 19 records. Each is a whole run annotated by 3 people:

| field            | type   | notes                                                       |
| ---------------- | ------ | ----------------------------------------------------------- |
| `round`          | str    | `Round 1` / `Round 2` / `Round 3` / `Generlazability` (sic) |
| `mas_name`       | str    | framework: AG2, HyperAgent, AppWorld, ChatDev, MetaGPT, GAIA |
| `benchmark_name` | str    | e.g. `GSM-Plus`, `SWE-Bench-Lite`, `ProgramDev`             |
| `trace_id`       | int    | index within the file                                       |
| `trace`          | str    | the run — JSON for AG2, a semi-structured log blob otherwise |
| `annotations`    | list   | one entry per candidate failure mode (see below)            |

Each `annotations` entry: `{"failure mode": "<num> <name>\n\n<definition>",
"annotator_1": bool, "annotator_2": bool, "annotator_3": bool}`. Labels are
**trace-level** — "did this mode occur anywhere in the run" — not span-level.

## The catch: three taxonomy versions

The taxonomy was still evolving while these were annotated, so the `failure mode`
strings come in **three incompatible label sets**:

| round(s)          | version | # modes | example label                     |
| ----------------- | ------- | ------- | --------------------------------- |
| Round 1           | `v1`    | 18 (4 categories) | `1.1 Poor task constraint compliance` |
| Rounds 2–3        | `v2`    | 17      | `1.5 Step repetition`             |
| Generalizability  | `final` | 14      | `1.3 Step Repetition`             |

The `final` set is exactly the 14 modes in `taxonomy/taxonomy.yaml`. The adapter
normalizes all three onto the canonical `FM-*` ids via `MAST_LABEL_TO_FM`, keyed on
the number-stripped mode name (the same mode carries different numbers per round).

`gold_labels(record)` reports which version each record used in
`MASTGold.taxonomy_version`, so evals can decide whether to mix versions or restrict
to `final`.

## Four modes we deliberately DON'T map

The `v1`/`v2` drafts had finer-grained modes that the final 14 consolidated away.
They map to **no** canonical id and are surfaced in `MASTGold.unmapped` rather than
force-fit (`UNMAPPED_LABELS`):

- `unbatched repetitive execution`
- `backtracking interruption`  — reaches majority in mad-8, mad-9
- `disagreement induced inaction`
- `waiting for known information` — reaches majority in mad-3, mad-4

Forcing these into a final mode would silently inflate agreement on that mode. Keeping
them visible-but-separate is the honest move; anyone recomputing κ can see exactly what
was set aside.

Two further mappings are **merges**, not verbatim renames, and are flagged in
`MERGED_LABELS` so they're auditable:

- `undetected conversation ambiguities and contradictions` → `FM-2.2` (clarification family)
- `lack of critical verification` → `FM-3.3` (weak verification ≈ incorrect verification)

## Trace parsing: AG2 first, others honest

Per the roadmap ("do one adapter end-to-end first"), only **AG2** is parsed into real
per-turn spans — its `trace` is structured JSON (`trajectory` of `{content, role,
name}` messages; agent identity is `name`, and the raw chat role is kept in
`span.meta["ag2_role"]`). Every other framework's `trace` is a log blob passed through
as a single span marked `meta["parsing"] == "raw_unsegmented"`. That marker is the
honest signal that span-level evidence isn't available for those frameworks yet —
their parsers are follow-up work, one framework at a time.
