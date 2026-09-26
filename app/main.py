from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, register_exception_handlers
from app.dashboard.router import router as dashboard_router
from app.db.session import get_session
from app.inventory.router import router as inventory_router
from app.master_data.router import router as master_data_router
from app.users.router import router as users_router
from app.warehouse.router import router as warehouse_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the versioned Smart Warehouse API application."""
    settings = settings or get_settings()
    application = FastAPI(title=settings.app_name, version="0.1.0")
    application.dependency_overrides[get_settings] = lambda: settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(master_data_router, prefix=settings.api_v1_prefix)
    application.include_router(warehouse_router, prefix=settings.api_v1_prefix)
    application.include_router(inventory_router, prefix=settings.api_v1_prefix)
    application.include_router(dashboard_router, prefix=settings.api_v1_prefix)
    application.include_router(users_router, prefix=settings.api_v1_prefix)
    application.include_router(audit_router, prefix=settings.api_v1_prefix)
    register_exception_handlers(application)

    @application.get(f"{settings.api_v1_prefix}/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(f"{settings.api_v1_prefix}/health/live", tags=["system"])
    def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @application.get(f"{settings.api_v1_prefix}/health/ready", tags=["system"])
    def readiness(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise DomainError(503, "DATABASE_UNAVAILABLE", "Database is unavailable.") from error
        return {"status": "ready"}

    return application


app = create_app()
