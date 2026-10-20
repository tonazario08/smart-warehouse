from app.models.domain import (
    Category,
    Inbound,
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Region,
    RouteLog,
    Stock,
    StockTransaction,
    StockTransfer,
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
    "MovementProvenance",
    "Outbound",
    "Product",
    "PurchaseRequest",
    "PurchaseRequestWorkflow",
    "Region",
    "RouteLog",
    "Stock",
    "StockTransaction",
    "StockTransfer",
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
