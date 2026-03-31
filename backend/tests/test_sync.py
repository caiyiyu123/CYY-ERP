from unittest.mock import patch
from app.models.shop import Shop
from app.models.order import Order
from app.models.inventory import Inventory
from app.models.product import SkuMapping
from app.utils.security import encrypt_token
from app.services.sync import sync_shop_orders, sync_shop_inventory

# Mock data matching real WB API response format
MOCK_WB_ORDERS = [
    {
        "id": 123456,
        "createdAt": "2026-03-30T12:00:00Z",
        "warehouseId": 5,
        "nmId": 99001,
        "chrtId": 88001,
        "price": 235000,        # kopecks
        "convertedPrice": 235000,
        "currencyCode": 643,    # RUB
        "cargoType": 1,
        "skus": ["WB-SKU-001"],
        "article": "ART-001",
        "isZeroOrder": False,
    }
]

MOCK_WB_NEW_ORDERS = []  # No new orders in this test

MOCK_WB_ORDER_STATUSES = [
    {
        "id": 123456,
        "supplierStatus": "new",
        "wbStatus": "waiting",
    }
]

MOCK_WB_CARDS = [
    {
        "nmID": 99001,
        "title": "Кроссовки мужские",
        "vendorCode": "ART-001",
        "photos": [],
    }
]

MOCK_WB_WAREHOUSES = [
    {"id": 5, "name": "My Warehouse"},
]

MOCK_WB_STOCKS = [
    {"sku": "WB-SKU-001", "amount": 50},
]


def test_sync_shop_orders(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    with (
        patch("app.services.sync.fetch_new_orders", return_value=MOCK_WB_NEW_ORDERS),
        patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS),
        patch("app.services.sync.fetch_order_statuses", return_value=MOCK_WB_ORDER_STATUSES),
        patch("app.services.sync.fetch_cards", return_value=MOCK_WB_CARDS),
    ):
        sync_shop_orders(db, shop)
    orders = db.query(Order).all()
    assert len(orders) == 1
    assert orders[0].wb_order_id == "123456"
    assert orders[0].order_type == "FBS"
    assert orders[0].total_price == 2350.0  # 235000 kopecks → 2350 rubles
    assert orders[0].currency == "RUB"
    # Verify idempotent — running again should not create duplicates
    with (
        patch("app.services.sync.fetch_new_orders", return_value=MOCK_WB_NEW_ORDERS),
        patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS),
        patch("app.services.sync.fetch_order_statuses", return_value=MOCK_WB_ORDER_STATUSES),
        patch("app.services.sync.fetch_cards", return_value=MOCK_WB_CARDS),
    ):
        sync_shop_orders(db, shop)
    assert db.query(Order).count() == 1


def test_sync_shop_inventory(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    # Need at least one SKU mapping for inventory sync to query
    mapping = SkuMapping(shop_id=shop.id, shop_sku="WB-SKU-001", wb_product_name="Кроссовки")
    db.add(mapping)
    db.commit()
    with (
        patch("app.services.sync.fetch_warehouses", return_value=MOCK_WB_WAREHOUSES),
        patch("app.services.sync.fetch_stocks", return_value=MOCK_WB_STOCKS),
    ):
        sync_shop_inventory(db, shop)
    inv = db.query(Inventory).filter(Inventory.sku == "WB-SKU-001").first()
    assert inv is not None
    assert inv.stock_fbs == 50


def test_sync_creates_sku_mappings(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    with (
        patch("app.services.sync.fetch_new_orders", return_value=MOCK_WB_NEW_ORDERS),
        patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS),
        patch("app.services.sync.fetch_order_statuses", return_value=MOCK_WB_ORDER_STATUSES),
        patch("app.services.sync.fetch_cards", return_value=MOCK_WB_CARDS),
    ):
        sync_shop_orders(db, shop)
    mapping = db.query(SkuMapping).filter(SkuMapping.shop_sku == "WB-SKU-001").first()
    assert mapping is not None
    assert mapping.shop_id == shop.id
    assert mapping.wb_product_name == "Кроссовки мужские"


def test_sync_status_update(db):
    """Test that order statuses are updated from WB API."""
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    # First sync — create order
    with (
        patch("app.services.sync.fetch_new_orders", return_value=MOCK_WB_NEW_ORDERS),
        patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS),
        patch("app.services.sync.fetch_order_statuses", return_value=MOCK_WB_ORDER_STATUSES),
        patch("app.services.sync.fetch_cards", return_value=MOCK_WB_CARDS),
    ):
        sync_shop_orders(db, shop)

    order = db.query(Order).filter(Order.wb_order_id == "123456").first()
    assert order.status == "pending"  # waiting → pending

    # Second sync — status changed to sold/complete
    updated_statuses = [{"id": 123456, "supplierStatus": "complete", "wbStatus": "sold"}]
    with (
        patch("app.services.sync.fetch_new_orders", return_value=[]),
        patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS),
        patch("app.services.sync.fetch_order_statuses", return_value=updated_statuses),
        patch("app.services.sync.fetch_cards", return_value=MOCK_WB_CARDS),
    ):
        sync_shop_orders(db, shop)

    db.refresh(order)
    assert order.status == "completed"  # sold → completed
