from app.dashboard.schemas import DashboardStats


def test_dashboard_stats_accepts_nonnegative_database_aggregates() -> None:
    stats = DashboardStats(product_count=3, total_stock=29, low_stock_count=2)

    assert stats.model_dump() == {
        "product_count": 3,
        "total_stock": 29,
        "low_stock_count": 2,
    }
