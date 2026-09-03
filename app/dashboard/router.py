from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.dashboard.schemas import DashboardStats
from app.db.session import get_session
from app.models import Product, Stock, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.DASHBOARD_READ))],
) -> DashboardStats:
    product_count = session.scalar(select(func.count()).select_from(Product)) or 0
    total_stock = session.scalar(select(func.coalesce(func.sum(Stock.quantity), 0))) or 0
    low_stock_count = (
        session.scalar(
            select(func.count()).select_from(
                select(Stock.id)
                .join(Product, Product.id == Stock.product_id)
                .where(Stock.quantity <= Product.reorder_level)
                .subquery()
            )
        )
        or 0
    )
    return DashboardStats(
        product_count=product_count,
        total_stock=total_stock,
        low_stock_count=low_stock_count,
    )
