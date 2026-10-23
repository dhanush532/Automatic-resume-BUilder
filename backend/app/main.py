from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.request_limits import ReviewBodyLimit


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Connections are created per request/session rather than at import time.
    # This keeps the health endpoint useful before PostgreSQL is configured.
    yield


def create_application() -> FastAPI:
    from app.auth.logging import protect_auth_logs
    protect_auth_logs()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json" if settings.docs_enabled else None,
        docs_url=f"{settings.api_prefix}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(ReviewBodyLimit, prefix=f"{settings.api_prefix}/review")
    app.add_middleware(ReviewBodyLimit, prefix=f"{settings.api_prefix}/interviews")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID", "X-CSRF-Token"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(request, error):
        # Pydantic's default errors include raw inputs, potentially passwords/OTPs.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(item["loc"]), "msg": item["msg"].removeprefix("Value error, "), "type": item["type"]}
            for item in error.errors()]})
    from app.auth.tokens import AuthenticationConfigurationError
    @app.exception_handler(AuthenticationConfigurationError)
    async def authentication_configuration_error(request, error):
        return JSONResponse(status_code=503, content={"detail": "Authentication configuration is unavailable. Contact the administrator."})
    return app


app = create_application()
