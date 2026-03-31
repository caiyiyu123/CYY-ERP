from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.shop import Shop
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory
from app.models.product import SkuMapping
from app.utils.security import decrypt_token
from app.services.wb_api import (
    fetch_new_orders, fetch_orders, fetch_order_statuses,
    fetch_warehouses, fetch_stocks, fetch_cards,
)

# WB supplier status → system status
SUPPLIER_STATUS_MAP = {
    "new": "pending",
    "confirm": "pending",
    "complete": "shipped",
    "cancel": "cancelled",
}

# WB platform status → system status
WB_STATUS_MAP = {
    "waiting": "pending",
    "sorted": "in_transit",
    "sold": "completed",
    "canceled": "cancelled",
    "canceled_by_client": "cancelled",
    "declined_by_client": "cancelled",
    "defect": "returned",
    "ready_for_pickup": "in_transit",
    "delivered": "completed",
}

# Currency code mapping (WB uses numeric codes)
CURRENCY_MAP = {
    643: "RUB",
    840: "USD",
    978: "EUR",
    933: "BYN",
    398: "KZT",
    156: "CNY",
}


def _resolve_status(supplier_status: str, wb_status: str) -> str:
    """Determine system status from WB supplier and platform statuses.

    Priority: wb_status (platform) > supplier_status (seller side).
    """
    if wb_status and wb_status in WB_STATUS_MAP:
        return WB_STATUS_MAP[wb_status]
    if supplier_status and supplier_status in SUPPLIER_STATUS_MAP:
        return SUPPLIER_STATUS_MAP[supplier_status]
    return "pending"


def sync_shop_orders(db: Session, shop: Shop):
    """Sync orders for a shop: fetch new + historical orders, then update statuses."""
    api_token = decrypt_token(shop.api_token)

    # Step 1: Fetch new orders (awaiting processing)
    new_orders = fetch_new_orders(api_token)

    # Step 2: Fetch historical orders (incremental from last sync)
    historical_orders = fetch_orders(api_token, date_from=shop.last_sync_at)

    # Merge all orders, deduplicate by id
    all_raw_orders = {}
    for raw in new_orders + historical_orders:
        order_id = raw.get("id")
        if order_id:
            all_raw_orders[order_id] = raw

    # Step 3: Build nmId → card info lookup from product cards
    cards = fetch_cards(api_token)
    nm_card_map = {}
    for card in cards:
        nm_id = card.get("nmID")
        if nm_id:
            nm_card_map[nm_id] = {
                "name": card.get("title", ""),
                "vendorCode": card.get("vendorCode", ""),
                "photos": card.get("photos", []),
            }

    # Step 4: Save/update orders
    wb_order_ids = []
    for wb_id, raw in all_raw_orders.items():
        wb_order_id = str(wb_id)
        wb_order_ids.append(wb_id)

        existing = db.query(Order).filter(Order.wb_order_id == wb_order_id).first()
        if existing:
            continue  # Status update handled in batch below

        # Parse order fields from WB API response
        price_kopecks = raw.get("convertedPrice", raw.get("price", 0))
        price = price_kopecks / 100.0  # Convert kopecks to rubles
        currency_code = raw.get("currencyCode", 643)
        currency = CURRENCY_MAP.get(currency_code, "RUB")
        warehouse_id = raw.get("warehouseId", 0)
        nm_id = raw.get("nmId", 0)
        chrt_id = raw.get("chrtId", 0)
        article = raw.get("article", "")
        skus = raw.get("skus", [])
        created_at_str = raw.get("createdAt", "")

        # Determine order type: all orders from /api/v3/orders are FBS
        order_type = "FBS"

        # Parse created time
        order_created = None
        if created_at_str:
            try:
                order_created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                order_created = datetime.now(timezone.utc)

        # Get product info from cards
        card_info = nm_card_map.get(nm_id, {})
        product_name = card_info.get("name", article)
        sku = skus[0] if skus else ""

        order = Order(
            wb_order_id=wb_order_id,
            shop_id=shop.id,
            order_type=order_type,
            status="pending",
            total_price=price,
            currency=currency,
            warehouse_name=str(warehouse_id),
            created_at=order_created or datetime.now(timezone.utc),
        )
        db.add(order)
        db.flush()

        # Initial status log
        log = OrderStatusLog(
            order_id=order.id,
            status="pending",
            wb_status="new",
        )
        db.add(log)

        # Each WB order = one item (one SKU per order)
        item = OrderItem(
            order_id=order.id,
            wb_product_id=str(nm_id),
            product_name=product_name,
            sku=sku,
            barcode=sku,
            quantity=1,
            price=price,
        )
        db.add(item)

        # Auto-create SKU mapping if not exists
        if sku:
            existing_mapping = db.query(SkuMapping).filter(
                SkuMapping.shop_id == shop.id, SkuMapping.shop_sku == sku
            ).first()
            if not existing_mapping:
                mapping = SkuMapping(
                    shop_id=shop.id,
                    shop_sku=sku,
                    wb_product_name=product_name,
                    wb_barcode=sku,
                )
                db.add(mapping)

    # Step 5: Batch update statuses for all known orders
    if wb_order_ids:
        _update_order_statuses(db, shop.id, api_token, wb_order_ids)

    shop.last_sync_at = datetime.now(timezone.utc)
    db.commit()


