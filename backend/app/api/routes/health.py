from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Report safe service configuration status")
async def health() -> HealthResponse:
    settings = get_settings()
    database = "configured" if settings.database_url else "not_configured"
    status = "ok" if database == "configured" else "degraded"
    return HealthResponse(
        status=status,
        service="careerpilot-api",
        database=database,
        environment=settings.app_env,
    )
