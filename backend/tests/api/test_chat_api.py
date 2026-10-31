"""Chat API tests. Every provider scenario runs against scripted fake clients (no network)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx
import openai
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services import chat_llm
from app.services.chat_tools import TOOL_SCHEMAS

BACKEND_DIR = Path(__file__).resolve().parents[2]


class FakeLLM:
    """Returns scripted responses in order (repeating the last) and records every call.

    Exposes the Anthropic (`messages.create`), OpenAI (`chat.completions.create`) and Gemini
    (`models.generate_content`) shapes.
    """

    def __init__(self, *scripted, error: Exception | None = None):
        self.scripted = list(scripted)
        self.error = error
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(generate_content=self._create)

    def _create(self, **kwargs):
        # Snapshot the growing conversation (Anthropic/OpenAI: messages, Gemini: contents).
        key = "contents" if "contents" in kwargs else "messages"
        self.calls.append({**kwargs, key: list(kwargs[key])})
        if self.error:
            raise self.error
        index = min(len(self.calls), len(self.scripted)) - 1
        return self.scripted[index]


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.example.com")


class AnthropicProvider:
    name = "anthropic"
    upstream_error = anthropic.APIConnectionError(request=_request())

    def configure(self, monkeypatch, fake):
        monkeypatch.setattr(settings, "AGENT_PROVIDER", "anthropic")
        monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(chat_llm, "get_anthropic_client", lambda: fake)

    def text(self, value: str):
        block = SimpleNamespace(type="text", text=value)
        return SimpleNamespace(content=[block], stop_reason="end_turn")

    def tool(self, name: str, tool_input: dict, block_id: str = "tu_1"):
        block = SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)
        return SimpleNamespace(content=[block], stop_reason="tool_use")

    def model(self, call: dict) -> str:
        return call["model"]

    def tool_names(self, call: dict) -> set[str]:
        return {t["name"] for t in call["tools"]}

    def system(self, call: dict) -> str:
        return call["system"]

    def history(self, call: dict) -> list[dict]:
        return call["messages"]

    def tool_results(self, call: dict) -> list[dict]:
        """Normalised results sent back after a tool call: id, payload, is_error."""
        return [
            {
                "id": b["tool_use_id"],
                "payload": json.loads(b["content"]),
                "is_error": b["is_error"],
            }
            for b in call["messages"][-1]["content"]
        ]


class OpenAIProvider:
    name = "openai"
    upstream_error = openai.APIConnectionError(request=_request())

    def configure(self, monkeypatch, fake):
        monkeypatch.setattr(settings, "AGENT_PROVIDER", "openai")
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
        monkeypatch.setattr(chat_llm, "get_openai_client", lambda: fake)

    def _response(self, content, tool_calls=None):
        message = SimpleNamespace(content=content, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def text(self, value: str):
        return self._response(value)

    def tool(self, name: str, tool_input: dict, block_id: str = "tu_1"):
        return self.raw_tool(name, json.dumps(tool_input), block_id)

    def raw_tool(self, name: str, arguments: str, block_id: str = "tu_1"):
        function = SimpleNamespace(name=name, arguments=arguments)
        call = SimpleNamespace(id=block_id, type="function", function=function)
        return self._response(None, [call])

    def model(self, call: dict) -> str:
        return call["model"]

    def tool_names(self, call: dict) -> set[str]:
        return {t["function"]["name"] for t in call["tools"]}

    def system(self, call: dict) -> str:
        return call["messages"][0]["content"]

    def history(self, call: dict) -> list[dict]:
        return call["messages"][1:]

    def tool_results(self, call: dict) -> list[dict]:
        trailing = []
        for message in reversed(call["messages"]):
            if message["role"] != "tool":
                break
            payload = json.loads(message["content"])
            trailing.append(
                {
                    "id": message["tool_call_id"],
                    "payload": payload,
                    "is_error": "error" in payload,
                }
            )
        return list(reversed(trailing))


class GeminiProvider:
    name = "gemini"
    upstream_error = genai_errors.APIError(500, {"error": {"message": "boom"}})

    def configure(self, monkeypatch, fake):
        monkeypatch.setattr(settings, "AGENT_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(chat_llm, "get_gemini_client", lambda: fake)

    def _response(self, *parts: genai_types.Part):
        content = genai_types.Content(role="model", parts=list(parts))
        return genai_types.GenerateContentResponse(
            candidates=[genai_types.Candidate(content=content)]
        )

    def text(self, value: str):
        return self._response(genai_types.Part(text=value))

    def tool(self, name: str, tool_input: dict, block_id: str | None = "tu_1"):
        call = genai_types.FunctionCall(id=block_id, name=name, args=tool_input)
        return self._response(genai_types.Part(function_call=call))

    def model(self, call: dict) -> str:
        return call["model"]

    def tool_names(self, call: dict) -> set[str]:
        [tool] = call["config"].tools
        return {d.name for d in tool.function_declarations}

    def system(self, call: dict) -> str:
        return call["config"].system_instruction

    def history(self, call: dict) -> list[dict]:
        return [
            {"role": "assistant" if c.role == "model" else "user", "content": c.parts[0].text}
            for c in call["contents"]
        ]

    def tool_results(self, call: dict) -> list[dict]:
        results = []
        for part in call["contents"][-1].parts:
            response = part.function_response.response
            results.append(
                {
                    "id": part.function_response.id or part.function_response.name,
                    "payload": response.get("result", response),
                    "is_error": "error" in response,
                }
            )
        return results


@pytest.fixture(
    params=[AnthropicProvider(), OpenAIProvider(), GeminiProvider()], ids=lambda p: p.name
)
def provider(request):
    return request.param


@pytest.fixture()
def use_fake(monkeypatch, provider):
    def _use(*scripted, error: Exception | None = None) -> FakeLLM:
        fake = FakeLLM(*scripted, error=error)
        provider.configure(monkeypatch, fake)
        return fake

    return _use


def ask(client, headers, content="hi"):
    body = {"messages": [{"role": "user", "content": content}]}
    return client.post("/api/chat", json=body, headers=headers)


# ---- access and configuration


def test_requires_authentication(client):
    assert ask(client, {}).status_code == 401


@pytest.mark.parametrize(
    ("agent_provider", "keys"),
    [
        ("", {}),
        ("", {"OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "k", "GEMINI_API_KEY": "k"}),
        ("openai", {}),
        ("anthropic", {}),
        ("gemini", {}),
        ("openai", {"ANTHROPIC_API_KEY": "k", "GEMINI_API_KEY": "k"}),
        ("anthropic", {"OPENAI_API_KEY": "k", "GEMINI_API_KEY": "k"}),
        ("gemini", {"OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "k"}),
    ],
)
def test_503_when_no_provider_or_selected_providers_key_is_missing(
    client, viewer_h, monkeypatch, agent_provider, keys
):
    monkeypatch.setattr(settings, "AGENT_PROVIDER", agent_provider)
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setattr(settings, name, keys.get(name, ""))
    res = ask(client, viewer_h)
    assert res.status_code == 503
    assert res.json() == {"detail": "Chat is not configured"}


def test_defaults_disable_chat_and_set_model_names(monkeypatch):
    for name in ("AGENT_PROVIDER", "OPENAI_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.AGENT_PROVIDER == ""
    assert defaults.OPENAI_MODEL == "gpt-4o"
    assert defaults.GEMINI_MODEL == "gemini-2.5-flash"


@pytest.mark.parametrize("value", ["openai", "anthropic", "gemini", "", " Gemini ", "OPENAI"])
def test_supported_agent_providers_are_accepted_and_normalised(value):
    assert value.strip().lower() == Settings(_env_file=None, AGENT_PROVIDER=value).AGENT_PROVIDER


@pytest.mark.parametrize("value", ["gemni", "claude", "true", "none"])
def test_unsupported_agent_provider_fails_fast(value):
    with pytest.raises(ValidationError, match="AGENT_PROVIDER"):
        Settings(_env_file=None, AGENT_PROVIDER=value)


def test_unsupported_agent_provider_stops_app_startup():
    env = {**os.environ, "AGENT_PROVIDER": "gemni"}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        env=env,
    )
    assert result.returncode != 0
    assert "AGENT_PROVIDER" in result.stderr


def test_agent_provider_routes_to_one_provider_only(client, viewer_h, monkeypatch):
    def forbidden():
        raise AssertionError("another provider must not be used")

    providers = {
        "openai": OpenAIProvider(),
        "anthropic": AnthropicProvider(),
        "gemini": GeminiProvider(),
    }
    fakes = {name: FakeLLM(p.text(f"from {name}")) for name, p in providers.items()}
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setattr(settings, key, "k")

    for selected in providers:
        for name, fake in fakes.items():
            factory = (lambda f=fake: f) if name == selected else forbidden
            monkeypatch.setattr(chat_llm, f"get_{name}_client", factory)
        monkeypatch.setattr(settings, "AGENT_PROVIDER", selected)
        assert ask(client, viewer_h).json()["reply"] == f"from {selected}"


# ---- the agent loop (runs for every provider)


def test_plain_answer_without_tools(client, viewer_h, use_fake, provider):
    fake = use_fake(provider.text("Hello! Ask me about pay."))
    res = ask(client, viewer_h)
    assert res.status_code == 200
    assert res.json() == {"reply": "Hello! Ask me about pay.", "tools_used": []}
    call = fake.calls[0]
    expected_model = {
        "anthropic": settings.ANTHROPIC_MODEL,
        "openai": "gpt-4o",
        "gemini": settings.GEMINI_MODEL,
    }[provider.name]
    assert provider.model(call) == expected_model
    assert provider.tool_names(call) >= {"search_employees", "get_average_pay"}
    assert "Today's date is" in provider.system(call)


def test_tool_loop_feeds_db_result_back_to_model(
    client, viewer_h, use_fake, provider, make_employee
):
    e = make_employee(first_name="Ana", last_name="Silva", country_code="BR", salary=185000.5)
    fake = use_fake(
        provider.tool("get_employee_salary", {"employee_id": e.id}),
        provider.text("Ana Silva earns BRL 185,000.50."),
    )
    res = ask(client, viewer_h, f"salary of employee {e.id}")
    assert res.json() == {
        "reply": "Ana Silva earns BRL 185,000.50.",
        "tools_used": ["get_employee_salary"],
    }
    assert len(fake.calls) == 2
    [result] = provider.tool_results(fake.calls[1])
    assert result["id"] == "tu_1"
    assert result["is_error"] is False
    assert result["payload"]["salary"] == 185000.5
    assert result["payload"]["currency"] == "BRL"


def test_name_lookup_returns_all_candidates_for_disambiguation(
    client, hr_h, use_fake, provider, make_employee
):
    a = make_employee(first_name="Ana", last_name="Silva")
    b = make_employee(first_name="Ana", last_name="Costa")
    fake = use_fake(
        provider.tool("search_employees", {"query": "Ana"}), provider.text("Which Ana?")
    )
    res = ask(client, hr_h, "salary of Ana")
    assert res.json()["tools_used"] == ["search_employees"]
    [result] = provider.tool_results(fake.calls[1])
    assert result["payload"]["total_matches"] == 2
    assert {e["employee_id"] for e in result["payload"]["employees"]} == {a.id, b.id}


def test_tool_error_is_reported_to_model_not_http_client(client, viewer_h, use_fake, provider):
    fake = use_fake(
        provider.tool("get_employee_salary", {"employee_id": 999}),
        provider.text("I couldn't find employee 999."),
    )
    res = ask(client, viewer_h)
    assert res.status_code == 200
    [result] = provider.tool_results(fake.calls[1])
    assert result["is_error"] is True
    assert "999" in result["payload"]["error"]


def test_unknown_tool_is_an_error_result(client, viewer_h, use_fake, provider):
    fake = use_fake(
        provider.tool("delete_employee", {"employee_id": 1}), provider.text("I can't do that.")
    )
    assert ask(client, viewer_h).status_code == 200
    assert provider.tool_results(fake.calls[1])[0]["is_error"] is True


def test_iteration_cap_stops_runaway_loop(client, viewer_h, use_fake, provider, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_MAX_TOOL_ITERATIONS", 3)
    fake = use_fake(provider.tool("get_current_date", {}))
    res = ask(client, viewer_h)
    assert res.status_code == 200
    assert len(fake.calls) == 3
    assert "couldn't finish" in res.json()["reply"]
    assert res.json()["tools_used"] == ["get_current_date"] * 3


def test_upstream_failure_maps_to_502_without_leaking_details(client, viewer_h, use_fake, provider):
    use_fake(error=provider.upstream_error)
    res = ask(client, viewer_h)
    assert res.status_code == 502
    assert res.json() == {"detail": "The assistant is unavailable right now"}


def test_conversation_history_is_forwarded(client, viewer_h, use_fake, provider):
    fake = use_fake(provider.text("ok"))
    body = {
        "messages": [
            {"role": "user", "content": "salary of Ana"},
            {"role": "assistant", "content": "Which Ana?"},
            {"role": "user", "content": "id 7"},
        ]
    }
    assert client.post("/api/chat", json=body, headers=viewer_h).status_code == 200
    assert provider.history(fake.calls[0]) == body["messages"]


@pytest.mark.parametrize("role_header", ["admin_h", "hr_h", "viewer_h"])
def test_every_role_can_chat(request, client, use_fake, provider, role_header):
    use_fake(provider.text("ok"))
    assert ask(client, request.getfixturevalue(role_header)).status_code == 200


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": ""}],
        [{"role": "user", "content": "   "}],
        [{"role": "user", "content": "x" * 2001}],
        [{"role": "system", "content": "hi"}],
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        [{"role": "user", "content": "hi"}] * 21,
    ],
)
def test_invalid_requests_are_rejected(client, viewer_h, use_fake, provider, messages):
    fake = use_fake(provider.text("ok"))
    res = client.post("/api/chat", json={"messages": messages}, headers=viewer_h)
    assert res.status_code == 422
    assert fake.calls == []


# ---- OpenAI wire format


@pytest.fixture()
def openai_provider():
    return OpenAIProvider()


@pytest.fixture()
def use_openai(monkeypatch, openai_provider):
    def _use(*scripted) -> FakeLLM:
        fake = FakeLLM(*scripted)
        openai_provider.configure(monkeypatch, fake)
        return fake

    return _use


def test_openai_receives_tools_in_function_format(client, viewer_h, use_openai, openai_provider):
    fake = use_openai(openai_provider.text("ok"))
    ask(client, viewer_h)
    sent = fake.calls[0]["tools"]
    assert sent == [
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
    assert fake.calls[0]["messages"][0]["role"] == "system"


def test_openai_tool_round_trip_message_shapes(
    client, viewer_h, use_openai, openai_provider, make_employee
):
    e = make_employee()
    fake = use_openai(
        openai_provider.tool("get_employee_salary", {"employee_id": e.id}, "call_9"),
        openai_provider.text("done"),
    )
    ask(client, viewer_h)
    _, assistant, tool = fake.calls[1]["messages"][-3:]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"] == [
        {
            "id": "call_9",
            "type": "function",
            "function": {
                "name": "get_employee_salary",
                "arguments": json.dumps({"employee_id": e.id}),
            },
        }
    ]
    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call_9"


def test_openai_invalid_json_arguments_become_an_error_result(
    client, viewer_h, use_openai, openai_provider
):
    fake = use_openai(
        openai_provider.raw_tool("get_employee_salary", "{not json"), openai_provider.text("sorry")
    )
    res = ask(client, viewer_h)
    assert res.status_code == 200
    [result] = openai_provider.tool_results(fake.calls[1])
    assert result["is_error"] is True
    assert "not valid JSON" in result["payload"]["error"]


def test_openai_non_object_arguments_become_an_error_result(
    client, viewer_h, use_openai, openai_provider
):
    fake = use_openai(
        openai_provider.raw_tool("get_current_date", "[1, 2]"), openai_provider.text("x")
    )
    assert ask(client, viewer_h).status_code == 200
    [result] = openai_provider.tool_results(fake.calls[1])
    assert result["is_error"] is True


# ---- Gemini wire format


@pytest.fixture()
def gemini_provider():
    return GeminiProvider()


@pytest.fixture()
def use_gemini(monkeypatch, gemini_provider):
    def _use(*scripted) -> FakeLLM:
        fake = FakeLLM(*scripted)
        gemini_provider.configure(monkeypatch, fake)
        return fake

    return _use


def test_gemini_receives_declarations_from_tool_schemas(
    client, viewer_h, use_gemini, gemini_provider
):
    fake = use_gemini(gemini_provider.text("ok"))
    ask(client, viewer_h)
    config = fake.calls[0]["config"]
    [tool] = config.tools
    declared = [
        (d.name, d.description, d.parameters_json_schema) for d in tool.function_declarations
    ]
    assert declared == [(t["name"], t["description"], t["input_schema"]) for t in TOOL_SCHEMAS]
    assert config.max_output_tokens == settings.CHAT_MAX_TOKENS


def test_gemini_automatic_function_calling_is_disabled(
    client, viewer_h, use_gemini, gemini_provider
):
    fake = use_gemini(gemini_provider.text("ok"))
    ask(client, viewer_h)
    assert fake.calls[0]["config"].automatic_function_calling.disable is True


def test_gemini_tool_round_trip_message_shapes(
    client, viewer_h, use_gemini, gemini_provider, make_employee
):
    e = make_employee()
    fake = use_gemini(
        gemini_provider.tool("get_employee_salary", {"employee_id": e.id}, "call_9"),
        gemini_provider.text("done"),
    )
    ask(client, viewer_h)
    _, model_turn, tool_turn = fake.calls[1]["contents"]
    assert model_turn.role == "model"
    assert model_turn.parts[0].function_call.name == "get_employee_salary"
    assert tool_turn.role == "user"
    response = tool_turn.parts[0].function_response
    assert (response.id, response.name) == ("call_9", "get_employee_salary")
    assert response.response["result"]["employee_id"] == e.id


def test_gemini_calls_without_ids_still_round_trip(client, viewer_h, use_gemini, gemini_provider):
    fake = use_gemini(
        gemini_provider.tool("get_current_date", {}, block_id=None), gemini_provider.text("done")
    )
    res = ask(client, viewer_h)
    assert res.json()["tools_used"] == ["get_current_date"]
    response = fake.calls[1]["contents"][-1].parts[0].function_response
    assert response.id is None
    assert response.name == "get_current_date"


def test_gemini_parallel_calls_keep_their_order(client, viewer_h, use_gemini, gemini_provider):
    def call(name, args):
        return genai_types.Part(function_call=genai_types.FunctionCall(name=name, args=args))

    parts = [call("get_current_date", {}), call("get_employee_salary", {"employee_id": 999})]
    fake = use_gemini(gemini_provider._response(*parts), gemini_provider.text("done"))
    ask(client, viewer_h)
    sent = fake.calls[1]["contents"][-1].parts
    assert [p.function_response.name for p in sent] == ["get_current_date", "get_employee_salary"]
    assert "error" in sent[1].function_response.response


def test_gemini_blocked_response_uses_fallback_reply(client, viewer_h, use_gemini):
    use_gemini(genai_types.GenerateContentResponse(candidates=[]))
    res = ask(client, viewer_h)
    assert res.status_code == 200
    assert res.json()["reply"]
    assert res.json()["tools_used"] == []