def _update_order_statuses(db: Session, shop_id: int, api_token: str, wb_order_ids: list[int]):
    """Batch query and update order statuses from WB API."""
    statuses = fetch_order_statuses(api_token, wb_order_ids)

    for status_info in statuses:
        wb_id = str(status_info.get("id", ""))
        supplier_status = status_info.get("supplierStatus", "")
        wb_status = status_info.get("wbStatus", "")

        order = db.query(Order).filter(
            Order.shop_id == shop_id, Order.wb_order_id == wb_id
        ).first()
        if not order:
            continue

        new_status = _resolve_status(supplier_status, wb_status)
        if order.status != new_status:
            order.status = new_status
            order.updated_at = datetime.now(timezone.utc)
            log = OrderStatusLog(
                order_id=order.id,
                status=new_status,
                wb_status=f"{supplier_status}/{wb_status}",
            )
            db.add(log)


def sync_shop_inventory(db: Session, shop: Shop):
    """Sync inventory: fetch warehouses, then query stock per warehouse."""
    api_token = decrypt_token(shop.api_token)

    # Step 1: Get all seller warehouses
    warehouses = fetch_warehouses(api_token)
    if not warehouses:
        print(f"[Sync] No warehouses found for shop {shop.name}")
        return

    # Step 2: Collect all known SKUs from SKU mappings
    mappings = db.query(SkuMapping).filter(SkuMapping.shop_id == shop.id).all()
    all_skus = [m.shop_sku for m in mappings if m.shop_sku]

    if not all_skus:
        print(f"[Sync] No SKUs to query for shop {shop.name}")
        return

    # Step 3: Query stock for each warehouse
    sku_stocks: dict[str, dict] = {}
    for wh in warehouses:
        wh_id = wh.get("id")
        wh_name = wh.get("name", "")
        if not wh_id:
            continue

        stocks = fetch_stocks(api_token, wh_id, all_skus)
        for s in stocks:
            sku = s.get("sku", "")
            amount = s.get("amount", 0)
            if not sku:
                continue

            if sku not in sku_stocks:
                # Find product name from mapping
                mapping = next((m for m in mappings if m.shop_sku == sku), None)
                name = mapping.wb_product_name if mapping else ""
                sku_stocks[sku] = {"name": name, "fbs": 0, "fbw": 0}

            # FBS warehouses are seller's own warehouses (from /api/v3/warehouses)
            sku_stocks[sku]["fbs"] += amount

    # Step 4: Also try to get FBW stock from WB warehouses (office stock)
    # FBW stock comes from a different source — the seller can check it
    # via the statistics API or supplies API. For now we track FBS stock
    # from the seller's warehouses.

    # Step 5: Update inventory records
    for sku, data in sku_stocks.items():
        inv = db.query(Inventory).filter(
            Inventory.shop_id == shop.id, Inventory.sku == sku
        ).first()
        if inv:
            inv.stock_fbs = data["fbs"]
            inv.updated_at = datetime.now(timezone.utc)
        else:
            inv = Inventory(
                shop_id=shop.id,
                product_name=data["name"],
                sku=sku,
                barcode=sku,
                stock_fbs=data["fbs"],
                stock_fbw=0,
            )
            db.add(inv)

    db.commit()
