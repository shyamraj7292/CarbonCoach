from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatAction(BaseModel):
    tool: str
    args: dict
    result: dict


class ChatResponse(BaseModel):
    reply: str
    actions: list[ChatAction] = []


class OnboardRequest(BaseModel):
    name: str | None = None
    country: str = "global"
    goal_annual_kg: float = 2500


class DashboardSummary(BaseModel):
    today_kg: float
    week_kg: float
    month_kg: float
    by_category_month: dict[str, float]
    comparison: dict
    goal_annual_kg: float


class InsightResponse(BaseModel):
    summary: str
    top_category: str | None
    top_category_kg: float
    suggestions: list[dict]
    progress: dict
