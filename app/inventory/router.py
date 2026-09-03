from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import Permission, require_permission
from app.db.session import get_session
from app.inventory.schemas import (
    InventoryMovementCreate,
    InventoryMovementResponse,
    StockResponse,
    TransactionResponse,
)
from app.models import (
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    User,
    Warehouse,
)

router = APIRouter(tags=["inventory"])


def _validate_references(session: Session, movement: InventoryMovementCreate) -> None:
    if session.get(Warehouse, movement.warehouse_id) is None:
        raise HTTPException(status_code=422, detail="Warehouse does not exist")
    if session.get(Product, movement.product_id) is None:
        raise HTTPException(status_code=422, detail="Product does not exist")


@router.get("/stock", response_model=list[StockResponse])
def list_stock(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
    warehouse_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
) -> list[Stock]:
    statement = select(Stock).order_by(Stock.id)
    if warehouse_id is not None:
        statement = statement.where(Stock.warehouse_id == warehouse_id)
    if product_id is not None:
        statement = statement.where(Stock.product_id == product_id)
    return list(session.scalars(statement))


@router.post(
    "/inbounds", response_model=InventoryMovementResponse, status_code=status.HTTP_201_CREATED
)
def create_inbound(
    movement: InventoryMovementCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_WRITE))],
) -> Inbound:
    _validate_references(session, movement)
    stock = session.scalar(
        select(Stock)
        .where(Stock.warehouse_id == movement.warehouse_id, Stock.product_id == movement.product_id)
        .with_for_update()
    )
    if stock is None:
        stock = Stock(
            warehouse_id=movement.warehouse_id, product_id=movement.product_id, quantity=0
        )
        session.add(stock)
        session.flush()
    stock.quantity += movement.quantity
    inbound = Inbound(**movement.model_dump(), created_by_id=user.id)
    session.add(inbound)
    session.flush()
    session.add(
        StockTransaction(
            transaction_type=TransactionType.INBOUND,
            warehouse_id=movement.warehouse_id,
            product_id=movement.product_id,
            quantity=movement.quantity,
            inbound_id=inbound.id,
            created_by_id=user.id,
        )
    )
    session.commit()
    session.refresh(inbound)
    return inbound


@router.post(
    "/outbounds", response_model=InventoryMovementResponse, status_code=status.HTTP_201_CREATED
)
def create_outbound(
    movement: InventoryMovementCreate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_permission(Permission.INVENTORY_WRITE))],
) -> Outbound:
    _validate_references(session, movement)
    stock = session.scalar(
        select(Stock)
        .where(Stock.warehouse_id == movement.warehouse_id, Stock.product_id == movement.product_id)
        .with_for_update()
    )
    if stock is None or stock.quantity < movement.quantity:
        raise HTTPException(status_code=409, detail="Insufficient stock")
    stock.quantity -= movement.quantity
    outbound = Outbound(**movement.model_dump(), created_by_id=user.id)
    session.add(outbound)
    session.flush()
    session.add(
        StockTransaction(
            transaction_type=TransactionType.OUTBOUND,
            warehouse_id=movement.warehouse_id,
            product_id=movement.product_id,
            quantity=movement.quantity,
            outbound_id=outbound.id,
            created_by_id=user.id,
        )
    )
    session.commit()
    session.refresh(outbound)
    return outbound


@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_permission(Permission.INVENTORY_READ))],
) -> list[StockTransaction]:
    return list(session.scalars(select(StockTransaction).order_by(StockTransaction.id)))
