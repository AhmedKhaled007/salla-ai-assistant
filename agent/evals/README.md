# Evaluation harness

`evaluation_contract.json` is the versioned source of truth for behavior.
`cases.json` contains 22 evaluation cases that reference the contract by stable IDs:
14 are Arabic and 8 are English. Together they cover all 12 MCP tools and 10
evaluators: 6 deterministic checks and 4 LLM judges.
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
docker compose --profile eval run --rm --no-deps eval validate

# Run all 22 cases and write a timestamped JSON report
docker compose --profile eval run --rm eval run

# Return 0 when the report passes the quality thresholds, otherwise 1
docker compose --profile eval run --rm --no-deps eval gate \
  --report /app/evals/reports/YYYYMMDDTHHMMSSZ.json

```

The deterministic quality gate requires 100% safety, zero task failures, and at
least 90% across applicable deterministic checks. Non-applicable checks are
reported without affecting pass rates. All LLM-judge scores remain visible but
non-blocking.

The deterministic checks cover expected tool sequence, expected tool arguments,
final store state, mutation safety, iteration limit, and Arabic response
language. The LLM judges are Phoenix's built-in `tool_selection` and
`tool_invocation` metrics plus the custom response-groundedness and semantic
response-behavior judges. The response-behavior judge owns
clarification and decline evaluation, including their no-tool-call expectation



The fixture is synthetic and tools never call Salla. Phoenix and the configured
LLM provider are the only external dependencies of an experiment run.
