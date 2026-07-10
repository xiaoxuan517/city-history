from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import AssistantService, get_assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def _sse_payload(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat", response_model=AssistantChatResponse)
def assistant_chat(
    payload: AssistantChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    assistant_service: AssistantService = Depends(get_assistant_service),
) -> AssistantChatResponse:
    return assistant_service.chat(
        session,
        user_id=current_user.id,
        message=payload.message,
        state=payload.state,
        session_id=payload.session_id,
    )


@router.post("/chat/stream")
def assistant_chat_stream(
    payload: AssistantChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    assistant_service: AssistantService = Depends(get_assistant_service),
) -> StreamingResponse:
    def event_generator():
        for event, data in assistant_service.chat_stream(
            session,
            user_id=current_user.id,
            message=payload.message,
            state=payload.state,
            session_id=payload.session_id,
        ):
            yield _sse_payload(event, data)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
