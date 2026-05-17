# Legal Quality Evals

This folder contains structured regression cases for the legal RAG pipeline.

Use these evals when adding new legal domains or changing retrieval, prompts,
chunking, embeddings, reranking, or answer logic.

Case groups:
- `retrieval`: verifies the right legal source/chunk appears in search results.
- `answer`: verifies the final answer includes required legal facts and avoids
  known bad phrases.
- `calculation`: reserved for deterministic legal calculations; currently empty
  because this demo scope is military-service law.

Group labels inside the JSON cases are used to cluster scenarios by domain,
such as `military.age`, `military.deferment`, `military.health`,
`military.penalty`, `military.gender`, and `military.discharge`.

To run only a subset of groups, set `EVAL_GROUPS`:

```bash
EVAL_GROUPS=military.health,military.penalty uv run pytest tests/test_quality_eval.py -q
```

Run locally:

```bash
uv run pytest tests/test_quality_eval.py -q
```

Or use:

```bash
make eval
```

## Draft Generator

When adding many new legal documents, use the draft generator to create candidate
eval cases before manually reviewing them:

```bash
make eval-generate
```

By default this scans `data/*.txt` and writes `evals/generated_candidates.json`.
The generated file is ignored by git on purpose. Review the draft cases, keep the
ones that represent important domain behavior, then copy those selected cases
into `evals/legal_quality_cases.json`.

Generated drafts are not loaded by the regression suite by default. To run a
reviewed generated file explicitly:

```bash
INCLUDE_GENERATED_EVALS=1 GENERATED_EVAL_CASES_PATH=evals/generated_cases.json uv run pytest tests/test_quality_eval.py -q
```

To scan one file:

```bash
uv run python scripts/generate_eval_candidates.py --file nghia-vu-quan-su-curated-luat-hop-nhat-80-2025.txt
```

When a user finds a wrong answer, add the question here first, define the
expected evidence or answer constraints, then fix the pipeline until the eval
passes.
