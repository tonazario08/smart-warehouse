from app.anomalies.models import AnomalyAlert, AnomalyReview, AnomalyRun
from app.auth.recovery_models import PasswordRecoveryBudget, PasswordResetToken
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
    "AnomalyAlert",
    "AnomalyReview",
    "AnomalyRun",
    "Category",
    "Inbound",
    "MovementProvenance",
    "Outbound",
    "PasswordRecoveryBudget",
    "PasswordResetToken",
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
