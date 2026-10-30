"""Chat agent: an LLM tool-use loop over the read-only tools in chat_tools.

The provider (Anthropic or OpenAI) is chosen in chat_llm; this loop is provider-neutral.
"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reference import COUNTRIES, DEPARTMENTS, TITLE_DEPARTMENT
from app.schemas.chat import ChatMessage
from app.services import chat_llm
from app.services.chat_llm import ToolCall, ToolResult
from app.services.chat_tools import TOOL_ERRORS, run_tool

_FALLBACK_REPLY = (
    "I couldn't finish looking that up. Please try a more specific question, "
    "for example by giving an employee id or a country."
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


def _execute_tool(db: Session, call: ToolCall, today: date) -> ToolResult:
    if call.error:
        return ToolResult(call, json.dumps({"error": call.error}), True)
    try:
        return ToolResult(call, json.dumps(run_tool(db, call.name, call.input, today)), False)
    except TOOL_ERRORS as exc:
        message = getattr(exc, "message", None) or str(exc)
        return ToolResult(call, json.dumps({"error": message}), True)


def answer(
    db: Session, messages: list[ChatMessage], today: date | None = None
) -> tuple[str, list[str]]:
    """Run the agent loop. Returns (reply, names of tools used)."""
    today = today or date.today()
    session = chat_llm.create_session(
        build_system_prompt(today), [{"role": m.role, "content": m.content} for m in messages]
    )
    tools_used: list[str] = []

    for _ in range(settings.CHAT_MAX_TOOL_ITERATIONS):
        turn = session.step()
        if not turn.tool_calls:
            return turn.text or _FALLBACK_REPLY, tools_used

        results = []
        for call in turn.tool_calls:
            tools_used.append(call.name)
            results.append(_execute_tool(db, call, today))
        session.add_tool_results(results)

    return _FALLBACK_REPLY, tools_used
