"""Phoenix tracing lifecycle for the agent service."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from openinference.instrumentation.litellm import LiteLLMInstrumentor
from phoenix.otel import SpanAttributes, TracerProvider, register, using_session

from agent.core.config import Settings
from agent.core.logger import logger


@contextmanager
def agent_turn_span(
    tracer_provider: TracerProvider | None,
    *,
    conversation_id: str,
    query: str,
    model: str,
    prompt_version: str,
    mode: str,
) -> Iterator[Any | None]:
    """Trace one user turn and group it into its conversation session."""
    if tracer_provider is None:
        yield None
        return

    tracer = tracer_provider.get_tracer("salla-agent")
    attributes = {
        SpanAttributes.SESSION_ID: conversation_id,
        "agent.model": model,
        "agent.mode": mode,
        "agent.prompt.version": prompt_version,
    }
    with using_session(conversation_id):
        with tracer.start_as_current_span(
            "salla-agent",
            openinference_span_kind="agent",
            attributes=attributes,
        ) as span:
            span.set_input(query, mime_type="text/plain")
            yield span


@contextmanager
def tool_call_span(
    tracer_provider: TracerProvider | None,
    tool_name: str,
    arguments: dict,
) -> Iterator[Any | None]:
    """Trace an MCP tool call beneath the current agent span."""
    if tracer_provider is None:
        yield None
        return

    tracer = tracer_provider.get_tracer("salla-agent")
    attributes = {
        "tool.name": tool_name,
    }
    with tracer.start_as_current_span(
        f"mcp.{tool_name}",
        openinference_span_kind="tool",
        attributes=attributes,
    ) as span:
        span.set_input(arguments, mime_type="application/json")
        yield span


def _shutdown_observability(
    tracer_provider: TracerProvider | None,
    instrumentor: LiteLLMInstrumentor | None,
) -> None:
    """Remove instrumentation and flush pending spans without raising."""
    if instrumentor is not None:
        try:
            instrumentor.uninstrument()
        except Exception:
            logger.exception("Failed to remove LiteLLM instrumentation")

    if tracer_provider is not None:
        try:
            tracer_provider.force_flush(timeout_millis=5_000)
            tracer_provider.shutdown()
        except Exception:
            logger.exception("Failed to flush Phoenix traces during shutdown")


@contextmanager
def phoenix_observability(
    config: Settings,
) -> Iterator[TracerProvider | None]:
    """Provide a fail-open Phoenix tracing lifecycle for the application."""
    if not config.phoenix_enabled:
        logger.info("Phoenix tracing is disabled")
        yield None
        return
    if not config.phoenix_collector_endpoint:
        logger.warning(
            "Phoenix tracing is enabled without PHOENIX_COLLECTOR_ENDPOINT"
        )
        yield None
        return

    tracer_provider: TracerProvider | None = None
    instrumentor: LiteLLMInstrumentor | None = None
    try:
        tracer_provider = register(
            endpoint=config.phoenix_collector_endpoint,
            project_name=config.phoenix_project_name,
            batch=True,
            verbose=False,
            set_global_tracer_provider=False,
        )
        instrumentor = LiteLLMInstrumentor()
        instrumentor.instrument(tracer_provider=tracer_provider)
    except Exception:
        logger.exception("Phoenix tracing initialization failed; continuing without it")
        _shutdown_observability(tracer_provider, instrumentor)
        yield None
        return

    logger.info(
        "Phoenix tracing initialized for project %s",
        config.phoenix_project_name,
    )
    try:
        yield tracer_provider
    finally:
        _shutdown_observability(tracer_provider, instrumentor)
