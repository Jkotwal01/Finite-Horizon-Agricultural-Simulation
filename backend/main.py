"""
main.py — FastAPI application entry point.

Serves both the REST API and the frontend static files.
"""
import sys, os

# Ensure backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router

app = FastAPI(
    title="Finite-Horizon Agricultural Simulation",
    description=(
        "AI-driven farm simulation. Maximize Terminal Wealth over 720 turns. "
        "Backend: FastAPI + Python. Frontend: HTML/CSS/JS."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register API routes
app.include_router(router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        """Serve the main dashboard page."""
        return FileResponse(os.path.join(frontend_dir, "index.html"))
