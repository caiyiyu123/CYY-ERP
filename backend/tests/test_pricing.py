"""
pricing 路由测试
覆盖：CRUD 生命周期 / 参数读写 / Product 快照 / 平台级联删除 / 权限校验
"""
from app.models.user import User
from app.models.product import Product
from app.models.pricing import PricingItem, PricingPlatform
from app.utils.security import hash_password


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _setup_admin(db):
    u = User(
        username="pricing_admin",
        password_hash=hash_password("pw"),
        role="admin",
        is_active=True,
        permissions="pricing",
    )
    db.add(u)
    db.commit()
    return u


def _login(client):
    r = client.post("/api/auth/login", data={"username": "pricing_admin", "password": "pw"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _item_payload(**overrides):
    base = {
        "name": "Test Item",
        "sku": "TEST-SKU-001",
        "image_url": "",
        "purchase_cost": 50.0,
        "weight_kg": 1.5,
        "length_cm": 30.0,
        "width_cm": 20.0,
        "height_cm": 10.0,
        "platforms": [
            {
                "platform": "wb_local",
                "price_rub": 999.0,
                "price_rmb": 80.0,
                "discount_pct": 0.0,
                "extra": {},
            }
        ],
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────
# Test 1: 完整 CRUD 生命周期
# ──────────────────────────────────────────────

def test_create_list_get_update_delete(client, db):
    _setup_admin(db)
    h = _login(client)

    # POST → 201
    r = client.post("/api/pricing/items", json=_item_payload(), headers=h)
    assert r.status_code == 201, r.text
    item = r.json()
    item_id = item["id"]
    assert item["sku"] == "TEST-SKU-001"
    assert len(item["platforms"]) == 1
    assert item["platforms"][0]["price_rub"] == 999.0

    # GET list → 200, total >= 1
    r = client.get("/api/pricing/items", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1

    # GET single → 200, sku 匹配
    r = client.get(f"/api/pricing/items/{item_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["sku"] == "TEST-SKU-001"

    # PUT → 200, 字段更新
    updated_payload = _item_payload(
        sku="TEST-SKU-001",
        purchase_cost=88.0,
        platforms=[
            {
                "platform": "wb_local",
                "price_rub": 1200.0,
                "price_rmb": 100.0,
                "discount_pct": 5.0,
                "extra": {},
            }
        ],
    )
    r = client.put(f"/api/pricing/items/{item_id}", json=updated_payload, headers=h)
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["purchase_cost"] == 88.0
    assert updated["platforms"][0]["price_rub"] == 1200.0

    # DELETE → 200
    r = client.delete(f"/api/pricing/items/{item_id}", headers=h)
    assert r.status_code == 200

    # GET after delete → 404
    r = client.get(f"/api/pricing/items/{item_id}", headers=h)
    assert r.status_code == 404


# ──────────────────────────────────────────────
# Test 2: 参数读写
# ──────────────────────────────────────────────

def test_params_read_write(client, db):
    _setup_admin(db)
    h = _login(client)

    # GET 默认值
    r = client.get("/api/pricing/params", headers=h)
    assert r.status_code == 200
    defaults = r.json()
    assert defaults["withdrawal_rate"] == 0.015

    # PUT 修改
    new_params = {
        "rate_rub_cny": 0.09,
        "rate_usd_cny": 7.5,
        "order_fee_threshold_kg": 3.0,
        "order_fee_light": 7.0,
        "order_fee_heavy": 12.0,
        "withdrawal_rate": 0.02,
    }
    r = client.put("/api/pricing/params", json=new_params, headers=h)
    assert r.status_code == 200

    # GET 再次 → 新值
    r = client.get("/api/pricing/params", headers=h)
    assert r.status_code == 200
    got = r.json()
    assert got["withdrawal_rate"] == 0.02
    assert got["rate_rub_cny"] == 0.09
    assert got["order_fee_heavy"] == 12.0


# ──────────────────────────────────────────────
# Test 3: Product 快照行为
# ──────────────────────────────────────────────

def test_product_snapshot_on_create(client, db):
    _setup_admin(db)
    h = _login(client)

    # 创建 Product（只有 sku 是必填的，其他有默认值）
    product = Product(
        sku="SNAP-SKU-999",
        name="Snapshot Product",
        image="http://example.com/img.jpg",
        purchase_price=120.0,
        weight=2.5,
        length=40.0,
        width=30.0,
        height=20.0,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # POST pricing item：故意把 purchase_cost/weight 设为 0
    payload = {
        "name": "Snap Test",
        "sku": "SNAP-TEST",
        "product_id": product.id,
        "image_url": "",
        "purchase_cost": 0.0,
        "weight_kg": 0.0,
        "length_cm": 0.0,
        "width_cm": 0.0,
        "height_cm": 0.0,
        "platforms": [],
    }
    r = client.post("/api/pricing/items", json=payload, headers=h)
    assert r.status_code == 201, r.text
    item = r.json()
    item_id = item["id"]

    # 快照应覆盖 0 值
    assert item["purchase_cost"] == 120.0,  f"期望快照 purchase_cost=120, 实际={item['purchase_cost']}"
    assert item["weight_kg"] == 2.5,        f"期望快照 weight_kg=2.5, 实际={item['weight_kg']}"
    assert item["length_cm"] == 40.0,       f"期望快照 length_cm=40, 实际={item['length_cm']}"
    assert item["width_cm"] == 30.0,        f"期望快照 width_cm=30, 实际={item['width_cm']}"
    assert item["height_cm"] == 20.0,       f"期望快照 height_cm=20, 实际={item['height_cm']}"
    assert item["image_url"] == "http://example.com/img.jpg", f"期望快照 image_url, 实际={item['image_url']}"

    # 修改 Product 的价格
    product.purchase_price = 999.0
    db.commit()

    # GET pricing item → purchase_cost 仍为快照值（不跟随 Product 变化）
    r = client.get(f"/api/pricing/items/{item_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["purchase_cost"] == 120.0, "快照不应跟随 Product 后续变化"


# ──────────────────────────────────────────────
# Test 4: 平台级联删除
# ──────────────────────────────────────────────

def test_cascade_delete_platforms(client, db):
    _setup_admin(db)
    h = _login(client)

    # POST with 1 platform
    r = client.post("/api/pricing/items", json=_item_payload(sku="CASCADE-SKU"), headers=h)
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    # DB 里有 1 条 PricingPlatform
    count_before = db.query(PricingPlatform).filter(PricingPlatform.item_id == item_id).count()
    assert count_before == 1, f"预期 1 条 platform，实际 {count_before}"

    # DELETE item
    r = client.delete(f"/api/pricing/items/{item_id}", headers=h)
    assert r.status_code == 200

    # DB 里 platform 也被级联删除
    count_after = db.query(PricingPlatform).filter(PricingPlatform.item_id == item_id).count()
    assert count_after == 0, f"级联删除后应为 0 条 platform，实际 {count_after}"


# ──────────────────────────────────────────────
# Test 5: 无 token 访问 → 401
# ──────────────────────────────────────────────

def test_permission_required(client, db):
    r = client.get("/api/pricing/items")
    assert r.status_code == 401, f"无 token 应返回 401，实际 {r.status_code}"
