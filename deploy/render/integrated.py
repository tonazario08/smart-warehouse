"""Admit only the reviewed synthetic catalogs to the dedicated Render demo."""

import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.anomalies.catalog import verify_run
from app.anomalies.service import AnomalyService
from app.cold_start.catalog import read_report
from app.db.session import get_engine
from app.forecasting.repository import verify_catalog_run
from app.models import Product, Stock, User, Warehouse
from app.replenishment.artifacts import verify_public_projection

BUNDLE_LIMIT = 4 * 1024 * 1024
EXPANDED_LIMIT = 24 * 1024 * 1024
BINDING = (70004001, 70004002, "unit")
DEMO_SKU = "DEMO-ANALYTICS-001"
DEMO_WAREHOUSE = "WH-ANALYTICS-DEMO"
MEMBERS = (
    re.compile(
        r"forecast/operational/frv1-[0-9a-f]{64}/"
        r"(?:metrics\.json|predictions\.jsonl|public-manifest\.json)"
    ),
    re.compile(
        r"replenishment/operational/rrv1-[0-9a-f]{64}/"
        r"(?:calibration\.json|days\.jsonl|orders\.jsonl|summaries\.json|public-manifest\.json)"
    ),
    re.compile(r"cold-start/csv1-[0-9a-f]{64}"),
    re.compile(r"anomaly/arv1-[0-9a-f]{64}\.json"),
)


def extract_bundle(archive: Path, target: Path) -> None:
    with ZipFile(archive) as bundle:
        entries = bundle.infolist()
        names = {entry.filename for entry in entries}
        if (
            len(entries) != 11
            or len(names) != len(entries)
            or "manifest.json" not in names
            or sum(entry.file_size for entry in entries) > EXPANDED_LIMIT
            or any(
                not any(pattern.fullmatch(name) for pattern in MEMBERS)
                for name in names - {"manifest.json"}
            )
        ):
            raise ValueError("Unexpected bundle members")
        target.mkdir()
        for entry in entries:
            destination = target / entry.filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(bundle.read(entry))


def prepare_bundle(url: str, checksum: str, root: Path, download):
    release = urlsplit(url)
    parts = release.path.strip("/").split("/")
    if (
        release.scheme != "https" or release.netloc != "github.com"
        or len(parts) != 6 or parts[2:4] != ["releases", "download"]
        or not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", parts[5])
        or release.query or release.fragment
    ):
        raise ValueError("Expected an HTTPS GitHub Release bundle URL")
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Invalid bundle checksum format")
    archive = root / "bundle.zip"
    download(url, archive, BUNDLE_LIMIT)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
        raise ValueError("Synthetic bundle checksum mismatch")
    target = root / "catalogs"
    extract_bundle(archive, target)
    run = verify_catalogs(target)
    archive.unlink()
    return target, run


def verify_catalogs(root: Path):
    forecast_dir, = (root / "forecast" / "operational").iterdir()
    policy_dir, = (root / "replenishment" / "operational").iterdir()
    cold, = (root / "cold-start").iterdir()
    anomaly, = (root / "anomaly").iterdir()
    forecast = verify_catalog_run(forecast_dir, allow_fixture=True)
    policy = verify_public_projection(policy_dir)
    binding = forecast.manifest.binding
    policy_binding = tuple(policy["binding"][key] for key in ("product_id", "warehouse_id", "unit"))
    if (
        forecast.manifest.dataset_class != "fixture"
        or policy["dataset_class"] != "fixture"
        or policy["forecast_run_id"] != forecast.manifest.run_id
        or binding is None or (binding.product_id, binding.warehouse_id, binding.unit) != BINDING
        or policy_binding != BINDING
    ):
        raise ValueError("Unexpected synthetic catalog binding")
    read_report(cold.parent, cold.name)
    run = verify_run(anomaly.parent, anomaly.stem)
    if not any(alert.explanation.state == "available" for alert in run.payload.alerts):
        raise ValueError("Synthetic anomaly run has no explainable alerts")
    return run


def seed_analytics(database_url: str, admin_email: str, run) -> None:
    product_id, warehouse_id, unit = BINDING
    with Session(get_engine(database_url)) as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": product_id})
        product = session.scalars(select(Product).where(
            or_(Product.id == product_id, Product.sku == DEMO_SKU)
        )).one_or_none()
        warehouse = session.scalars(select(Warehouse).where(
            or_(Warehouse.id == warehouse_id, Warehouse.code == DEMO_WAREHOUSE)
        )).one_or_none()
        if product is None and warehouse is None:
            category_id = session.scalar(
                select(Product.category_id).where(Product.sku == "DEMO-001")
            )
            if category_id is None:
                raise ValueError("Base demo product is required")
            product = Product(
                id=product_id, sku=DEMO_SKU, name="Sản phẩm mô phỏng phân tích",
                category_id=category_id, unit=unit,
            )
            warehouse = Warehouse(
                id=warehouse_id, code=DEMO_WAREHOUSE, name="Kho mô phỏng phân tích",
                address="Điểm kiểm thử tại TP. Hồ Chí Minh", latitude=10.78077, longitude=106.70042,
            )
            session.add(Stock(product=product, warehouse=warehouse, quantity=2))
            session.flush()
        if (
            product is None
            or (product.id, product.sku, product.unit) != (product_id, DEMO_SKU, unit)
            or warehouse is None or (warehouse.id, warehouse.code) != (warehouse_id, DEMO_WAREHOUSE)
        ):
            raise ValueError("Reserved demo identity collides with existing data")
        actor_id = session.scalar(select(User.id).where(User.email == admin_email))
        if actor_id is None:
            raise ValueError("Configured demo actor missing")
        AnomalyService(session, app_env="integration", allow_fixture=True).import_run(actor_id, run)
