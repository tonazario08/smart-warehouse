"""Bind the pre-existing forecast and replenishment fixtures to this isolated demo."""

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import Product, Stock, Warehouse


def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url)
    if (
        settings.app_env != "integration"
        or url.host != "db"
        or url.database != "smart_warehouse_full_demo"
        or url.username != "smart_warehouse_full_demo"
    ):
        raise SystemExit("Seed requires the isolated full demo database.")

    with Session(get_engine(settings.database_url)) as session, session.begin():
        product = session.get(Product, 1)
        central = session.get(Warehouse, 1)
        if product is None or product.sku != "DEMO-001":
            raise SystemExit("Unexpected base demo fixture binding.")
        if central is None or central.code != "HCM-01":
            raise SystemExit("Unexpected base demo fixture binding.")
        product.unit = "unit"
        central.latitude, central.longitude = 10.7767, 106.6921

        destination = session.scalar(select(Warehouse).where(Warehouse.code == "WH-DEMO-02"))
        if destination is None:
            destination = Warehouse(
                code="WH-DEMO-02",
                name="Kho demo bổ sung hàng",
                address="Điểm mẫu dùng để trình diễn",
                latitude=10.78077,
                longitude=106.70042,
            )
            session.add(destination)
            session.flush()
        if destination.id != 2:
            raise SystemExit("Unexpected destination warehouse binding.")
        stock = session.scalar(
            select(Stock).where(
                Stock.product_id == product.id, Stock.warehouse_id == destination.id
            )
        )
        if stock is None:
            session.add(Stock(product_id=product.id, warehouse_id=destination.id, quantity=2))
    print("Demo stock and warehouse bindings are ready.")


if __name__ == "__main__":
    main()
