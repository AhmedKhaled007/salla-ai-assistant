"""Shared helpers for the Salla agent evaluation suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.services.mcp_client import MCPClient


EVALS_DIR = Path(__file__).parent
DEFAULT_CASES = EVALS_DIR / "cases.json"
DEFAULT_CONTRACT = EVALS_DIR / "evaluation_contract.json"


async def load_tool_schemas() -> list[dict]:
    client = MCPClient()
    async with client.connect() as connection:
        return await client.get_openai_tools(connection)


def load_and_validate_cases(
    cases_path: Path = DEFAULT_CASES,
    contract_path: Path = DEFAULT_CONTRACT,
) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    valid_requirements = {item["id"] for item in contract["requirements"]}
    required_fields = {
        "case_id",
        "question",
        "expected_tool_sequence",
        "expected_arguments",
        "expected_tool_results",
        "expected_store_state",
        "expected_behavior",
        "allow_mutation",
        "language",
        "category",
        "requirement_ids",
    }
    ids = [case.get("case_id") for case in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be present and unique.")
    for case in cases:
        missing = required_fields - case.keys()
        if missing:
            raise ValueError(f"{case['case_id']} is missing fields: {sorted(missing)}")
        if not case["question"].strip():
            raise ValueError(f"{case['case_id']} has an empty question.")
        sequence_length = len(case["expected_tool_sequence"])
        if sequence_length != len(case["expected_arguments"]):
            raise ValueError(f"{case['case_id']} has mismatched tool arguments.")
        if sequence_length != len(case["expected_tool_results"]):
            raise ValueError(f"{case['case_id']} has mismatched tool results.")
        unknown = set(case["requirement_ids"]) - valid_requirements
        if unknown:
            raise ValueError(f"{case['case_id']} has unknown requirements: {sorted(unknown)}")
    return payload["dataset_name"], cases


def serialize_tool_definitions(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def decode_json(value: Any, default: Any) -> Any:
    if not isinstance(value, str):
        return value if value is not None else default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def contains_expected(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains_expected(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(contains_expected(item, expected_item) for item in actual)
            for expected_item in expected
        )
    return actual == expected


def extract_agent_trajectory(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    tool_calls = []
    tool_responses = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function") or {}
            tool_calls.append({
                "id": tool_call.get("id"),
                "name": function.get("name"),
                "arguments": decode_json(function.get("arguments"), {}),
            })
        if message.get("role") == "tool":
            tool_responses.append({
                "tool_call_id": message.get("tool_call_id"),
                "name": message.get("name"),
                "result": decode_json(message.get("content"), message.get("content")),
            })
    return tool_calls, tool_responses
