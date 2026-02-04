"""FastAPI application entry point for Yume."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.config import get_settings
from app.database import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan - startup and shutdown events."""
    # Startup
    print("Starting Yume API...")
    print(f"Environment: {settings.app_env}")
    print(f"Database: {settings.async_database_url.split('@')[-1]}")  # Hide credentials

    # Test database connection
    try:
        async with engine.connect() as conn:
            print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")

    yield

    # Shutdown
    print("Shutting down Yume API...")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="Yume API",
    description="WhatsApp-native AI scheduling assistant for beauty businesses in Mexico",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
# Build allowed origins list
allowed_origins = [
    settings.frontend_url,  # Render frontend URL or local
    "http://localhost:3000",  # Local development
]

# Add Render preview deployments in production
if not settings.is_development:
    allowed_origins.append("https://*.onrender.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if not settings.is_development else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": "Yume API",
        "version": "0.1.0",
        "description": "WhatsApp-native AI scheduling assistant",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Global health check."""
    return {"status": "ok"}
