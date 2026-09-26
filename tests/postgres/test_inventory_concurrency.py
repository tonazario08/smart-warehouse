"""PostgreSQL concurrency tests use independent sessions and database lock evidence."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep

from sqlalchemy import event, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)


def seed_inventory(postgres_session: Session) -> tuple[int, int, int]:
    user = User(
        email="concurrency-operator@example.com",
        password_hash="test",
        role=UserRole.WAREHOUSE,
    )
    warehouse = Warehouse(code="CC-01", name="Concurrency warehouse", address="Test road")
    product = Product(
        sku="CC-SKU-01",
        name="Concurrency product",
        category=Category(name="Concurrency"),
        unit="each",
    )
    postgres_session.add_all([user, warehouse, product])
    postgres_session.commit()
    return user.id, warehouse.id, product.id


def counts(session: Session) -> dict[str, int]:
    return {
        "inbounds": session.scalar(select(func.count()).select_from(Inbound)) or 0,
        "outbounds": session.scalar(select(func.count()).select_from(Outbound)) or 0,
        "transactions": session.scalar(select(func.count()).select_from(StockTransaction)) or 0,
        "audits": session.scalar(text("SELECT count(*) FROM audit_logs")) or 0,
    }


def test_concurrent_first_inbounds_do_not_lose_quantity(postgres_session, postgres_engine) -> None:
    operator_id, warehouse_id, product_id = seed_inventory(postgres_session)
    barrier = Barrier(2)

    def receive(quantity: int) -> None:
        with Session(postgres_engine) as session:
            barrier.wait(timeout=10)
            InventoryService(InventoryRepository(session)).create_inbound(
                operator_id,
                InventoryMovementCreate(
                    warehouse_id=warehouse_id, product_id=product_id, quantity=quantity
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(receive, quantity) for quantity in (7, 11)]
        for future in futures:
            future.result(timeout=20)

    with Session(postgres_engine) as check:
        stock = check.scalar(
            select(Stock).where(
                Stock.warehouse_id == warehouse_id, Stock.product_id == product_id
            )
        )
        assert stock is not None and stock.quantity == 18
        assert counts(check) == {"inbounds": 2, "outbounds": 0, "transactions": 2, "audits": 0}


def test_competing_outbounds_cannot_oversell(postgres_session, postgres_engine) -> None:
    operator_id, warehouse_id, product_id = seed_inventory(postgres_session)
    postgres_session.add(Stock(warehouse_id=warehouse_id, product_id=product_id, quantity=10))
    postgres_session.commit()
    barrier = Barrier(2)

    def ship() -> str:
        with Session(postgres_engine) as session:
            barrier.wait(timeout=10)
            try:
                InventoryService(InventoryRepository(session)).create_outbound(
                    operator_id,
                    InventoryMovementCreate(
                        warehouse_id=warehouse_id, product_id=product_id, quantity=7
                    ),
                )
                return "ok"
            except DomainError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(ship) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]

    assert sorted(results) == ["INSUFFICIENT_STOCK", "ok"]
    with Session(postgres_engine) as check:
        stock = check.scalar(
            select(Stock).where(
                Stock.warehouse_id == warehouse_id, Stock.product_id == product_id
            )
        )
        assert stock is not None and stock.quantity == 3
        assert counts(check) == {"inbounds": 0, "outbounds": 1, "transactions": 1, "audits": 0}


def test_waiting_outbound_uses_quantity_committed_by_inbound(
    postgres_session, postgres_engine
) -> None:
    operator_id, warehouse_id, product_id = seed_inventory(postgres_session)
    stock = Stock(warehouse_id=warehouse_id, product_id=product_id, quantity=5)
    postgres_session.add(stock)
    postgres_session.commit()

    holder = Session(postgres_engine)
    held_stock = holder.scalar(
        select(Stock)
        .where(Stock.warehouse_id == warehouse_id, Stock.product_id == product_id)
        .with_for_update()
    )
    assert held_stock is not None
    held_stock.quantity += 5
    inbound = Inbound(
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=5,
        created_by_id=operator_id,
    )
    holder.add(inbound)
    holder.flush()
    holder.add(
        StockTransaction(
            transaction_type=TransactionType.INBOUND,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=5,
            inbound_id=inbound.id,
            created_by_id=operator_id,
        )
    )
    waiting_for_lock = Event()
    worker_pid: list[int] = []

    def observe_lock_query(
        connection, cursor, statement: str, parameters, context, executemany
    ) -> None:
        if "FOR UPDATE" in statement.upper():
            waiting_for_lock.set()

    def ship() -> str:
        with Session(postgres_engine) as session:
            worker_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            return InventoryService(InventoryRepository(session)).create_outbound(
                operator_id,
                InventoryMovementCreate(
                    warehouse_id=warehouse_id, product_id=product_id, quantity=8
                ),
            ).id.__str__()

    event.listen(Engine, "before_cursor_execute", observe_lock_query)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(ship)
            assert waiting_for_lock.wait(timeout=10), "outbound never attempted the row lock"
            deadline = monotonic() + 10
            database_observed_wait = False
            while monotonic() < deadline:
                with postgres_engine.connect() as observer:
                    blocked = observer.scalar(
                        text(
                            "SELECT cardinality(pg_blocking_pids(:pid)) > 0 "
                            "FROM pg_stat_activity WHERE pid = :pid"
                        ),
                        {"pid": worker_pid[0]},
                    )
                if blocked:
                    database_observed_wait = True
                    break
                sleep(0.02)
            assert database_observed_wait, (
                "PostgreSQL did not report the outbound blocked by the inbound lock"
            )
            holder.commit()
            outbound_id = int(future.result(timeout=20))
    finally:
        event.remove(Engine, "before_cursor_execute", observe_lock_query)
        holder.close()

    with Session(postgres_engine) as check:
        final_stock = check.scalar(
            select(Stock).where(
                Stock.warehouse_id == warehouse_id, Stock.product_id == product_id
            )
        )
        outbound = check.get(Outbound, outbound_id)
        assert final_stock is not None and final_stock.quantity == 2
        assert outbound is not None and outbound.quantity == 8
        assert counts(check) == {"inbounds": 1, "outbounds": 1, "transactions": 2, "audits": 0}
