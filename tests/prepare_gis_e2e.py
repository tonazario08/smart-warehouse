"""Prepare the external synthetic road catalog or seed the isolated M10 E2E database."""

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.config import Settings
from app.gis.catalog import canonical_json, checked_path, manifest_id, verify_snapshot, write_graph
from app.gis.schemas import PUBLIC_BOUNDS, Edge, Graph, GraphStats, Manifest, Node, edge_weight
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import (
    Category,
    Inbound,
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Stock,
    StockTransaction,
    StockTransfer,
    User,
    UserRole,
    Warehouse,
)
from app.purchase_requests.repository import PurchaseRequestRepository
from app.purchase_requests.schemas import PurchaseRequestCreate
from app.purchase_requests.service import PurchaseRequestService
from app.transfers.repository import TransferRepository
from app.transfers.schemas import TransferCreate
from app.transfers.service import TransferService

PROJECT = "sw-m10-gis-e2e"
DATABASE = "sw_m10_gis_e2e"
CATALOG = Path("/catalog")
SEED_PATH = Path("/fixtures/prepare_gis_e2e.py")
PUBLIC_ID = "gsv1-83bb3fea3577b8821509cb5d7cbe0fd2de608965e81485045241bcdbd044f889"
SKU = "M10-GIS-SKU"
FIXTURE_ACTION = "m10.gis_e2e_fixture_v1"
FIXTURE_TYPE = "gis_e2e_fixture"
PERIOD_START = datetime(2026, 11, 1, 17, tzinfo=UTC)
PERIOD_END = datetime(2026, 11, 2, 17, tzinfo=UTC)
NODES = (
    Node(1, 106.6921, 10.7767),  # Approved real route origin.
    Node(2, 106.7002, 10.779),
    Node(3, 106.6947, 10.779),
    Node(4, 106.70042, 10.78077),  # Approved real route destination.
    Node(5, 106.715, 10.789),
    Node(6, 106.7155, 10.7893),
    Node(7, 106.697, 10.795),
    Node(8, 106.688, 10.79),
    Node(9, 106.69, 10.782),
)
WAREHOUSES = (
    ("ROAD", "Đường", NODES[0]),
    ("DETOUR", "Vòng", NODES[1]),
    ("NEAR", "Gần", NODES[3]),
    ("DISCONNECTED", "Rời", NODES[4]),
    ("NO-POINT", "Thiếu vị trí", None),
    ("OUTSIDE", "Ngoài vùng", Node(10, 106.8, 10.78)),
    ("NO-STOCK", "Chưa có tồn", NODES[2]),
)


class FixtureError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FixtureError(code)


def prepare_catalog(root: Path) -> str:
    checked_path(root, directory=True, create=True)
    workspace = Path(__file__).resolve().parents[1]
    require(not root.is_relative_to(workspace), "CATALOG_MUST_BE_EXTERNAL")
    root.mkdir()
    connections = ((1, 3), (3, 4), (2, 7), (7, 8), (8, 9), (9, 1), (5, 6), (6, 5))
    graph = Graph(
        NODES,
        tuple(
            Edge(i, i, source, target, edge_weight(NODES[source - 1], NODES[target - 1]))
            for i, (source, target) in enumerate(connections, 1)
        ),
        (),
    )
    graph_path = root / "graph.json"
    with graph_path.open("xb") as stream:
        graph_sha256 = write_graph(stream, graph)
    now = datetime.now(UTC).replace(microsecond=0)
    manifest = Manifest(
        dataset_class="synthetic_fixture",
        snapshot_at=now,
        prepared_at=now,
        source_url=None,
        source_sha256=None,
        graph_sha256=graph_sha256,
        bounds=PUBLIC_BOUNDS,
        license="synthetic_fixture",
        attribution="Synthetic fixture",
        stats=GraphStats(
            nodes=len(graph.nodes),
            edges=len(graph.edges),
            restrictions=0,
            excluded_access_ways=0,
            excluded_barrier_nodes=0,
            excluded_restrictions=0,
            excluded_restriction_ways=0,
        ),
    )
    contents = canonical_json(manifest.model_dump(mode="json"))
    snapshot_id = manifest_id(contents)
    output = root / snapshot_id
    output.mkdir()
    graph_path.rename(output / "graph.json")
    (output / "manifest.json").write_bytes(contents)
    verify_snapshot(root, snapshot_id, datetime.now(UTC), allow_fixture=True)
    return snapshot_id


def readonly_mount(target: Path) -> bool:
    for record in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        fields = record.split()
        if fields[4] == str(target) and "ro" in fields[5].split(","):
            return True
    return False


