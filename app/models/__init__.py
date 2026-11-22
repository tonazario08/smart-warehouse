from app.anomalies.models import AnomalyAlert, AnomalyOutboundLink, AnomalyReview, AnomalyRun
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
from app.order_analytics.models import (
    OrderAnalyticsJob,
    OrderAnalyticsKeyState,
    OrderAnalyticsOrderCheck,
)

__all__ = [
    "AuditLog",
    "AnomalyAlert",
    "AnomalyOutboundLink",
    "AnomalyReview",
    "AnomalyRun",
    "Category",
    "Inbound",
    "MovementProvenance",
    "OrderAnalyticsJob",
    "OrderAnalyticsKeyState",
    "OrderAnalyticsOrderCheck",
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
