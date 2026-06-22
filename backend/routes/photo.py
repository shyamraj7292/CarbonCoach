import logging

from fastapi import APIRouter, File, Form, UploadFile

from models.schemas import ChatResponse
from services.agent_service import agent_service

logger = logging.getLogger("carboncoach.routes.photo")
router = APIRouter()


@router.post("", response_model=ChatResponse)
async def log_from_photo(file: UploadFile = File(...), message: str = Form("")):
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"
        result = agent_service.chat_with_image(message, image_bytes, mime_type)
    except Exception as e:
        logger.exception("Photo analysis error")
        result = {"reply": f"Could not analyze the photo: {e}", "actions": []}
    return ChatResponse(**result)
