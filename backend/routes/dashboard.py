from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from models.schemas import DashboardSummary
from services.storage_service import DEFAULT_USER_ID, storage
from services.tools import tool_compare_to_average, tool_get_history

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def summary():
    today = tool_get_history(DEFAULT_USER_ID, "today")
    week = tool_get_history(DEFAULT_USER_ID, "week")
    month = tool_get_history(DEFAULT_USER_ID, "month")
    comparison = tool_compare_to_average(DEFAULT_USER_ID)
    user = storage.get_user(DEFAULT_USER_ID)

    return DashboardSummary(
        today_kg=today["total_co2e_kg"],
        week_kg=week["total_co2e_kg"],
        month_kg=month["total_co2e_kg"],
        by_category_month=month["by_category"],
        comparison=comparison,
        goal_annual_kg=user["goal_annual_kg"],
    )


@router.get("/history")
async def history(days: int = 14):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    activities = storage.get_activities(DEFAULT_USER_ID, since=since)

    daily: dict[str, float] = defaultdict(float)
    for a in activities:
        day = a["timestamp"][:10]
        daily[day] += a["co2e_kg"]

    series = []
    for i in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        series.append({"date": day, "co2e_kg": round(daily.get(day, 0.0), 2)})

    return {"days": days, "series": series}


@router.get("/activities")
async def activities(period: str = "week"):
    return tool_get_history(DEFAULT_USER_ID, period)