def check_environment():
    require(
        sys.platform.startswith("linux")
        and os.getuid() == 10001
        and Path(__file__).resolve() == SEED_PATH
        and Path.cwd() == Path("/app")
        and os.environ.get("M10_GIS_PROJECT") == PROJECT,
        "WRONG_M10_SEED_RUNTIME",
    )
    require(readonly_mount(CATALOG) and readonly_mount(SEED_PATH), "FIXTURE_MOUNTS_NOT_READ_ONLY")
    settings = Settings(_env_file=None)
    require(
        settings.app_env == "integration"
        and settings.gis_catalog_root == CATALOG
        and settings.gis_allow_fixture
        and settings.gis_snapshot_id is not None,
        "WRONG_M10_CONFIGURATION",
    )
    scenario = os.environ.get("M10_GIS_SCENARIO")
    require(scenario in ("synthetic", "public"), "WRONG_M10_SCENARIO")
    snapshot = verify_snapshot(CATALOG, settings.gis_snapshot_id, datetime.now(UTC), True)
    expected = "public_osm" if scenario == "public" else "synthetic_fixture"
    require(
        snapshot.manifest.dataset_class == expected
        and (scenario != "public" or snapshot.snapshot_id == PUBLIC_ID),
        "WRONG_M10_SNAPSHOT",
    )
    url = make_url(settings.database_url)
    require(
        (url.drivername, url.username, url.host, url.port, url.database)
        == ("postgresql+psycopg", DATABASE, "db", 5432, DATABASE)
        and bool(url.password)
        and dict(url.query) == {"application_name": PROJECT},
        "WRONG_M10_DATABASE_TARGET",
    )
    return url, scenario, snapshot.snapshot_id


def check_database(connection) -> None:
    result = connection.execute(text(
        "SELECT current_database(), current_user, current_schema(), pg_get_userbyid(datdba) "
        "FROM pg_database WHERE datname = current_database()"
    )).one()
    require(tuple(result) == (DATABASE, DATABASE, "public", DATABASE), "WRONG_M10_DATABASE_OWNER")
    head = ScriptDirectory.from_config(Config("/app/alembic.ini")).get_current_head()
    require(
        connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == head,
        "WRONG_M10_MIGRATION_HEAD",
    )
    connection.execute(text("SELECT pg_stat_clear_snapshot()"))
    competitors = connection.scalar(text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND pid <> pg_backend_pid() "
        "AND backend_type = 'client backend' "
        "AND (usename <> current_user OR application_name <> :app OR state = 'active')"
    ), {"app": PROJECT})
    require(competitors == 0, "M10_DATABASE_SESSION_CONFLICT")


def fixture_roles(session: Session) -> dict[UserRole, User]:
    roles = {}
    for role in UserRole:
        email = os.environ.get(f"SEED_{role.name}_EMAIL", "").strip().lower()
        user = session.scalar(select(User).where(User.email == email))
        require(user is not None and user.role == role and user.is_active, "M10_ROLE_NOT_SEEDED")
        roles[role] = user
    return roles


