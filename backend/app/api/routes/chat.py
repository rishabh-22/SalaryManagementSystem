from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbSession
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_agent, chat_llm

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, _: CurrentUser, db: DbSession):
    try:
        reply, tools_used = chat_agent.answer(db, body.messages)
    except chat_llm.ChatNotConfiguredError:
        raise HTTPException(status_code=503, detail="Chat is not configured") from None
    except chat_llm.ChatUpstreamError:
        raise HTTPException(
            status_code=502, detail="The assistant is unavailable right now"
        ) from None
    return ChatResponse(reply=reply, tools_used=tools_used)
