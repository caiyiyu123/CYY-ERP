from unittest.mock import patch
from app.models.shop import Shop
from app.models.order import Order
from app.models.inventory import Inventory
from app.models.product import SkuMapping
from app.utils.security import encrypt_token
from app.services.sync import sync_shop_orders, sync_shop_inventory

MOCK_WB_ORDERS = [
    {
        "id": 123456, "orderType": "fbs", "status": 0, "totalPrice": 2350,
        "currency": "RUB", "address": "Moscow", "warehouseName": "Коледино",
        "products": [
            {"name": "Кроссовки", "sku": "WB-SKU-001", "barcode": "123456",
             "quantity": 1, "price": 2350, "commission": 235, "logisticsCost": 150}
        ],
    }
]

MOCK_WB_STOCKS = [
    {"sku": "WB-SKU-001", "name": "Кроссовки", "barcode": "123456", "stock": 50, "warehouseId": 1, "warehouseName": "FBS"},
    {"sku": "WB-SKU-001", "name": "Кроссовки", "barcode": "123456", "stock": 30, "warehouseId": 2, "warehouseName": "FBW"},
]


def test_sync_shop_orders(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    with patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS):
        sync_shop_orders(db, shop)
    orders = db.query(Order).all()
    assert len(orders) == 1
    assert orders[0].wb_order_id == "123456"
    assert orders[0].order_type == "FBS"
    with patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS):
        sync_shop_orders(db, shop)
    assert db.query(Order).count() == 1


def test_sync_shop_inventory(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    with patch("app.services.sync.fetch_stocks", return_value=MOCK_WB_STOCKS):
        sync_shop_inventory(db, shop)
    inv = db.query(Inventory).filter(Inventory.sku == "WB-SKU-001").first()
    assert inv is not None
    assert inv.stock_fbs == 50
    assert inv.stock_fbw == 30


def test_sync_creates_sku_mappings(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()
    with patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS):
        sync_shop_orders(db, shop)
    mapping = db.query(SkuMapping).filter(SkuMapping.shop_sku == "WB-SKU-001").first()
    assert mapping is not None
    assert mapping.shop_id == shop.id
