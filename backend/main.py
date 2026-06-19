"""
CarbonCoach — Backend API Server

FastAPI application serving the CarbonCoach agent (chat, dashboard, insights,
photo logging) and the static frontend.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from routes.chat import router as chat_router
from routes.dashboard import router as dashboard_router
from routes.onboard import router as onboard_router
from routes.insights import router as insights_router
from routes.photo import router as photo_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("carboncoach")

app = FastAPI(
    title="CarbonCoach API",
    description="AI agent that helps people understand, track, and reduce their carbon footprint — powered by Gemini.",
    version="1.0.0",
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(onboard_router, prefix="/api/onboard", tags=["Onboard"])
app.include_router(insights_router, prefix="/api/insights", tags=["Insights"])
app.include_router(photo_router, prefix="/api/photo", tags=["Photo"])

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "CarbonCoach API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
