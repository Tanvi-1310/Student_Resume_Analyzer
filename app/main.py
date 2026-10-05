"""Main application entrypoint for the Student Resume Analyzer service."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core import settings
from app.schemas import HealthResponse

# Application Factory / Initialization
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "An academically defensible backend for student resume structure evaluation, "
        "ATS formatting checks, and skill alignment analysis."
    ),
    version=settings.VERSION,
    debug=settings.APP_DEBUG,
)

# Cross-Origin Resource Sharing (CORS) Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
from app.api import evaluation_router, resumes_router

app.include_router(resumes_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")

# Core System Endpoints
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Returns the operational status, application name, and version.",
)
async def health_check() -> HealthResponse:
    """Return application health and metadata."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.VERSION,
    )

# Static Frontend Assets and UI Serving
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    css_path = FRONTEND_DIR / "css"
    js_path = FRONTEND_DIR / "js"

    if css_path.exists():
        app.mount("/css", StaticFiles(directory=css_path), name="css")
    if js_path.exists():
        app.mount("/js", StaticFiles(directory=js_path), name="js")

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        """Serve the landing frontend page."""
        return FileResponse(FRONTEND_DIR / "index.html")
