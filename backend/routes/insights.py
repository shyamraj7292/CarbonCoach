from fastapi import APIRouter

from models.schemas import InsightResponse
from services.storage_service import DEFAULT_USER_ID, storage
from services.tools import tool_get_history, tool_suggest_swaps

router = APIRouter()


@router.get("", response_model=InsightResponse)
async def insights():
    week = tool_get_history(DEFAULT_USER_ID, "week")
    swaps = tool_suggest_swaps(DEFAULT_USER_ID, top_n=1)
    user = storage.get_user(DEFAULT_USER_ID)

    by_category = week["by_category"]
    top_category = max(by_category, key=by_category.get) if by_category else None
    top_category_kg = by_category.get(top_category, 0.0) if top_category else 0.0

    weekly_goal = user["goal_annual_kg"] / 52
    progress = {
        "week_total_kg": week["total_co2e_kg"],
        "weekly_goal_kg": round(weekly_goal, 2),
        "on_track": week["total_co2e_kg"] <= weekly_goal,
        "diff_kg": round(week["total_co2e_kg"] - weekly_goal, 2),
    }

    parts = []
    if week["activity_count"] == 0:
        parts.append("No activities logged this week yet — chat with CarbonCoach to start tracking.")
    else:
        parts.append(f"This week you logged {week['total_co2e_kg']} kg CO2e across {week['activity_count']} activities.")
        if top_category:
            parts.append(f"Your biggest source was {top_category} at {top_category_kg} kg CO2e.")
        if progress["on_track"]:
            parts.append(f"You're on track against your weekly goal of {progress['weekly_goal_kg']} kg.")
        else:
            parts.append(f"You're {progress['diff_kg']} kg over your weekly goal of {progress['weekly_goal_kg']} kg.")

    if swaps["suggestions"]:
        s = swaps["suggestions"][0]
        parts.append(f"Tip: {s['suggestion']} to save ~{s['monthly_savings_kg_co2e']} kg CO2e/month.")

    return InsightResponse(
        summary=" ".join(parts),
        top_category=top_category,
        top_category_kg=round(top_category_kg, 2),
        suggestions=swaps["suggestions"],
        progress=progress,
    )
