"""Run the versioned Salla agent evaluation cases as a Phoenix experiment."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pandas as pd
from phoenix.client import AsyncClient
from phoenix.client.resources.datasets import Dataset
from phoenix.client.resources.experiments.types import RanExperiment
from phoenix.evals import ClassificationEvaluator, LLM, bind_evaluator

from agent.core.config import settings
from agent.core.observability import agent_turn_span, phoenix_observability
from agent.services.agent_runner import AgentRunner, MAX_ITERATIONS_MESSAGE
from agent.services.prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from evals.fake_mcp import FakeSallaStore
from evals.helpers import (
    contains_expected,
    decode_json,
    extract_agent_trajectory,
    load_and_validate_cases,
    load_tool_schemas,
    serialize_tool_definitions,
)
from evals.reporting import build_experiment_report, gate_exit_code, write_report


EVALS_DIR = Path(__file__).parent
DEFAULT_FIXTURE = EVALS_DIR / "fixtures" / "fake_store_data.json"
REPORTS_DIR = EVALS_DIR / "reports"
MUTATION_TOOLS = {
    "salla_create_product",
    "salla_update_product",
    "salla_create_order",
    "salla_update_order_status",
    "salla_create_customer",
}


async def create_evaluation_dataset(
    phx_client: AsyncClient,
    dataset_name: str,
    cases: list[dict[str, Any]],
) -> Dataset:
    cases_df = pd.DataFrame([
        {
            **case,
            "expected_tool_sequence": json.dumps(case["expected_tool_sequence"]),
            "expected_arguments": json.dumps(case["expected_arguments"], ensure_ascii=False),
            "expected_tool_results": json.dumps(case["expected_tool_results"], ensure_ascii=False),
            "expected_store_state": json.dumps(case["expected_store_state"], ensure_ascii=False),
            "requirement_ids": json.dumps(case["requirement_ids"]),
            "prompt_version": SYSTEM_PROMPT_VERSION,
        }
        for case in cases
    ])
    return await phx_client.datasets.create_dataset(
        name=dataset_name,
        dataframe=cases_df,
        input_keys=["question"],
        output_keys=[
            "expected_tool_sequence",
            "expected_arguments",
            "expected_tool_results",
            "expected_store_state",
            "expected_behavior",
            "allow_mutation",
        ],
        metadata_keys=[
            "language",
            "category",
            "requirement_ids",
            "prompt_version",
        ],
        example_id_key="case_id",
        dataset_description=(
            "Versioned Salla agent evaluation cases executed against a deterministic fake store."
        ),
    )


def expected_tool_sequence_matches(output: dict, expected: dict) -> bool:
    expected_sequence = decode_json(expected.get("expected_tool_sequence"), [])
    actual_sequence = [call.get("name") for call in (output or {}).get("tool_calls", [])]
    return bool(output) and actual_sequence == expected_sequence


def expected_tool_arguments_match(output: dict, expected: dict) -> bool:
    expected_arguments = decode_json(expected.get("expected_arguments"), [])
    actual_calls = (output or {}).get("tool_calls", [])
    return bool(output) and len(actual_calls) == len(expected_arguments) and all(
        contains_expected(
            call.get("arguments", {}).get("params", call.get("arguments", {})),
            arguments,
        )
        for call, arguments in zip(actual_calls, expected_arguments)
    )


def expected_store_state_matches(output: dict, expected: dict) -> bool | dict[str, str]:
    expected_state = decode_json(expected.get("expected_store_state"), {})
    if not expected_state:
        return {"label": "not_applicable"}
    return bool(output) and contains_expected(output.get("store_state"), expected_state)


def mutation_policy_matches(output: dict, expected: dict) -> bool | dict[str, str]:
    allow_mutation = str(expected.get("allow_mutation", "false")).lower() == "true"
    if allow_mutation:
        return {"label": "not_applicable"}
    used_mutation = any(
        call.get("name") in MUTATION_TOOLS
        for call in (output or {}).get("tool_calls", [])
    )
    return bool(output) and not used_mutation


def completed_within_iteration_limit(output: dict) -> bool:
    return bool(output) and not output.get("reached_max_iterations", False)


def clarification_or_decline_matches(output: dict, expected: dict) -> bool | dict[str, str]:
    behavior = expected.get("expected_behavior")
    if behavior not in {"clarify", "decline"}:
        return {"label": "not_applicable"}
    return bool(output) and not output.get("tool_calls") and bool(output.get("answer", "").strip())


def response_language_matches(output: dict, metadata: dict) -> bool | dict[str, str]:
    if metadata.get("language") != "ar":
        return {"label": "not_applicable"}
    if not output:
        return False
    answer = output.get("answer", "")
    return any("\u0600" <= character <= "\u06ff" for character in answer)


def llm_as_judge_response_evaluators():
    judge_llm = LLM(provider="litellm", model=settings.eval_model)
    shared_mapping = {
        "question": lambda row: row["input"]["question"],
        "expected_behavior": lambda row: row["expected"]["expected_behavior"],
        "tool_calls": lambda row: serialize_tool_definitions(
            (row.get("output") or {}).get("tool_calls", [])
        ),
        "tool_results": lambda row: serialize_tool_definitions(
            (row.get("output") or {}).get("tool_responses", [])
        ),
        "answer": lambda row: (row.get("output") or {}).get("answer", ""),
    }
    return [
        bind_evaluator(
            evaluator=ClassificationEvaluator(
                name="response_groundedness",
                llm=judge_llm,
                prompt_template=(
                    "Evaluate whether the Salla merchant assistant's response is grounded "
                    "in what actually happened.\n\n"
                    "User request: {question}\n"
                    "Expected behavior: {expected_behavior}\n"
                    "Executed tool calls: {tool_calls}\n"
                    "Tool results: {tool_results}\n"
                    "Assistant response: {answer}\n\n"
                    "Label correct when factual claims and claims of success or failure are "
                    "supported by the tool results. For clarification or refusal responses, "
                    "label correct when the assistant makes no unsupported claim that an "
                    "operation was completed. Judge meaning, not exact wording."
                ),
                choices={"correct": 1.0, "incorrect": 0.0},
                temperature=0.0,
            ),
            input_mapping=shared_mapping,
        ),
        bind_evaluator(
            evaluator=ClassificationEvaluator(
                name="response_behavior",
                llm=judge_llm,
                prompt_template=(
                    "Evaluate whether the Salla merchant assistant's response follows the "
                    "expected behavior for the user request.\n\n"
                    "User request: {question}\n"
                    "Expected behavior: {expected_behavior}\n"
                    "Assistant response: {answer}\n\n"
                    "Behavior meanings: answer = directly answer or confirm the requested "
                    "operation; explain_error = accurately explain that the operation or "
                    "lookup failed; clarify = ask for the relevant missing information; "
                    "decline = explain that the request is outside Salla store assistance. "
                    "The response should be relevant and use the user's language. Judge "
                    "meaning, not exact wording, and do not re-evaluate tool selection."
                ),
                choices={"correct": 1.0, "incorrect": 0.0},
                temperature=0.0,
            ),
            input_mapping={
                key: shared_mapping[key]
                for key in ("question", "expected_behavior", "answer")
            },
        ),
    ]


async def run_agent(input: dict, *, agent: AgentRunner, tools: list[dict] ,tracer_provider: Any) -> dict:
    question = input["question"]
    conversation_id = f"eval-{uuid4()}"
    store = FakeSallaStore(DEFAULT_FIXTURE)
    with agent_turn_span(
        tracer_provider,
        conversation_id=conversation_id,
        query=question,
        model=settings.llm_model,
        prompt_version=SYSTEM_PROMPT_VERSION,
        mode="evaluation",
    ) as span:
        result = await agent.run(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            tools,
            store.execute_tool,
        )
        answer = result[-1].get("content") or ""
        if span is not None:
            span.set_output(answer, mime_type="text/plain")
    tool_calls, tool_responses = extract_agent_trajectory(result)
    return {
        "answer": answer,
        "conversation_id": conversation_id,
        "tool_calls": tool_calls,
        "tool_responses": tool_responses,
        "path_length": len(tool_calls),
        "reached_max_iterations": answer == MAX_ITERATIONS_MESSAGE,
        "store_state": store.data,
    }


async def run_agent_experiment(
    phx_client: AsyncClient,
    dataset: Dataset,
) -> RanExperiment:
    tools = await load_tool_schemas()
    with phoenix_observability(settings) as tracer_provider:
        agent = AgentRunner(tracer_provider=tracer_provider)
        task = partial(
            run_agent,
            agent=agent,
            tools=tools,
            tracer_provider=tracer_provider,
        )

        return await phx_client.experiments.run_experiment(
            dataset=dataset,
            task=task,
            evaluators=[
                expected_tool_sequence_matches,
                expected_tool_arguments_match,
                expected_store_state_matches,
                mutation_policy_matches,
                completed_within_iteration_limit,
                clarification_or_decline_matches,
                response_language_matches,
                *llm_as_judge_response_evaluators(),
            ],
            experiment_name=(
                f"Salla agent | {settings.llm_model} | prompt {SYSTEM_PROMPT_VERSION}"
            ),
            experiment_description=(
                "Runs the Salla agent against a deterministic fake merchant store."
            ),
            experiment_metadata={
                "agent_model": settings.llm_model,
                "eval_model": settings.eval_model,
                "prompt_version": SYSTEM_PROMPT_VERSION,
                "trace_project": settings.phoenix_project_name,
            },
            concurrency=1,
            timeout=None,
            retries=0,
        )


async def run(report_path: Path | None) -> dict[str, Any]:
    dataset_name, cases = load_and_validate_cases()
    async with httpx.AsyncClient(base_url=settings.phoenix_base_url) as http_client:
        phx_client = AsyncClient(http_client=http_client)
        dataset = await create_evaluation_dataset(phx_client, dataset_name, cases)
        print(
            f"Uploaded {len(dataset.examples)} cases to {dataset.name!r} "
            f"(version {dataset.version_id})"
        )
        ran_experiment = await run_agent_experiment(phx_client, dataset)
    report = build_experiment_report(ran_experiment, dataset, cases)
    if report_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = REPORTS_DIR / f"{timestamp}.json"
    write_report(report, report_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report written to {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Run a Phoenix experiment.")
    run_parser.add_argument("--report", type=Path)
    subparsers.add_parser("validate", help="Validate evaluation cases without an LLM.")
    gate_parser = subparsers.add_parser("gate", help="Apply the release gate to a report.")
    gate_parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    command = args.command or "run"
    if command == "validate":
        _, cases = load_and_validate_cases()
        print(f"Evaluation cases valid: {len(cases)} unique cases")
        return
    if command == "gate":
        report = json.loads(args.report.read_text(encoding="utf-8"))
        exit_code = gate_exit_code(report)
        print(json.dumps(report.get("gate", {}), indent=2))
        raise SystemExit(exit_code)
    asyncio.run(run(args.report if args.command else None))


if __name__ == "__main__":
    main()
