from fastapi import APIRouter

from models.schemas import ChatRequest, ChatResponse
from services.agent_service import agent_service

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = agent_service.chat(request.message)
    return ChatResponse(**result)
