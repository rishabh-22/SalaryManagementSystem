"""Chat agent: a Claude tool-use loop over the read-only tools in chat_tools."""

from __future__ import annotations

import json
from datetime import date

import anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reference import COUNTRIES, DEPARTMENTS, TITLE_DEPARTMENT
from app.schemas.chat import ChatMessage
from app.services.chat_tools import TOOL_ERRORS, TOOL_SCHEMAS, run_tool

_REQUEST_TIMEOUT_SECONDS = 30
_FALLBACK_REPLY = (
    "I couldn't finish looking that up. Please try a more specific question, "
    "for example by giving an employee id or a country."
)


class ChatNotConfiguredError(Exception):
    """ANTHROPIC_API_KEY is not set."""


class ChatUpstreamError(Exception):
    """The Anthropic API call failed."""


def get_anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY, timeout=_REQUEST_TIMEOUT_SECONDS, max_retries=1
    )


def build_system_prompt(today: date) -> str:
    countries = ", ".join(f"{code} ({c['name']}, {c['currency']})" for code, c in COUNTRIES.items())
    return f"""You are the HR assistant inside ACME's Salary Management System. You help HR \
managers answer questions about employee pay. Today's date is {today.isoformat()}.

Rules:
- Answer ONLY from tool results. Never invent or estimate numbers. If a tool returns nothing, \
say so.
- You are read-only. If asked to change, create or delete anything, politely decline and point the \
user to the Employees page.
- Keep answers short. Show money with its currency code, e.g. "INR 2,500,000.00".

Domain facts:
- Salaries are annual and stored in each employee's local currency. NEVER add, average or compare \
amounts across different currencies. When a result spans several countries, report each country \
separately with its own currency.
- Pay insights (averages, medians) count active employees only.
- Countries: {countries}.
- Departments: {", ".join(DEPARTMENTS)}.
- Job titles: {", ".join(TITLE_DEPARTMENT)}.

Finding employees:
- Tools need a numeric employee_id. If the user gives a name, email or code (e.g. ACME-00042) \
instead of an id, call search_employees first.
- Exactly one match: continue with that employee and mention who it is.
- Several matches: do NOT guess. List them (id, employee code, name, job title, country) and ask \
which one the user means; the user can reply with the id.
- No match: say so and suggest checking the spelling.
- If the user gives a numeric id, use it directly.

Dates:
- "Last quarter" means the previous calendar quarter. Call get_current_date to get its exact start \
and end, then call list_salary_revisions with those dates. For other periods (last month, this \
year, ...) work out explicit dates from today's date.
- If list_salary_revisions says total_revisions is larger than shown, tell the user the list is \
truncated.
"""


def _reply_text(content: list) -> str:
    return "\n".join(b.text for b in content if getattr(b, "type", None) == "text").strip()


def _execute_tool(db: Session, name: str, args: dict, today: date) -> dict:
    try:
        return {"content": json.dumps(run_tool(db, name, args, today)), "is_error": False}
    except TOOL_ERRORS as exc:
        message = getattr(exc, "message", None) or str(exc)
        return {"content": json.dumps({"error": message}), "is_error": True}


def answer(
    db: Session, messages: list[ChatMessage], today: date | None = None
) -> tuple[str, list[str]]:
    """Run the agent loop. Returns (reply, names of tools used)."""
    if not settings.ANTHROPIC_API_KEY:
        raise ChatNotConfiguredError
    today = today or date.today()
    client = get_anthropic_client()
    system = build_system_prompt(today)
    convo: list[dict] = [{"role": m.role, "content": m.content} for m in messages]
    tools_used: list[str] = []

    for _ in range(settings.CHAT_MAX_TOOL_ITERATIONS):
        try:
            response = client.messages.create(
                model=settings.CHAT_MODEL,
                max_tokens=settings.CHAT_MAX_TOKENS,
                system=system,
                tools=TOOL_SCHEMAS,
                messages=convo,
            )
        except anthropic.APIError as exc:
            raise ChatUpstreamError from exc

        if response.stop_reason != "tool_use":
            return _reply_text(response.content) or _FALLBACK_REPLY, tools_used

        convo.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            tools_used.append(block.name)
            outcome = _execute_tool(db, block.name, block.input, today)
            results.append({"type": "tool_result", "tool_use_id": block.id, **outcome})
        convo.append({"role": "user", "content": results})

    return _FALLBACK_REPLY, tools_used
