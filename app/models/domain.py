from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    ADMIN = "admin"
    WAREHOUSE = "warehouse"
    CLIENT = "client"


class TransactionType(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class PurchaseRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FULFILLED = "fulfilled"


def enum_values(enum_type: type[Enum]) -> list[str]:
    return [member.value for member in enum_type]


class IdentifierMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class User(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Category(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    parent: Mapped[Category | None] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
    products: Mapped[list[Product]] = relationship("Product", back_populates="category")


class Supplier(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    products: Mapped[list[Product]] = relationship("Product", back_populates="supplier")


class Product(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("reorder_level >= 0", name="ck_products_reorder_level_nonnegative"),
    )

    sku: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[Category] = relationship("Category", back_populates="products")
    supplier: Mapped[Supplier | None] = relationship("Supplier", back_populates="products")
    stocks: Mapped[list[Stock]] = relationship("Stock", back_populates="product")


class Warehouse(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint("code = upper(trim(code))", name="ck_warehouses_code_normalized"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND "
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
            name="ck_warehouses_coordinates_paired_and_ranged",
        ),
    )

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    stocks: Mapped[list[Stock]] = relationship("Stock", back_populates="warehouse")


class Stock(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_stocks_warehouse_product"),
        CheckConstraint("quantity >= 0", name="ck_stocks_quantity_nonnegative"),
    )

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warehouse: Mapped[Warehouse] = relationship("Warehouse", back_populates="stocks")
    product: Mapped[Product] = relationship("Product", back_populates="stocks")


class Inbound(IdentifierMixin, Base):
    __tablename__ = "inbounds"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inbounds_quantity_positive"),
        Index(
            "ix_inbounds_warehouse_product_created_at", "warehouse_id", "product_id", "created_at"
        ),
    )

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Outbound(IdentifierMixin, Base):
    __tablename__ = "outbounds"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_outbounds_quantity_positive"),
        Index(
            "ix_outbounds_warehouse_product_created_at", "warehouse_id", "product_id", "created_at"
        ),
    )

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class StockTransaction(IdentifierMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transactions_quantity_positive"),
        CheckConstraint(
            "(transaction_type = 'inbound' AND inbound_id IS NOT NULL AND outbound_id IS NULL) OR "
            "(transaction_type = 'outbound' AND outbound_id IS NOT NULL AND inbound_id IS NULL)",
            name="ck_transactions_exactly_one_movement",
        ),
        Index(
            "ix_transactions_warehouse_product_type_created_at",
            "warehouse_id",
            "product_id",
            "transaction_type",
            "created_at",
        ),
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        SqlEnum(
            TransactionType,
            name="transaction_type",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    inbound_id: Mapped[int | None] = mapped_column(ForeignKey("inbounds.id", ondelete="RESTRICT"))
    outbound_id: Mapped[int | None] = mapped_column(ForeignKey("outbounds.id", ondelete="RESTRICT"))
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class StockTransfer(IdentifierMixin, Base):
    """One immediate transfer with immutable original balance snapshots."""

    __tablename__ = "stock_transfers"
    __table_args__ = (
        UniqueConstraint("created_by_id", "idempotency_key", name="uq_transfers_actor_key"),
        UniqueConstraint("outbound_id", name="uq_transfers_outbound"),
        UniqueConstraint("inbound_id", name="uq_transfers_inbound"),
        UniqueConstraint("outbound_transaction_id", name="uq_transfers_outbound_transaction"),
        UniqueConstraint("inbound_transaction_id", name="uq_transfers_inbound_transaction"),
        CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name="ck_transfers_distinct_warehouses",
        ),
        CheckConstraint(
            "quantity BETWEEN 1 AND 2147483647", name="ck_transfers_quantity_bounds"
        ),
        CheckConstraint(
            "source_quantity_before BETWEEN 0 AND 2147483647 AND "
            "source_quantity_after BETWEEN 0 AND 2147483647 AND "
            "destination_quantity_before BETWEEN 0 AND 2147483647 AND "
            "destination_quantity_after BETWEEN 0 AND 2147483647",
            name="ck_transfers_balance_bounds",
        ),
        Index("ix_transfers_created_at_id", "created_at", "id"),
    )

    source_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    destination_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    source_quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    outbound_id: Mapped[int] = mapped_column(
        ForeignKey("outbounds.id", ondelete="RESTRICT"), nullable=False
    )
    inbound_id: Mapped[int] = mapped_column(
        ForeignKey("inbounds.id", ondelete="RESTRICT"), nullable=False
    )
    outbound_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )
    inbound_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )


class MovementProvenance(Base):
    """Purpose is provenance, never a sales or demand assertion."""

    __tablename__ = "movement_provenance"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound', "
            "'transfer_in', 'transfer_out', 'purchase_request_fulfillment')",
            name="ck_provenance_purpose"
        ),
        CheckConstraint(
            "(purpose IN ('transfer_in', 'transfer_out') AND transfer_id IS NOT NULL) OR "
            "(purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound', "
            "'purchase_request_fulfillment') "
            "AND transfer_id IS NULL)", name="ck_provenance_transfer_link"
        ),
        Index("ix_provenance_transfer_id", "transfer_id"),
    )

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), primary_key=True
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    transfer_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_transfers.id", ondelete="RESTRICT"), nullable=True
    )
    transaction: Mapped[StockTransaction] = relationship("StockTransaction")


