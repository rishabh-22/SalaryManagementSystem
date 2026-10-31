"""LLM provider adapters for the chat agent: OpenAI, Anthropic or Gemini, picked by AGENT_PROVIDER.

Each session keeps its provider's native message format; the agent loop only sees ToolCall/Turn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import openai
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

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


def get_gemini_client() -> genai.Client:
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        # The SDK takes milliseconds.
        http_options=genai_types.HttpOptions(timeout=_REQUEST_TIMEOUT_SECONDS * 1000),
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


def _gemini_tools() -> list[genai_types.Tool]:
    return [
        genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["input_schema"],
                )
                for t in TOOL_SCHEMAS
            ]
        )
    ]


class GeminiSession:
    def __init__(self, client: Any, system: str, messages: list[dict]) -> None:
        self._client = client
        self._invented_ids: set[str] = set()
        self._config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=settings.CHAT_MAX_TOKENS,
            tools=_gemini_tools(),
            # Our loop runs the tools; the SDK must never call anything itself.
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
        )
        self._convo: list[genai_types.Content] = [
            genai_types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[genai_types.Part(text=m["content"])],
            )
            for m in messages
        ]

    def step(self) -> Turn:
        try:
            response = self._client.models.generate_content(
                model=settings.GEMINI_MODEL, contents=self._convo, config=self._config
            )
        except genai_errors.APIError as exc:
            raise ChatUpstreamError from exc

        # No candidates or content (blocked): the agent shows its fallback reply.
        content = response.candidates[0].content if response.candidates else None
        parts = (content.parts if content else None) or []
        text = "\n".join(p.text for p in parts if p.text and not p.thought).strip()
        calls = []
        for i, p in enumerate(p for p in parts if p.function_call):
            fc = p.function_call
            call_id = fc.id
            if not call_id:  # Gemini often omits ids; invent one for our bookkeeping only
                call_id = f"{fc.name}-{i}"
                self._invented_ids.add(call_id)
            calls.append(ToolCall(call_id, fc.name, dict(fc.args or {})))
        if not calls:
            return Turn(text, [])
        # Keep the model's content verbatim; Gemini needs it (incl. thought signatures) echoed back.
        self._convo.append(content)
        return Turn(text, calls)

    def add_tool_results(self, results: list[ToolResult]) -> None:
        # Gemini has no is_error flag, so errors travel in the payload.
        parts = [
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=None if r.call.id in self._invented_ids else r.call.id,
                    name=r.call.name,
                    response={"error": json.loads(r.content)["error"]}
                    if r.is_error
                    else {"result": json.loads(r.content)},
                )
            )
            for r in results
        ]
        self._convo.append(genai_types.Content(role="user", parts=parts))


# provider name -> (API key setting, client factory name, session class). The factory is looked up
# on the module at call time so tests can monkeypatch it.
_PROVIDERS: dict[str, tuple[str, str, type]] = {
    "openai": ("OPENAI_API_KEY", "get_openai_client", OpenAISession),
    "anthropic": ("ANTHROPIC_API_KEY", "get_anthropic_client", AnthropicSession),
    "gemini": ("GEMINI_API_KEY", "get_gemini_client", GeminiSession),
}


def create_session(system: str, messages: list[dict]) -> ChatSession:
    entry = _PROVIDERS.get(settings.AGENT_PROVIDER)
    if entry is None:  # empty provider; unsupported names never get past config validation
        raise ChatNotConfiguredError
    key_setting, factory_name, session_cls = entry
    if not getattr(settings, key_setting):
        raise ChatNotConfiguredError
    return session_cls(globals()[factory_name](), system, messages)
