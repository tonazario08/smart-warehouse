from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import Permission, require_permission
from app.dashboard.repository import DashboardRepository
from app.dashboard.schemas import DashboardStats
from app.dashboard.service import DashboardService
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    session: Annotated[object, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.DASHBOARD_READ))],
) -> DashboardStats:
    return DashboardService(DashboardRepository(session)).get_stats()
