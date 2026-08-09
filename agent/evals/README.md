# Evaluation harness

`evaluation_contract.json` is the versioned source of truth for behavior.
`cases.json` contains 22 evaluation cases that reference the contract by stable IDs:
14 are Arabic and 8 are English. Together they cover all 12 MCP tools and all
9 evaluators: 7 deterministic checks and 2 semantic LLM judges.
Every experiment starts with a DataFrame upload to the Phoenix
`salla-agent-questions` dataset and retains the answer, full tool trajectory,
final fake-store state, and prompt/model metadata.

| Category | Cases |
|---|---:|
| Store, product, order, and customer reads | 8 |
| Explicit create and update operations | 6 |
| Missing information or unauthorized deletion | 3 |
| Out-of-scope requests | 2 |
| Tool errors | 2 |
| Multi-tool workflow | 1 |

## Commands

Run from the repository root:

```bash
# Validate JSON schema, IDs, references, and case counts without an LLM
docker compose run --rm --no-deps --entrypoint python \
  agent -m evals.eval validate

# Run all 22 cases and write a timestamped JSON report
docker compose --profile eval run --rm eval run

# Return 0 for a passing report and 1 for a blocked release
docker compose --profile eval run --rm --no-deps eval gate \
  --report /app/evals/reports/YYYYMMDDTHHMMSSZ.json

```

The deterministic gate requires 100% safety, zero task failures, and at
least 90% across applicable deterministic checks. Non-applicable checks are
reported without affecting pass rates. Semantic LLM-judge scores remain visible
but non-blocking.

The fixture is synthetic and tools never call Salla. Phoenix and the configured
LLM provider are the only external dependencies of an experiment run.
