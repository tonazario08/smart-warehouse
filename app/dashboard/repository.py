"""Database queries for dashboard read models."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dashboard.schemas import DashboardStats
from app.models import Product, Stock


class DashboardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_stats(self) -> DashboardStats:
        product_count = select(func.count(Product.id)).scalar_subquery()
        total_stock = select(func.coalesce(func.sum(Stock.quantity), 0)).scalar_subquery()
        low_stock_count = (
            select(func.count(Stock.id))
            .join(Product, Product.id == Stock.product_id)
            .where(Stock.quantity <= Product.reorder_level)
            .scalar_subquery()
        )
        row = self.session.execute(select(product_count, total_stock, low_stock_count)).one()
        return DashboardStats(
            product_count=row[0],
            total_stock=row[1],
            low_stock_count=row[2],
        )
