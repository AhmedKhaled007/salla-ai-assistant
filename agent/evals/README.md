# Salla Agent Evaluation Contract

`evaluation_contract.json` is the versioned source of truth for expected agent
behavior. It translates the system prompt and current MCP tool surface into
requirements that later datasets and evaluators can reference by stable ID.

## Action policy

- Read operations may execute when they are relevant to an explicit user request.
- Create and update operations require explicit user intent. They do not require a
  second confirmation under the current product policy, but the agent must ask for
  every missing required field and must not invent values.
- Delete operations require explicit confirmation. No delete MCP tool currently
  exists, so the agent must not substitute another mutation and must explain that
  the operation is unavailable after confirmation.
- A tool call must never be made for an unrelated request or without authorization
  from the user's request.

Changing any of these rules requires a new contract version and corresponding
dataset updates so historical Phoenix experiments remain interpretable.

## Run the offline harness

The harness uses the real LLM and current MCP tool schemas, but executes tools
against `fixtures/synthetic_store.json` instead of the Salla API:

```bash
docker compose --profile eval run --rm eval \
  --query "List the products that are out of stock"
```

Repeat `--query` to run multiple isolated cases. Results are printed as JSON and
traces are written to the `salla-agent-eval` Phoenix project.
