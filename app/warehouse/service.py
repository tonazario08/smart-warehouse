"""Warehouse use cases and transaction ownership."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.pagination import Page, PageParams
from app.models import Warehouse
from app.warehouse.repository import WarehouseRepository
from app.warehouse.schemas import WarehouseWrite


class WarehouseService:
    """Apply warehouse rules and commit or roll back warehouse mutations."""

    def __init__(self, session: Session, warehouses: WarehouseRepository) -> None:
        self.session = session
        self.warehouses = warehouses

    def list(self, params: PageParams, search: str | None = None) -> Page[Warehouse]:
        return Page[Warehouse](
            items=self.warehouses.list(params, search),
            total=self.warehouses.count(search),
            page=params.page,
            page_size=params.page_size,
        )

    def get(self, warehouse_id: int) -> Warehouse:
        warehouse = self.warehouses.get(warehouse_id)
        if warehouse is None:
            raise DomainError(404, "WAREHOUSE_NOT_FOUND", "Warehouse was not found.")
        return warehouse

    def create(self, request: WarehouseWrite) -> Warehouse:
        warehouse = Warehouse(**request.model_dump())
        try:
            self.warehouses.add(warehouse)
            self.session.commit()
            self.session.refresh(warehouse)
            return warehouse
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "WAREHOUSE_CONFLICT", "Warehouse code or name already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def update(self, warehouse_id: int, request: WarehouseWrite) -> Warehouse:
        warehouse = self.get(warehouse_id)
        self.warehouses.update(warehouse, request.model_dump())
        return self._commit_or_conflict(warehouse)

    def delete(self, warehouse_id: int) -> None:
        warehouse = self.get(warehouse_id)
        if self.warehouses.has_references(warehouse_id):
            raise DomainError(
                409, "WAREHOUSE_IN_USE", "Warehouse is referenced by another record."
            )
        try:
            self.warehouses.delete(warehouse)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "WAREHOUSE_IN_USE", "Warehouse is referenced by another record."
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def _commit_or_conflict(self, warehouse: Warehouse) -> Warehouse:
        try:
            self.session.commit()
            self.session.refresh(warehouse)
            return warehouse
        except IntegrityError as error:
            self.session.rollback()
            raise DomainError(
                409, "WAREHOUSE_CONFLICT", "Warehouse code or name already exists."
            ) from error
        except Exception:
            self.session.rollback()
            raise
