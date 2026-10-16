from app.models.domain import (
    Category,
    Inbound,
    Outbound,
    Product,
    PurchaseRequest,
    Region,
    RouteLog,
    Stock,
    StockTransaction,
    Supplier,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)

__all__ = [
    "AuditLog",
    "Category",
    "Inbound",
    "Outbound",
    "Product",
    "PurchaseRequest",
    "Region",
    "RouteLog",
    "Stock",
    "StockTransaction",
    "Supplier",
    "TransactionType",
    "User",
    "UserRole",
    "Warehouse",
]


def __getattr__(name: str) -> object:
    if name == "AuditLog":
        from app.audit.models import AuditLog

        return AuditLog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
