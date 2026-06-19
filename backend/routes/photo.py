from fastapi import APIRouter, File, Form, UploadFile

from models.schemas import ChatResponse
from services.agent_service import agent_service

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def log_from_photo(file: UploadFile = File(...), message: str = Form("")):
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"
    result = agent_service.chat_with_image(message, image_bytes, mime_type)
    return ChatResponse(**result)