class Region(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class PurchaseRequest(IdentifierMixin, TimestampMixin, Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_requests_quantity_positive"),
        Index("ix_purchase_requests_owner_created_id", "requested_by_id", "created_at", "id"),
        Index("ix_purchase_requests_created_id", "created_at", "id"),
        Index("ix_purchase_requests_status_created_id", "status", "created_at", "id"),
    )

    request_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PurchaseRequestStatus] = mapped_column(
        SqlEnum(
            PurchaseRequestStatus,
            name="purchase_request_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
        ),
        default=PurchaseRequestStatus.PENDING,
        nullable=False,
    )
    requested_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class PurchaseRequestWorkflow(Base):
    """Durable managed history; base requests without this row remain legacy."""

    __tablename__ = "purchase_request_workflows"
    __table_args__ = (
        UniqueConstraint(
            "created_by_id", "idempotency_key", name="uq_purchase_request_workflows_actor_key"
        ),
        UniqueConstraint("outbound_id", name="uq_purchase_request_workflows_outbound"),
        UniqueConstraint(
            "outbound_transaction_id", name="uq_purchase_request_workflows_transaction"
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64 AND "
            "length(replace(replace(replace(replace(replace(replace(replace(replace("
            "replace(replace(replace(replace(replace(replace(replace(replace("
            "request_fingerprint,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),"
            "'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','')) = 0",
            name="ck_pr_workflow_fingerprint",
        ),
        CheckConstraint("note IS NULL OR length(note) <= 2000", name="ck_pr_workflow_note"),
        CheckConstraint(
            "(decision_kind IS NULL AND decided_by_id IS NULL AND decided_at IS NULL "
            "AND rejection_reason IS NULL) OR "
            "(decision_kind IS NOT NULL AND decision_kind = 'approved' "
            "AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL "
            "AND rejection_reason IS NULL) OR "
            "(decision_kind IS NOT NULL AND decision_kind = 'rejected' "
            "AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL "
            "AND rejection_reason IS NOT NULL AND rejection_reason = trim(rejection_reason, "
            "'\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
            "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000') "
            "AND length(rejection_reason) BETWEEN 1 AND 1000 "
            ")",
            name="ck_pr_workflow_decision",
        ),
        CheckConstraint(
            "(fulfilled_by_id IS NULL AND fulfilled_at IS NULL AND outbound_id IS NULL "
            "AND outbound_transaction_id IS NULL "
            "AND quantity_before IS NULL AND quantity_after IS NULL) OR "
            "(fulfilled_by_id IS NOT NULL AND fulfilled_at IS NOT NULL AND outbound_id IS NOT NULL "
            "AND outbound_transaction_id IS NOT NULL AND quantity_before IS NOT NULL "
            "AND quantity_after IS NOT NULL AND decision_kind IS NOT NULL "
            "AND decision_kind = 'approved')",
            name="ck_pr_workflow_fulfillment",
        ),
        CheckConstraint(
            "(quantity_before IS NULL AND quantity_after IS NULL) OR "
            "(quantity_before IS NOT NULL AND quantity_after IS NOT NULL "
            "AND quantity_after >= 0 AND quantity_after < quantity_before "
            "AND quantity_before <= 2147483647)",
            name="ck_pr_workflow_balances",
        ),
    )

    purchase_request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="RESTRICT"), primary_key=True
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    decision_kind: Mapped[str | None] = mapped_column(String(8))
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    fulfilled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outbound_id: Mapped[int | None] = mapped_column(ForeignKey("outbounds.id", ondelete="RESTRICT"))
    outbound_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT")
    )
    quantity_before: Mapped[int | None] = mapped_column(Integer)
    quantity_after: Mapped[int | None] = mapped_column(Integer)


class RouteLog(IdentifierMixin, Base):
    __tablename__ = "route_logs"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    route_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


Index("uq_users_email_lower", func.lower(User.email), unique=True)
Index("uq_products_sku_upper", func.upper(Product.sku), unique=True)
Index("uq_warehouses_code_upper", func.upper(Warehouse.code), unique=True)
