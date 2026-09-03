from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.dashboard.router import router as dashboard_router
from app.inventory.router import router as inventory_router
from app.master_data.router import router as master_data_router
from app.warehouse.router import router as warehouse_router


def create_app() -> FastAPI:
    """Create the versioned Smart Warehouse API application."""
    application = FastAPI(title="Smart Warehouse API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(master_data_router, prefix="/api/v1")
    application.include_router(warehouse_router, prefix="/api/v1")
    application.include_router(inventory_router, prefix="/api/v1")
    application.include_router(dashboard_router, prefix="/api/v1")

    @application.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
