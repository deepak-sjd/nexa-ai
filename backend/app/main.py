from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import users, conversations,message


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


app.include_router(
    users.router,
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