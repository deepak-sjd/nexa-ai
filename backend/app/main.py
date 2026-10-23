import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging_config import configure_logging

from app.api.routes import (
    auth,
    conversations,
    message,
    documents,
)

configure_logging(debug=settings.debug)

logger = logging.getLogger(__name__)

is_production = settings.app_env.lower() == "production"

if is_production and settings.mock_image_generation:
    raise RuntimeError(
        "MOCK_IMAGE_GENERATION must be off when APP_ENV=production."
    )

if is_production and (
    settings.jwt_secret == "dev-only-secret-change-me"
    or len(settings.jwt_secret) < 32
):
    raise RuntimeError(
        "Set JWT_SECRET (32+ random characters) when APP_ENV=production."
    )

if is_production and settings.debug:
    logger.warning("DEBUG is on in production - set DEBUG=false.")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    # Hide the interactive API docs from the public in production.
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(
    auth.router,
    prefix="/api/v1",
)

app.include_router(
    conversations.router,
    prefix="/api/v1",
)

app.include_router(
    message.router,
    prefix="/api/v1",
)

app.include_router(
    documents.router,
    prefix="/api/v1",
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }