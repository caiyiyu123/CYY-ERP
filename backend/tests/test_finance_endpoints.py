from datetime import date, datetime, timezone
from app.models.user import User
from app.models.shop import Shop
from app.models.order import Order
from app.models.finance import FinanceOrderRecord, FinanceOtherFee
from app.utils.security import hash_password, encrypt_token


def _setup_admin(db):
    u = User(username="a", password_hash=hash_password("pw"), role="admin",
             is_active=True, permissions="finance")
    db.add(u); db.commit()
    return u


def _login(client):
    r = client.post("/api/auth/login", data={"username": "a", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_shop(db, type_="local"):
    s = Shop(name=f"Shop-{type_}", type=type_, api_token=encrypt_token("t"), is_active=True)
    db.add(s); db.commit()
    return s


def _make_record(db, shop, srid, **over):
    defaults = dict(
        shop_id=shop.id, srid=srid, currency="RUB",
        sale_date=date(2026, 4, 13), order_date=date(2026, 4, 8),
        report_period_start=date(2026, 4, 6), report_period_end=date(2026, 4, 12),
        nm_id="1", shop_sku="SKU-1", product_name="P", quantity=1,
        net_to_seller=100.0, delivery_fee=10.0, commission_amount=5.0, commission_rate=9.5,
        purchase_cost=20.0, net_profit=70.0, has_sku_mapping=True,
    )
    defaults.update(over)
    rec = FinanceOrderRecord(**defaults)
    db.add(rec); db.commit()
    return rec


def test_summary_returns_aggregates(client, db):
    _setup_admin(db)
    shop = _make_shop(db, "local")
    _make_record(db, shop, "A", net_to_seller=100, purchase_cost=20, net_profit=70)
    _make_record(db, shop, "B", net_to_seller=200, purchase_cost=40, net_profit=140)
    db.add(FinanceOtherFee(shop_id=shop.id, currency="RUB", sale_date=date(2026, 4, 10),
                           fee_type="fine", amount=50, raw_row={})); db.commit()

    headers = _login(client)
    r = client.get("/api/finance/summary", params={
        "shop_type": "local", "date_from": "2026-04-01", "date_to": "2026-04-30",
    }, headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert d["order_count"] == 2
    assert d["total_net_to_seller"] == 300
    assert d["total_purchase_cost"] == 60
    assert d["total_net_profit"] == 210
    assert d["total_other_fees"] == 50
    assert d["final_profit"] == 160
    assert d["currency"] == "RUB"


def test_summary_currency_from_shop_type(client, db):
    _setup_admin(db)
    shop_cb = _make_shop(db, "cross_border")
    _make_record(db, shop_cb, "C1", currency="CNY", net_to_seller=50, net_profit=30)
    headers = _login(client)
    r = client.get("/api/finance/summary", params={
        "shop_type": "cross_border", "date_from": "2026-04-01", "date_to": "2026-04-30",
    }, headers=headers)
    assert r.json()["currency"] == "CNY"
    assert r.json()["order_count"] == 1


def test_orders_list_pagination_and_filter(client, db):
    _setup_admin(db)
    shop = _make_shop(db, "local")
    for i in range(25):
        _make_record(db, shop, f"S{i}", has_sku_mapping=(i % 2 == 0))
    headers = _login(client)
    r = client.get("/api/finance/orders", params={
        "shop_type": "local", "date_from": "2026-04-01", "date_to": "2026-04-30",
        "page": 2, "page_size": 10,
    }, headers=headers)
    d = r.json()
    assert d["total"] == 25
    assert len(d["items"]) == 10
    # filter unmapped
    r = client.get("/api/finance/orders", params={
        "shop_type": "local", "date_from": "2026-04-01", "date_to": "2026-04-30",
        "has_mapping": "false",
    }, headers=headers)
    assert all(not it["has_sku_mapping"] for it in r.json()["items"])


def test_other_fees_list(client, db):
    _setup_admin(db)
    shop = _make_shop(db, "local")
    db.add_all([
        FinanceOtherFee(shop_id=shop.id, currency="RUB", sale_date=date(2026, 4, 10),
                        fee_type="storage", amount=100, raw_row={}),
        FinanceOtherFee(shop_id=shop.id, currency="RUB", sale_date=date(2026, 4, 11),
                        fee_type="fine", amount=50, raw_row={}),
    ]); db.commit()
    headers = _login(client)
    r = client.get("/api/finance/other-fees", params={
        "shop_type": "local", "date_from": "2026-04-01", "date_to": "2026-04-30",
    }, headers=headers)
    assert r.json()["total"] == 2


def test_reconciliation_missing_in_orders(client, db):
    """财报有 Srid，但 orders 表里找不到对应 srid。"""
    _setup_admin(db)
    shop = _make_shop(db, "local")
    _make_record(db, shop, "ORPHAN", net_to_seller=150)
    headers = _login(client)
    r = client.get("/api/finance/reconciliation", params={
        "shop_type": "local", "date_from": "2026-04-01", "date_to": "2026-04-30",
    }, headers=headers)
    d = r.json()
    assert len(d["missing_in_orders"]) == 1
    assert d["missing_in_orders"][0]["srid"] == "ORPHAN"


def test_reconciliation_missing_in_finance(client, db):
    """Order 存在，srid 非空，但财报里没这个 srid。"""
    _setup_admin(db)
    shop = _make_shop(db, "local")
    order = Order(wb_order_id="O1", srid="MISSING", shop_id=shop.id,
                  order_type="FBS", status="delivered", total_price=100,
                  created_at=datetime(2026, 4, 15, tzinfo=timezone.utc))
    db.add(order); db.commit()
    headers = _login(client)
    r = client.get("/api/finance/reconciliation", params={
        "shop_type": "local", "date_from": "2026-04-01", "date_to": "2026-04-30",
    }, headers=headers)
    d = r.json()
    assert any(x["srid"] == "MISSING" for x in d["missing_in_finance"])
