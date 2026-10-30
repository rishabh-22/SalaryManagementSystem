"""LLM provider adapters for the chat agent: Anthropic or OpenAI, picked by USE_ANTHROPIC_KEY.

Each session keeps its provider's native message format; the agent loop only sees ToolCall/Turn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import openai

from app.core.config import settings
from app.services.chat_tools import TOOL_SCHEMAS

_REQUEST_TIMEOUT_SECONDS = 30


class ChatNotConfiguredError(Exception):
    """The selected provider's API key is not set."""


class ChatUpstreamError(Exception):
    """The provider API call failed."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]
    error: str | None = None


@dataclass(frozen=True)
class ToolResult:
    call: ToolCall
    content: str
    is_error: bool


@dataclass(frozen=True)
class Turn:
    text: str
    tool_calls: list[ToolCall]


class ChatSession(Protocol):
    def step(self) -> Turn:
        """One model call. Remembers the assistant message so tool results can follow."""

    def add_tool_results(self, results: list[ToolResult]) -> None: ...


def get_anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY, timeout=_REQUEST_TIMEOUT_SECONDS, max_retries=1
    )


def get_openai_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=settings.OPENAI_API_KEY, timeout=_REQUEST_TIMEOUT_SECONDS, max_retries=1
    )


class AnthropicSession:
    def __init__(self, client: Any, system: str, messages: list[dict]) -> None:
        self._client = client
        self._system = system
        self._convo: list[dict] = list(messages)

    def step(self) -> Turn:
        try:
            response = self._client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.CHAT_MAX_TOKENS,
                system=self._system,
                tools=TOOL_SCHEMAS,
                messages=self._convo,
            )
        except anthropic.APIError as exc:
            raise ChatUpstreamError from exc

        text = "\n".join(
            b.text for b in response.content if getattr(b, "type", None) == "text"
        ).strip()
        if response.stop_reason != "tool_use":
            return Turn(text, [])
        self._convo.append({"role": "assistant", "content": response.content})
        calls = [
            ToolCall(b.id, b.name, b.input)
            for b in response.content
            if getattr(b, "type", None) == "tool_use"
        ]
        return Turn(text, calls)

    def add_tool_results(self, results: list[ToolResult]) -> None:
        blocks = [
            {
                "type": "tool_result",
                "tool_use_id": r.call.id,
                "content": r.content,
                "is_error": r.is_error,
            }
            for r in results
        ]
        self._convo.append({"role": "user", "content": blocks})


def _openai_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOL_SCHEMAS
    ]


def _parse_openai_call(raw: Any) -> ToolCall:
    name, arguments = raw.function.name, raw.function.arguments or "{}"
    try:
        args = json.loads(arguments)
    except json.JSONDecodeError:
        return ToolCall(raw.id, name, {}, error="Tool arguments were not valid JSON")
    if not isinstance(args, dict):
        return ToolCall(raw.id, name, {}, error="Tool arguments must be a JSON object")
    return ToolCall(raw.id, name, args)


class OpenAISession:
    def __init__(self, client: Any, system: str, messages: list[dict]) -> None:
        self._client = client
        self._convo: list[dict] = [{"role": "system", "content": system}, *messages]

    def step(self) -> Turn:
        try:
            response = self._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                max_completion_tokens=settings.CHAT_MAX_TOKENS,
                tools=_openai_tools(),
                messages=self._convo,
            )
        except openai.APIError as exc:
            raise ChatUpstreamError from exc

        message = response.choices[0].message
        text = (message.content or "").strip()
        raw_calls = [
            c for c in (message.tool_calls or []) if getattr(c, "type", "function") == "function"
        ]
        if not raw_calls:
            return Turn(text, [])
        self._convo.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.function.name, "arguments": c.function.arguments},
                    }
                    for c in raw_calls
                ],
            }
        )
        return Turn(text, [_parse_openai_call(c) for c in raw_calls])

    def add_tool_results(self, results: list[ToolResult]) -> None:
        # OpenAI has no is_error flag; the content already carries {"error": ...}.
        for r in results:
            self._convo.append({"role": "tool", "tool_call_id": r.call.id, "content": r.content})


def create_session(system: str, messages: list[dict]) -> ChatSession:
    if settings.USE_ANTHROPIC_KEY:
        if not settings.ANTHROPIC_API_KEY:
            raise ChatNotConfiguredError
        return AnthropicSession(get_anthropic_client(), system, messages)
    if not settings.OPENAI_API_KEY:
        raise ChatNotConfiguredError
    return OpenAISession(get_openai_client(), system, messages)
