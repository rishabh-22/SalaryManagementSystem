import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.core.config import settings
from app.services import chat_agent


def text(value: str):
    return SimpleNamespace(type="text", text=value)


def tool_use(name: str, tool_input: dict, block_id: str = "tu_1"):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def response(*blocks, stop_reason: str):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


class FakeAnthropic:
    """Returns scripted responses in order (repeating the last) and records every call."""

    def __init__(self, *scripted, error: Exception | None = None):
        self.scripted = list(scripted)
        self.error = error
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if self.error:
            raise self.error
        index = min(len(self.calls), len(self.scripted)) - 1
        return self.scripted[index]


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")


@pytest.fixture()
def use_fake(monkeypatch, configured):
    def _use(fake: FakeAnthropic) -> FakeAnthropic:
        monkeypatch.setattr(chat_agent, "get_anthropic_client", lambda: fake)
        return fake

    return _use


def ask(client, headers, content="hi", **extra):
    body = {"messages": [{"role": "user", "content": content}], **extra}
    return client.post("/api/chat", json=body, headers=headers)


def tool_results(call: dict) -> list[dict]:
    return call["messages"][-1]["content"]


def test_requires_authentication(client):
    assert ask(client, {}).status_code == 401


def test_returns_503_when_key_not_configured(client, viewer_h, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    res = ask(client, viewer_h)
    assert res.status_code == 503
    assert res.json() == {"detail": "Chat is not configured"}


def test_plain_answer_without_tools(client, viewer_h, use_fake):
    fake = use_fake(
        FakeAnthropic(response(text("Hello! Ask me about pay."), stop_reason="end_turn"))
    )
    res = ask(client, viewer_h)
    assert res.status_code == 200
    assert res.json() == {"reply": "Hello! Ask me about pay.", "tools_used": []}
    call = fake.calls[0]
    assert call["model"] == settings.CHAT_MODEL
    assert {t["name"] for t in call["tools"]} >= {"search_employees", "get_average_pay"}
    assert "Today's date is" in call["system"]


def test_tool_loop_feeds_db_result_back_to_model(client, viewer_h, use_fake, make_employee):
    e = make_employee(first_name="Ana", last_name="Silva", country_code="BR", salary=185000.5)
    fake = use_fake(
        FakeAnthropic(
            response(
                tool_use("get_employee_salary", {"employee_id": e.id}), stop_reason="tool_use"
            ),
            response(text("Ana Silva earns BRL 185,000.50."), stop_reason="end_turn"),
        )
    )
    res = ask(client, viewer_h, f"salary of employee {e.id}")
    assert res.json() == {
        "reply": "Ana Silva earns BRL 185,000.50.",
        "tools_used": ["get_employee_salary"],
    }
    assert len(fake.calls) == 2
    [result] = tool_results(fake.calls[1])
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tu_1"
    assert result["is_error"] is False
    payload = json.loads(result["content"])
    assert payload["salary"] == 185000.5
    assert payload["currency"] == "BRL"


def test_name_lookup_returns_all_candidates_for_disambiguation(
    client, hr_h, use_fake, make_employee
):
    a = make_employee(first_name="Ana", last_name="Silva")
    b = make_employee(first_name="Ana", last_name="Costa")
    fake = use_fake(
        FakeAnthropic(
            response(tool_use("search_employees", {"query": "Ana"}), stop_reason="tool_use"),
            response(text("Which Ana?"), stop_reason="end_turn"),
        )
    )
    res = ask(client, hr_h, "salary of Ana")
    assert res.json()["tools_used"] == ["search_employees"]
    [result] = tool_results(fake.calls[1])
    payload = json.loads(result["content"])
    assert payload["total_matches"] == 2
    assert {e["employee_id"] for e in payload["employees"]} == {a.id, b.id}


def test_tool_error_is_reported_to_model_not_http_client(client, viewer_h, use_fake):
    fake = use_fake(
        FakeAnthropic(
            response(
                tool_use("get_employee_salary", {"employee_id": 999}), stop_reason="tool_use"
            ),
            response(text("I couldn't find employee 999."), stop_reason="end_turn"),
        )
    )
    res = ask(client, viewer_h)
    assert res.status_code == 200
    [result] = tool_results(fake.calls[1])
    assert result["is_error"] is True
    assert "999" in json.loads(result["content"])["error"]


def test_unknown_tool_is_an_error_result(client, viewer_h, use_fake):
    fake = use_fake(
        FakeAnthropic(
            response(tool_use("delete_employee", {"employee_id": 1}), stop_reason="tool_use"),
            response(text("I can't do that."), stop_reason="end_turn"),
        )
    )
    assert ask(client, viewer_h).status_code == 200
    assert tool_results(fake.calls[1])[0]["is_error"] is True


def test_iteration_cap_stops_runaway_loop(client, viewer_h, use_fake, monkeypatch):
    monkeypatch.setattr(settings, "CHAT_MAX_TOOL_ITERATIONS", 3)
    fake = use_fake(
        FakeAnthropic(response(tool_use("get_current_date", {}), stop_reason="tool_use"))
    )
    res = ask(client, viewer_h)
    assert res.status_code == 200
    assert len(fake.calls) == 3
    assert "couldn't finish" in res.json()["reply"]
    assert res.json()["tools_used"] == ["get_current_date"] * 3


def test_upstream_failure_maps_to_502_without_leaking_details(client, viewer_h, use_fake):
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    use_fake(FakeAnthropic(error=error))
    res = ask(client, viewer_h)
    assert res.status_code == 502
    assert res.json() == {"detail": "The assistant is unavailable right now"}


def test_conversation_history_is_forwarded(client, viewer_h, use_fake):
    fake = use_fake(FakeAnthropic(response(text("ok"), stop_reason="end_turn")))
    body = {
        "messages": [
            {"role": "user", "content": "salary of Ana"},
            {"role": "assistant", "content": "Which Ana?"},
            {"role": "user", "content": "id 7"},
        ]
    }
    assert client.post("/api/chat", json=body, headers=viewer_h).status_code == 200
    assert fake.calls[0]["messages"] == body["messages"]


@pytest.mark.parametrize("role_header", ["admin_h", "hr_h", "viewer_h"])
def test_every_role_can_chat(request, client, use_fake, role_header):
    use_fake(FakeAnthropic(response(text("ok"), stop_reason="end_turn")))
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
def test_invalid_requests_are_rejected(client, viewer_h, use_fake, messages):
    fake = use_fake(FakeAnthropic(response(text("ok"), stop_reason="end_turn")))
    res = client.post("/api/chat", json={"messages": messages}, headers=viewer_h)
    assert res.status_code == 422
    assert fake.calls == []
