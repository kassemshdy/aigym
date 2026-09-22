"""The only place app/ code constructs an anthropic.Anthropic client or
calls .messages.*. Every caller goes through run_structured() so error
handling, logging, and the "no API key configured" case are handled once,
not once per feature. Structured outputs (client.messages.parse) are used
throughout instead of prompt-begged JSON, per this project's own
claude-api skill defaults — see docs/DECISIONS.md, decision 29.
"""

import logging
import time
import uuid
from typing import TypeVar

import anthropic
from anthropic.types import MessageParam, TextBlockParam
from pydantic import BaseModel

from app.settings import get_settings

logger = logging.getLogger("aigym.ai")

T = TypeVar("T", bound=BaseModel)


class AnthropicNotConfigured(Exception):
    """AIGYM_ANTHROPIC_API_KEY is unset. Callers turn this into a 503,
    never a 500 — a deployment without the key yet is a real, expected
    state (same pattern as the WhatsApp Business API credentials,
    decision 20), not a bug."""


class AiUnavailable(Exception):
    """Any Anthropic API failure (rate limit, 5xx, connection error, an
    unrecognized model) a caller should surface as temporarily
    unavailable — never a 500 that looks like a bug in our own code."""


def get_client() -> anthropic.Anthropic:
    api_key = get_settings().anthropic_api_key
    if not api_key:
        raise AnthropicNotConfigured("AIGYM_ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def run_structured(
    *,
    model: str,
    system: str | list[TextBlockParam],
    messages: list[MessageParam],
    response_model: type[T],
    max_tokens: int,
    purpose: str,
    gym_id: uuid.UUID,
) -> T:
    """One call in, one validated pydantic instance out. Logs a single
    structured JSON line per call (app/logging.py's JsonFormatter) — this
    phase's whole observability story; Sentry AI tracing is a documented
    fast-follow (decision 29)."""
    client = get_client()
    started = time.monotonic()
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_format=response_model,
        )
    except anthropic.NotFoundError as exc:
        raise AiUnavailable(f"model not found: {model}") from exc
    except anthropic.RateLimitError as exc:
        raise AiUnavailable("rate limited") from exc
    except anthropic.APIStatusError as exc:
        raise AiUnavailable(f"API error: {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:
        raise AiUnavailable("connection error") from exc

    logger.info(
        "ai_call",
        extra={
            "gym_id": str(gym_id),
            "model": model,
            "purpose": purpose,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "stop_reason": response.stop_reason,
        },
    )
    if response.parsed_output is None:
        raise AiUnavailable("model did not return a parseable structured response")
    return response.parsed_output
