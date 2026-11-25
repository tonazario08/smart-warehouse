from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.anomalies.operational_router import router as operational_anomaly_router
from app.anomalies.router import router as anomaly_router
from app.assistant.router import RateLimiter
from app.assistant.router import router as assistant_router
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.cold_start.router import router as cold_start_router
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, register_exception_handlers
from app.dashboard.router import router as dashboard_router
from app.db.session import get_session
from app.forecasting.router import router as forecast_router
from app.gis.router import router as gis_router
from app.gis.service import SnapshotCatalog
from app.inventory.router import router as inventory_router
from app.master_data.router import router as master_data_router
from app.order_analytics.router import router as order_analytics_router
from app.purchase_requests.delivery_geocode import DeliveryGeocoder
from app.purchase_requests.delivery_map import DeliveryMapCatalog
from app.purchase_requests.router import router as purchase_request_router
from app.replenishment.router import router as replenishment_router
from app.transfers.router import router as transfer_router
from app.users.router import router as users_router
from app.warehouse.router import router as warehouse_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the versioned Smart Warehouse API application."""
    settings = settings or get_settings()
    application = FastAPI(title=settings.app_name, version="0.1.0")
    application.dependency_overrides[get_settings] = lambda: settings
    application.state.assistant_rate_limiter = RateLimiter()
    application.state.gis_catalog = SnapshotCatalog(settings)
    application.state.delivery_geocoder = DeliveryGeocoder(
        settings.b2b_address_index_path if settings.b2b_address_index_sha256 else None,
        settings.b2b_address_index_sha256,
    )
    application.state.delivery_map_catalog = DeliveryMapCatalog(
        settings.b2b_delivery_map_path, settings.b2b_delivery_map_sha256,
    )

    @application.middleware("http")
    async def protect_delivery_lookup_response(request: Request, call_next):
        response = await call_next(request)
        if request.url.path in (
            f"{settings.api_v1_prefix}/purchase-requests/geocode-delivery-address",
            f"{settings.api_v1_prefix}/purchase-requests/delivery-map",
        ):
            if response.status_code == 422:
                # A malformed object can use an arbitrary private string as a field
                # name, so the general validation field-path representation is unsafe.
                return JSONResponse(
                    status_code=422,
                    content={"detail": {"code": "REQUEST_VALIDATION_ERROR",
                                        "message": "Request validation failed.", "fields": {}}},
                    headers={"Cache-Control": "no-store"},
                )
            response.headers["Cache-Control"] = "no-store"
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(assistant_router, prefix=settings.api_v1_prefix)
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(anomaly_router, prefix=settings.api_v1_prefix)
    application.include_router(operational_anomaly_router, prefix=settings.api_v1_prefix)
    application.include_router(master_data_router, prefix=settings.api_v1_prefix)
    application.include_router(warehouse_router, prefix=settings.api_v1_prefix)
    application.include_router(inventory_router, prefix=settings.api_v1_prefix)
    application.include_router(gis_router, prefix=settings.api_v1_prefix)
    application.include_router(dashboard_router, prefix=settings.api_v1_prefix)
    application.include_router(cold_start_router, prefix=settings.api_v1_prefix)
    application.include_router(forecast_router, prefix=settings.api_v1_prefix)
    application.include_router(replenishment_router, prefix=settings.api_v1_prefix)
    application.include_router(users_router, prefix=settings.api_v1_prefix)
    application.include_router(audit_router, prefix=settings.api_v1_prefix)
    application.include_router(transfer_router, prefix=settings.api_v1_prefix)
    application.include_router(purchase_request_router, prefix=settings.api_v1_prefix)
    application.include_router(order_analytics_router, prefix=settings.api_v1_prefix)
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