def fixture_digest(session: Session, product_id: int) -> str:
    transactions = select(StockTransaction.id).where(StockTransaction.product_id == product_id)
    requests = select(PurchaseRequest.id).where(PurchaseRequest.product_id == product_id)
    datasets = (
        (Product, Product.id == product_id),
        (Warehouse, Warehouse.code.startswith("M10-GIS-")),
        (Stock, Stock.product_id == product_id),
        (Inbound, Inbound.product_id == product_id),
        (Outbound, Outbound.product_id == product_id),
        (StockTransaction, StockTransaction.product_id == product_id),
        (MovementProvenance, MovementProvenance.transaction_id.in_(transactions)),
        (StockTransfer, StockTransfer.product_id == product_id),
        (PurchaseRequest, PurchaseRequest.product_id == product_id),
        (PurchaseRequestWorkflow, PurchaseRequestWorkflow.purchase_request_id.in_(requests)),
    )
    digest = hashlib.sha256()
    for model, predicate in datasets:
        table = model.__table__
        rows = session.execute(select(table).where(predicate).order_by(*table.primary_key.columns))
        digest.update(json.dumps(
            [table.name, [list(row) for row in rows]],
            default=str,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode())
    return digest.hexdigest()


def fixture_key(reference: str):
    return uuid5(NAMESPACE_URL, f"https://smart-warehouse.invalid/m10-gis/{reference}")


def set_movement_time(session: Session, transaction_id: int, stamp: datetime) -> None:
    transaction = session.get(StockTransaction, transaction_id)
    transaction.created_at = stamp
    if transaction.outbound_id is not None:
        session.get(Outbound, transaction.outbound_id).created_at = stamp
    if transaction.inbound_id is not None:
        session.get(Inbound, transaction.inbound_id).created_at = stamp


def seed_records(session: Session, roles: dict[UserRole, User]) -> int:
    admin, operator, client = (roles[role] for role in (UserRole.ADMIN, UserRole.WAREHOUSE,
                                                       UserRole.CLIENT))
    category = Category(name="Danh mục kiểm thử M10 GIS")
    product = Product(sku=SKU, name="Hàng kiểm thử M10", category=category, unit="hộp")
    sites = {}
    for code, title, node in WAREHOUSES:
        sites[code] = Warehouse(
            code=f"M10-GIS-{code}",
            name=f"Kho kiểm thử M10 {title}",
            address="Địa chỉ kiểm thử M10",
            latitude=node.latitude if node else None,
            longitude=node.longitude if node else None,
        )
    session.add_all([product, *sites.values()])
    session.flush()
    movements = InventoryService(InventoryRepository(session))
    for code, quantity in (("ROAD", 30), ("DETOUR", 8), ("DISCONNECTED", 8), ("NO-POINT", 10),
                           ("OUTSIDE", 6)):
        inbound = movements.create_inbound(operator.id, InventoryMovementCreate(
            warehouse_id=sites[code].id, product_id=product.id, quantity=quantity,
            reference=f"M10-GIS-IN-{code}",
        ))
        transaction_id = session.scalar(
            select(StockTransaction.id).where(StockTransaction.inbound_id == inbound.id)
        )
        set_movement_time(session, transaction_id, PERIOD_START - timedelta(days=1))

    purchases = PurchaseRequestService(PurchaseRequestRepository(session))
    purchases.create(client, fixture_key("destination"), PurchaseRequestCreate(
        warehouse_id=sites["NEAR"].id, product_id=product.id, quantity=5,
        note="M10-GIS-DESTINATION",
    ))
    for code, quantity, stamp, reference in (
        ("ROAD", 4, PERIOD_START, "M10-GIS-FULFILL-LOWER"),
        ("ROAD", 2, PERIOD_END, "M10-GIS-FULFILL-UPPER"),
        ("NO-POINT", 2, PERIOD_START + timedelta(hours=3), "M10-GIS-FULFILL-NO-POINT"),
    ):
        request, _ = purchases.create(client, fixture_key(reference), PurchaseRequestCreate(
            warehouse_id=sites[code].id, product_id=product.id, quantity=quantity, note=reference,
        ))
        purchases.approve(admin, request.id)
        result = purchases.fulfill(operator, request.id)
        set_movement_time(session, result.fulfillment.transaction_id, stamp)
        row = session.get(PurchaseRequest, request.id)
        row.created_at = stamp - timedelta(hours=2)
        row.updated_at = stamp
        workflow = session.get(PurchaseRequestWorkflow, request.id)
        workflow.decided_at = stamp - timedelta(hours=1)
        workflow.fulfilled_at = stamp

    transfers = TransferService(TransferRepository(session))
    for code, reference in (
        ("ROAD", "M10-GIS-TRANSFER"), ("DISCONNECTED", "M10-GIS-TRANSFER-LOST")
    ):
        transfer, _ = transfers.create(operator.id, fixture_key(reference), TransferCreate(
            source_warehouse_id=sites[code].id,
            destination_warehouse_id=sites["NEAR"].id,
            product_id=product.id,
            quantity=1,
            reference=reference,
        ))
        stamp = PERIOD_START + timedelta(hours=4)
        transfer.created_at = stamp
        set_movement_time(session, transfer.inbound_transaction_id, stamp)
        set_movement_time(session, transfer.outbound_transaction_id, stamp)

    outbound = movements.create_outbound(operator.id, InventoryMovementCreate(
        warehouse_id=sites["ROAD"].id, product_id=product.id, quantity=1,
        reference="M10-GIS-STANDARD-OUT",
    ))
    transaction_id = session.scalar(
        select(StockTransaction.id).where(StockTransaction.outbound_id == outbound.id)
    )
    set_movement_time(session, transaction_id, PERIOD_START + timedelta(hours=5))
    session.flush()
    return product.id


def seed_database() -> dict[str, str]:
    url, scenario, snapshot_id = check_environment()
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            check_database(connection)
            connection.execute(text("SET LOCAL lock_timeout = '3s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(301018082)"))
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                roles = fixture_roles(session)
                receipts = session.scalars(select(AuditLog).where(
                    AuditLog.action == FIXTURE_ACTION, AuditLog.target_type == FIXTURE_TYPE
                )).all()
                require(len(receipts) <= 1, "M10_FIXTURE_RECEIPT_CONFLICT")
                product_id = session.scalar(select(Product.id).where(Product.sku == SKU))
                if receipts:
                    receipt = receipts[0]
                    require(
                        product_id == receipt.target_id and receipt.after_data == {
                            "version": 1, "digest": fixture_digest(session, receipt.target_id)
                        },
                        "M10_FIXTURE_RECEIPT_MISMATCH",
                    )
                    state = "verified"
                else:
                    require(product_id is None, "M10_FIXTURE_WITHOUT_RECEIPT")
                    product_id = seed_records(session, roles)
                    session.add(AuditLog(
                        actor_user_id=roles[UserRole.ADMIN].id,
                        action=FIXTURE_ACTION,
                        target_type=FIXTURE_TYPE,
                        target_id=product_id,
                        after_data={"version": 1, "digest": fixture_digest(session, product_id)},
                    ))
                    session.commit()
                    state = "seeded"
        return {"state": state, "scenario": scenario, "snapshot_id": snapshot_id}
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action")
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.action == "catalog":
            result = {"state": "prepared", "snapshot_id": prepare_catalog(args.output)}
        else:
            result = seed_database()
    except FixtureError as failure:
        print(f"M10 fixture refused: {failure}", file=sys.stderr)
        return 1
    except Exception:
        print("M10 fixture preparation failed. Check the isolated runtime and fixture inputs.",
              file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
