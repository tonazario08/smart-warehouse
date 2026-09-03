from pydantic import BaseModel


class DashboardStats(BaseModel):
    product_count: int
    total_stock: int
    low_stock_count: int
