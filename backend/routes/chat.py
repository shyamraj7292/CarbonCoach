import logging

from fastapi import APIRouter

from models.schemas import ChatRequest, ChatResponse
from services.agent_service import agent_service

logger = logging.getLogger("carboncoach.routes.chat")
router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = agent_service.chat(request.message)
    except Exception as e:
        logger.exception("Chat error")
        result = {"reply": f"Sorry, something went wrong: {e}", "actions": []}
    return ChatResponse(**result)
