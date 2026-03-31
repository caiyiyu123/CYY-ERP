from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.shop import Shop
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory
from app.models.product import SkuMapping
from app.utils.security import decrypt_token
from app.services.wb_api import fetch_orders, fetch_stocks

WB_STATUS_MAP = {
    0: "pending", 1: "pending", 2: "shipped", 3: "in_transit",
    5: "completed", 6: "cancelled", 7: "returned",
}


def sync_shop_orders(db: Session, shop: Shop):
    api_token = decrypt_token(shop.api_token)
    raw_orders = fetch_orders(api_token, date_from=shop.last_sync_at)
    for raw in raw_orders:
        wb_order_id = str(raw.get("id", ""))
        existing = db.query(Order).filter(Order.wb_order_id == wb_order_id).first()
        if existing:
            new_status = WB_STATUS_MAP.get(raw.get("status", 0), "pending")
            if existing.status != new_status:
                existing.status = new_status
                existing.updated_at = datetime.now(timezone.utc)
                log = OrderStatusLog(order_id=existing.id, status=new_status, wb_status=str(raw.get("status", "")))
                db.add(log)
            continue

        order_type = raw.get("orderType", "fbs").upper()
        status = WB_STATUS_MAP.get(raw.get("status", 0), "pending")
        order = Order(
            wb_order_id=wb_order_id, shop_id=shop.id, order_type=order_type,
            status=status, total_price=raw.get("totalPrice", 0),
            currency=raw.get("currency", "RUB"), delivery_address=raw.get("address", ""),
            warehouse_name=raw.get("warehouseName", ""),
        )
        db.add(order)
        db.flush()
        log = OrderStatusLog(order_id=order.id, status=status, wb_status=str(raw.get("status", "")))
        db.add(log)
        for p in raw.get("products", []):
            item = OrderItem(
                order_id=order.id, product_name=p.get("name", ""), sku=p.get("sku", ""),
                barcode=p.get("barcode", ""), quantity=p.get("quantity", 1),
                price=p.get("price", 0), commission=p.get("commission", 0),
                logistics_cost=p.get("logisticsCost", 0),
            )
            db.add(item)
            sku = p.get("sku", "")
            if sku:
                existing_mapping = db.query(SkuMapping).filter(
                    SkuMapping.shop_id == shop.id, SkuMapping.shop_sku == sku
                ).first()
                if not existing_mapping:
                    mapping = SkuMapping(
                        shop_id=shop.id, shop_sku=sku,
                        wb_product_name=p.get("name", ""), wb_barcode=p.get("barcode", ""),
                    )
                    db.add(mapping)
    shop.last_sync_at = datetime.now(timezone.utc)
    db.commit()


def sync_shop_inventory(db: Session, shop: Shop):
    api_token = decrypt_token(shop.api_token)
    stocks = fetch_stocks(api_token)
    sku_stocks: dict[str, dict] = {}
    for s in stocks:
        sku = s.get("sku", "")
        if sku not in sku_stocks:
            sku_stocks[sku] = {"name": s.get("name", ""), "barcode": s.get("barcode", ""), "fbs": 0, "fbw": 0}
        wh_name = s.get("warehouseName", "")
        if "FBW" in wh_name.upper() or s.get("warehouseId", 0) >= 100:
            sku_stocks[sku]["fbw"] += s.get("stock", 0)
        else:
            sku_stocks[sku]["fbs"] += s.get("stock", 0)
    for sku, data in sku_stocks.items():
        inv = db.query(Inventory).filter(Inventory.shop_id == shop.id, Inventory.sku == sku).first()
        if inv:
            inv.stock_fbs = data["fbs"]
            inv.stock_fbw = data["fbw"]
            inv.updated_at = datetime.now(timezone.utc)
        else:
            inv = Inventory(
                shop_id=shop.id, product_name=data["name"], sku=sku,
                barcode=data["barcode"], stock_fbs=data["fbs"], stock_fbw=data["fbw"],
            )
            db.add(inv)
    db.commit()
