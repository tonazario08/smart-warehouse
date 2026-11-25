"""Read-only dashboard use cases."""

from app.dashboard.repository import DashboardRepository
from app.dashboard.schemas import DashboardStats


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    def get_stats(self) -> DashboardStats:
        return self.repository.get_stats()
