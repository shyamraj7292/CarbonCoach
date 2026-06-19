from fastapi import APIRouter

from models.schemas import OnboardRequest
from services.storage_service import DEFAULT_USER_ID, storage

router = APIRouter()


@router.post("")
async def onboard(request: OnboardRequest):
    fields = {"country": request.country, "goal_annual_kg": request.goal_annual_kg}
    if request.name:
        fields["name"] = request.name
    user = storage.update_user(DEFAULT_USER_ID, fields)
    return user


@router.get("")
async def get_profile():
    return storage.get_user(DEFAULT_USER_ID)
