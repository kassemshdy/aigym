"""app/ai/client.py never makes a real network call in this suite — every
test monkeypatches get_client()/messages.parse entirely. This is the
load-bearing decision for the whole AI phase: it keeps every later stage
testable in normal CI for free (see .agents/skills/ai-prompt-eval,
docs/DECISIONS.md decision 32 for the one job that does spend real
money)."""

import uuid
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from app.ai import client as ai_client
from app.settings import get_settings


class _Reply(BaseModel):
    text: str


def test_get_client_raises_when_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("AIGYM_ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ai_client.AnthropicNotConfigured):
        ai_client.get_client()
    get_settings.cache_clear()


def test_get_client_returns_a_client_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AIGYM_ANTHROPIC_API_KEY", "sk-ant-test-key")
    assert isinstance(ai_client.get_client(), anthropic.Anthropic)
    get_settings.cache_clear()


def _fake_response(parsed_output: Any) -> SimpleNamespace:
    return SimpleNamespace(
        parsed_output=parsed_output,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )


def test_run_structured_returns_the_parsed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_client,
        "get_client",
        lambda: SimpleNamespace(
            messages=SimpleNamespace(
                parse=lambda **kwargs: _fake_response(_Reply(text="hi"))
            )
        ),
    )
    result = ai_client.run_structured(
        model="claude-haiku-4-5",
        system="be terse",
        messages=[{"role": "user", "content": "hello"}],
        response_model=_Reply,
        max_tokens=100,
        purpose="test",
        gym_id=uuid.uuid4(),
    )
    assert result == _Reply(text="hi")


def _request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    "make_error",
    [
        lambda: anthropic.APIConnectionError(request=_request()),
        lambda: anthropic.RateLimitError(
            "rate limited", response=httpx2.Response(429, request=_request()), body=None
        ),
        lambda: anthropic.NotFoundError(
            "not found", response=httpx2.Response(404, request=_request()), body=None
        ),
        lambda: anthropic.APIStatusError(
            "server error", response=httpx2.Response(500, request=_request()), body=None
        ),
    ],
)
def test_run_structured_wraps_every_anthropic_failure_as_ai_unavailable(
    monkeypatch: pytest.MonkeyPatch, make_error: Any
) -> None:
    def _raise(**kwargs: Any) -> Any:
        raise make_error()

    monkeypatch.setattr(
        ai_client, "get_client", lambda: SimpleNamespace(messages=SimpleNamespace(parse=_raise))
    )
    with pytest.raises(ai_client.AiUnavailable):
        ai_client.run_structured(
            model="claude-haiku-4-5",
            system="be terse",
            messages=[{"role": "user", "content": "hello"}],
            response_model=_Reply,
            max_tokens=100,
            purpose="test",
            gym_id=uuid.uuid4(),
        )
