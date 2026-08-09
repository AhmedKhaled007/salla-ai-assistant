import asyncio
import litellm
from agent.core import settings, logger


async def call_llm(messages: list, tools: list = None, stream: bool = False):
    """
    Call the LLM with exponential backoff retry.

    Args:
        messages: List of message dictionaries
        tools: Optional list of tools in OpenAI format
        stream: Whether to stream the response

    Returns:
        The LLM response or stream iterator
    """
    retry_delay = settings.llm_retry_delay

    for attempt in range(settings.llm_max_retries):
        try:
            # Prepare args
            kwargs = {
                "model": settings.llm_model,
                "messages": messages,
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            if settings.llm_max_tokens:
                kwargs["max_tokens"] = settings.llm_max_tokens

            if stream:
                kwargs["stream"] = True

            response = await litellm.acompletion(**kwargs)

            # If streaming, response is an async generator which we return immediately
            # If not streaming, response is a ModelResponse object
            return response

        except Exception as e:
            if attempt == settings.llm_max_retries - 1:
                logger.error(f"LLM call failed after {settings.llm_max_retries} attempts: {e}")
                raise

            logger.warning(f"LLM call failed (attempt {attempt+1}), retrying in {retry_delay}s: {e}")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
