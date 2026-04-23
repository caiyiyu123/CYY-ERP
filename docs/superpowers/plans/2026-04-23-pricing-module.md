# 定价表模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CYY-ERP 新增"定价表"模块，本期只实现 WB 跨境 FBS 一行，支持按 SKU 软关联商品、实时计算利润和利润率，参数可配。

**Architecture:** 后端 2 张新表（`pricing_items` + `pricing_platforms`）+ CRUD API + 参数读写（复用 `system_settings`）。前端 1 主页 + 2 个 tab + 卡片列表 + 纯前端计算 composable。前端**不写自动化测试**（项目未装测试框架，通过手工验收清单验证）。

**Tech Stack:** FastAPI / SQLAlchemy 2.x / Pydantic v2 / Vue 3 `<script setup>` / Element Plus / Axios。复用现有 `system_settings` 表、`shipping_templates` 默认模板 API、`commission_rates` 接口、`/api/products` 接口。

---

## 设计对齐

本 plan 基于 [2026-04-23-pricing-module-design.md](../specs/2026-04-23-pricing-module-design.md) 的所有决策：
- 软关联 Product（创建时快照；编辑时若 `product_id` 变则重新快照）
- 不存中间计算字段（体积/利润等前端实时算）
- `platform="wb_cross_fbs"` 一条；其余 4 行本期不做
- 双向换算：在 `@input` 事件里直接同步另一个字段（不用 watch，避免死循环）

---

## 文件结构

### 后端新建
| 文件 | 职责 |
|---|---|
| `backend/app/models/pricing.py` | `PricingItem` + `PricingPlatform` 两张表定义 |
| `backend/app/routers/pricing.py` | CRUD + 参数读写 API（Pydantic schema 在同文件内定义）|
| `backend/tests/test_pricing.py` | pytest：CRUD、参数、软关联、FK 级联、权限 |

### 后端修改
| 文件 | 改动 |
|---|---|
| `backend/app/models/__init__.py` | 新增 `from app.models.pricing import PricingItem, PricingPlatform` |
| `backend/app/models/user.py:33` | `ALL_MODULES` 末尾加 `"pricing"` |
| `backend/app/main.py` | 注册 `pricing` router |

### 前端新建
| 文件 | 职责 |
|---|---|
| `frontend/src/views/Pricing.vue` | 主页，含 2 个 tab 容器 |
| `frontend/src/components/pricing/PricingListTab.vue` | "定价表" tab：搜索栏 + 新增按钮 + 卡片列表 |
| `frontend/src/components/pricing/PricingCard.vue` | 单个定价卡片（左商品信息 + 右 WB 跨境 FBS 定价行）|
| `frontend/src/components/pricing/ParamsTab.vue` | "参数" tab：5 个参数表单 + 保存按钮 |
| `frontend/src/composables/usePricingCalc.js` | 纯函数 composable，输入原始字段输出派生字段 |

### 前端修改
| 文件 | 改动 |
|---|---|
| `frontend/src/router/index.js` | 新增 `/pricing` 路由（module=`pricing`）|
| `frontend/src/views/Layout.vue` | 新增"定价表"菜单项 |

---

## 预检（开始前）

- [ ] **确认本地后端在跑**：`curl -s http://localhost:8000/api/health` 应返回 `{"status":"ok"}`
- [ ] **确认在 `feature/finance-module` 分支**：`git branch --show-current` 输出 `feature/finance-module`
- [ ] **确认工作区干净**：`git status --short` 应无 M 标记（未提交改动）；`??` 标记的 `uploads/` 可忽略
- [ ] **本地数据库是 SQLite**：`backend/wb_erp.db` 存在

---

## Task 1：后端模型 `pricing_items` + `pricing_platforms`

**Files:**
- Create: `backend/app/models/pricing.py`
- Modify: `backend/app/models/__init__.py`（末尾加 import）

- [ ] **Step 1.1：创建 `backend/app/models/pricing.py`**

```python
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PricingItem(Base):
    __tablename__ = "pricing_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    sku: Mapped[str] = mapped_column(String(200), default="", index=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    image_url: Mapped[str] = mapped_column(String(500), default="")
    purchase_cost: Mapped[float] = mapped_column(Float, default=0.0)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    length_cm: Mapped[float] = mapped_column(Float, default=0.0)
    width_cm: Mapped[float] = mapped_column(Float, default=0.0)
    height_cm: Mapped[float] = mapped_column(Float, default=0.0)
    wb_local_rate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commission_rates.id", ondelete="SET NULL"), nullable=True
    )
    wb_cross_rate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commission_rates.id", ondelete="SET NULL"), nullable=True
    )
    ozon_local_rate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commission_rates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    platforms: Mapped[list["PricingPlatform"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class PricingPlatform(Base):
    __tablename__ = "pricing_platforms"
    __table_args__ = (
        UniqueConstraint("item_id", "platform", name="uq_pricing_item_platform"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pricing_items.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(30))
    price_rub: Mapped[float] = mapped_column(Float, default=0.0)
    price_rmb: Mapped[float] = mapped_column(Float, default=0.0)
    discount_pct: Mapped[float] = mapped_column(Float, default=0.0)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    item: Mapped["PricingItem"] = relationship(back_populates="platforms")
```

- [ ] **Step 1.2：修改 `backend/app/models/__init__.py`**

Read 当前文件；在末尾（已有其他 model import 之后）追加：

```python
from app.models.pricing import PricingItem, PricingPlatform  # noqa: F401
```

- [ ] **Step 1.3：重启后端触发 create_all**

因为 uvicorn `--reload` 监听 .py 文件变化，保存 `pricing.py` 后会自动重启。验证新表已建：

```bash
cd backend && python -c "
import sqlite3
conn = sqlite3.connect('wb_erp.db')
cur = conn.cursor()
for t in ['pricing_items', 'pricing_platforms']:
    row = cur.execute(f\"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'\").fetchone()
    print(f'{t}: {\"OK\" if row else \"MISSING\"}')
"
```

Expected: `pricing_items: OK` + `pricing_platforms: OK`。

- [ ] **Step 1.4：Commit**

```bash
git add backend/app/models/pricing.py backend/app/models/__init__.py
git commit -m "feat(pricing): 新增 pricing_items + pricing_platforms 模型"
```

---

## Task 2：ALL_MODULES 加入 `pricing`

**Files:**
- Modify: `backend/app/models/user.py:33`

- [ ] **Step 2.1：修改 `ALL_MODULES`**

Read 第 33 行；把：

```python
ALL_MODULES = ["dashboard", "orders", "products", "purchase_plan", "ads", "finance", "customer_service", "commission_shipping", "inventory", "shops"]
```

改为：

```python
ALL_MODULES = ["dashboard", "orders", "products", "purchase_plan", "ads", "finance", "customer_service", "commission_shipping", "inventory", "shops", "pricing"]
```

- [ ] **Step 2.2：Commit**

```bash
git add backend/app/models/user.py
git commit -m "feat(pricing): ALL_MODULES 加入 pricing 权限模块"
```

---

## Task 3：后端 Router 骨架 + CRUD items

**Files:**
- Create: `backend/app/routers/pricing.py`
- Modify: `backend/app/main.py`（注册 router）

- [ ] **Step 3.1：创建 router 文件**

完整写 `backend/app/routers/pricing.py`：

```python
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pricing import PricingItem, PricingPlatform
from app.models.product import Product
from app.models.setting import SystemSetting
from app.utils.deps import require_module

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


# ========== Pydantic Schemas ==========

class PlatformIn(BaseModel):
    platform: str                           # "wb_cross_fbs" 等
    price_rub: float = 0.0
    price_rmb: float = 0.0
    discount_pct: float = 0.0
    extra: dict = {}


class ItemCreate(BaseModel):
    name: str = ""
    sku: str = ""
    product_id: Optional[int] = None
    image_url: str = ""
    purchase_cost: float = 0.0
    weight_kg: float = 0.0
    length_cm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    wb_local_rate_id: Optional[int] = None
    wb_cross_rate_id: Optional[int] = None
    ozon_local_rate_id: Optional[int] = None
    platforms: list[PlatformIn] = []


class ItemUpdate(ItemCreate):
    pass


# ========== Helpers ==========

def _item_to_dict(it: PricingItem) -> dict:
    return {
        "id": it.id,
        "name": it.name,
        "sku": it.sku,
        "product_id": it.product_id,
        "image_url": it.image_url,
        "purchase_cost": it.purchase_cost,
        "weight_kg": it.weight_kg,
        "length_cm": it.length_cm,
        "width_cm": it.width_cm,
        "height_cm": it.height_cm,
        "wb_local_rate_id": it.wb_local_rate_id,
        "wb_cross_rate_id": it.wb_cross_rate_id,
        "ozon_local_rate_id": it.ozon_local_rate_id,
        "created_at": it.created_at.isoformat(),
        "updated_at": it.updated_at.isoformat(),
        "platforms": [
            {
                "id": p.id,
                "platform": p.platform,
                "price_rub": p.price_rub,
                "price_rmb": p.price_rmb,
                "discount_pct": p.discount_pct,
                "extra": p.extra or {},
            }
            for p in it.platforms
        ],
    }


def _snapshot_from_product(db: Session, product_id: int) -> dict:
    """从 Product 表复制字段到 PricingItem 的快照"""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return {
        "image_url": p.image or "",
        "purchase_cost": p.purchase_price or 0.0,
        "weight_kg": p.weight or 0.0,
        "length_cm": p.length or 0.0,
        "width_cm": p.width or 0.0,
        "height_cm": p.height or 0.0,
    }


def _apply_platforms(db: Session, item: PricingItem, platforms_in: list[PlatformIn]) -> None:
    """全量替换 platforms (简单处理：删除再插入)"""
    for p in list(item.platforms):
        db.delete(p)
    db.flush()
    for p in platforms_in:
        db.add(PricingPlatform(
            item_id=item.id,
            platform=p.platform,
            price_rub=p.price_rub,
            price_rmb=p.price_rmb,
            discount_pct=p.discount_pct,
            extra=p.extra or {},
        ))


# ========== CRUD Items ==========

@router.get("/items")
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="模糊匹配 sku 或 name"),
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    q = db.query(PricingItem)
    if search:
        kw = f"%{search}%"
        q = q.filter((PricingItem.sku.ilike(kw)) | (PricingItem.name.ilike(kw)))
    total = q.count()
    items = q.order_by(PricingItem.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_item_to_dict(it) for it in items], "total": total}


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(
    data: ItemCreate,
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    payload = data.model_dump(exclude={"platforms"})
    # 如果传了 product_id，快照覆盖字段
    if data.product_id:
        payload.update(_snapshot_from_product(db, data.product_id))
    it = PricingItem(**payload)
    db.add(it)
    db.flush()
    _apply_platforms(db, it, data.platforms)
    db.commit()
    db.refresh(it)
    return _item_to_dict(it)


@router.get("/items/{item_id}")
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    it = db.query(PricingItem).filter(PricingItem.id == item_id).first()
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    return _item_to_dict(it)


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    it = db.query(PricingItem).filter(PricingItem.id == item_id).first()
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    payload = data.model_dump(exclude={"platforms"})
    # 若 product_id 从无→有 或 变更：重新快照
    if data.product_id and data.product_id != it.product_id:
        payload.update(_snapshot_from_product(db, data.product_id))
    for k, v in payload.items():
        setattr(it, k, v)
    _apply_platforms(db, it, data.platforms)
    db.commit()
    db.refresh(it)
    return _item_to_dict(it)


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    it = db.query(PricingItem).filter(PricingItem.id == item_id).first()
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(it)
    db.commit()
    return {"detail": "Item deleted"}


# ========== Params ==========

_PARAM_KEYS = [
    "pricing.rate_rub_cny",
    "pricing.rate_usd_cny",
    "pricing.order_fee_threshold_kg",
    "pricing.order_fee_light",
    "pricing.order_fee_heavy",
    "pricing.withdrawal_rate",
]
_PARAM_DEFAULTS = {
    "pricing.rate_rub_cny": 0.08,
    "pricing.rate_usd_cny": 7.2,
    "pricing.order_fee_threshold_kg": 2.0,
    "pricing.order_fee_light": 6.0,
    "pricing.order_fee_heavy": 10.0,
    "pricing.withdrawal_rate": 0.015,
}


class ParamsIn(BaseModel):
    rate_rub_cny: float = Field(0.08, gt=0)
    rate_usd_cny: float = Field(7.2, gt=0)
    order_fee_threshold_kg: float = Field(2.0, ge=0)
    order_fee_light: float = Field(6.0, ge=0)
    order_fee_heavy: float = Field(10.0, ge=0)
    withdrawal_rate: float = Field(0.015, ge=0, le=1)


@router.get("/params")
def get_params(
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    rows = {s.key: s.value for s in db.query(SystemSetting).filter(SystemSetting.key.in_(_PARAM_KEYS)).all()}
    return {
        "rate_rub_cny": float(rows.get("pricing.rate_rub_cny", _PARAM_DEFAULTS["pricing.rate_rub_cny"])),
        "rate_usd_cny": float(rows.get("pricing.rate_usd_cny", _PARAM_DEFAULTS["pricing.rate_usd_cny"])),
        "order_fee_threshold_kg": float(rows.get("pricing.order_fee_threshold_kg", _PARAM_DEFAULTS["pricing.order_fee_threshold_kg"])),
        "order_fee_light": float(rows.get("pricing.order_fee_light", _PARAM_DEFAULTS["pricing.order_fee_light"])),
        "order_fee_heavy": float(rows.get("pricing.order_fee_heavy", _PARAM_DEFAULTS["pricing.order_fee_heavy"])),
        "withdrawal_rate": float(rows.get("pricing.withdrawal_rate", _PARAM_DEFAULTS["pricing.withdrawal_rate"])),
    }


@router.put("/params")
def update_params(
    data: ParamsIn,
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    mapping = {
        "pricing.rate_rub_cny": data.rate_rub_cny,
        "pricing.rate_usd_cny": data.rate_usd_cny,
        "pricing.order_fee_threshold_kg": data.order_fee_threshold_kg,
        "pricing.order_fee_light": data.order_fee_light,
        "pricing.order_fee_heavy": data.order_fee_heavy,
        "pricing.withdrawal_rate": data.withdrawal_rate,
    }
    for k, v in mapping.items():
        row = db.query(SystemSetting).filter(SystemSetting.key == k).first()
        if row:
            row.value = str(v)
        else:
            db.add(SystemSetting(key=k, value=str(v)))
    db.commit()
    return {"detail": "Params updated"}


# ========== Single Rate Lookup ==========

@router.get("/rate/{rate_id}")
def get_single_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_module("pricing")),
):
    """按 id 取单条佣金率,供定价卡片显示佣金率和计算佣金使用"""
    from app.models.commission import CommissionRate
    r = db.query(CommissionRate).filter(CommissionRate.id == rate_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rate not found")
    return {
        "id": r.id,
        "rate": r.rate,
        "product_name": r.product_name,
        "category": r.category,
    }
```

- [ ] **Step 3.2：验证 Product 模型字段名**

代码里用了 `p.image / p.purchase_price / p.weight / p.length / p.width / p.height`。确认这些字段存在：

```bash
grep -n "Mapped\[" backend/app/models/product.py | head -20
```

Expected 输出应包含这 6 个字段。如果 `purchase_price` 不叫这个名字（可能叫 `price` 或 `cost_price`），修正 `_snapshot_from_product` 函数。

- [ ] **Step 3.3：Commit**

```bash
git add backend/app/routers/pricing.py
git commit -m "feat(pricing): 新增 pricing router (CRUD items + params)"
```

---

## Task 4：注册 pricing router 到 main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 4.1：查看 main.py 中 router 注册位置**

```bash
grep -n "include_router\|from app.routers" backend/app/main.py | head -20
```

找到已有的 `from app.routers import ...` 或 `app.include_router(...)` 语句。

- [ ] **Step 4.2：加入 pricing router**

在 imports 区加：
```python
from app.routers import pricing
```

在 `app.include_router(...)` 列表中（和其他 router 同级）加：
```python
app.include_router(pricing.router)
```

- [ ] **Step 4.3：验证**

后端 uvicorn `--reload` 会自动重载。验证端点已注册：

```bash
curl -s http://localhost:8000/api/pricing/params -H "Authorization: Bearer x" -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=401`（token 非法，但路由已注册），而不是 `404`。

- [ ] **Step 4.4：Commit**

```bash
git add backend/app/main.py
git commit -m "feat(pricing): 注册 pricing router 到主 app"
```

---

## Task 5：后端 pytest 测试

**Files:**
- Create: `backend/tests/test_pricing.py`

- [ ] **Step 5.1：写测试文件**

Create `backend/tests/test_pricing.py`：

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.product import Product
from app.models.commission import CommissionTable, CommissionRate
from app.models.pricing import PricingItem


@pytest.fixture
def admin_token(client, db):
    """复用项目现有的 conftest 提供的 admin token fixture（如无则需补）"""
    # 项目惯例:使用 TestClient login 拿 token
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def test_create_list_get_update_delete(client, db, auth_headers):
    # 新建
    resp = client.post("/api/pricing/items", headers=auth_headers, json={
        "name": "test",
        "sku": "SKU001",
        "purchase_cost": 10.0,
        "weight_kg": 1.5,
        "length_cm": 20, "width_cm": 15, "height_cm": 10,
        "platforms": [{"platform": "wb_cross_fbs", "price_rub": 100, "price_rmb": 8, "discount_pct": 10}],
    })
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    assert len(resp.json()["platforms"]) == 1

    # 列表
    resp = client.get("/api/pricing/items", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 详情
    resp = client.get(f"/api/pricing/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["sku"] == "SKU001"

    # 编辑
    resp = client.put(f"/api/pricing/items/{item_id}", headers=auth_headers, json={
        "name": "test-updated",
        "sku": "SKU001",
        "purchase_cost": 12.0,
        "weight_kg": 1.5,
        "length_cm": 20, "width_cm": 15, "height_cm": 10,
        "platforms": [{"platform": "wb_cross_fbs", "price_rub": 120, "price_rmb": 10, "discount_pct": 10}],
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "test-updated"
    assert resp.json()["platforms"][0]["price_rub"] == 120

    # 删除
    resp = client.delete(f"/api/pricing/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    resp = client.get(f"/api/pricing/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_params_read_write(client, db, auth_headers):
    # 默认值
    resp = client.get("/api/pricing/params", headers=auth_headers)
    assert resp.status_code == 200
    p = resp.json()
    assert p["withdrawal_rate"] == 0.015

    # 写入
    resp = client.put("/api/pricing/params", headers=auth_headers, json={
        "rate_rub_cny": 0.09,
        "rate_usd_cny": 7.3,
        "order_fee_threshold_kg": 2.0,
        "order_fee_light": 6.0,
        "order_fee_heavy": 10.0,
        "withdrawal_rate": 0.02,
    })
    assert resp.status_code == 200

    # 再读
    resp = client.get("/api/pricing/params", headers=auth_headers)
    assert resp.json()["rate_rub_cny"] == 0.09
    assert resp.json()["withdrawal_rate"] == 0.02


def test_product_snapshot_on_create(client, db, auth_headers):
    # 建一个 product
    p = Product(developer="T", sku="P001", name="Test", image="http://x/img.png",
                purchase_price=99.0, weight=2.5, length=30, width=20, height=15)
    db.add(p)
    db.commit()

    # 创建定价条目带 product_id
    resp = client.post("/api/pricing/items", headers=auth_headers, json={
        "name": "s",
        "sku": "P001",
        "product_id": p.id,
        # 这些应该被覆盖
        "purchase_cost": 0, "weight_kg": 0, "length_cm": 0, "width_cm": 0, "height_cm": 0,
        "image_url": "",
        "platforms": [],
    })
    assert resp.status_code == 201
    r = resp.json()
    assert r["purchase_cost"] == 99.0
    assert r["weight_kg"] == 2.5
    assert r["length_cm"] == 30
    assert r["image_url"] == "http://x/img.png"

    # 改 Product 的 purchase_price,老条目不受影响
    p.purchase_price = 200
    db.commit()
    resp = client.get(f"/api/pricing/items/{r['id']}", headers=auth_headers)
    assert resp.json()["purchase_cost"] == 99.0  # 仍是快照


def test_cascade_delete_platforms(client, db, auth_headers):
    resp = client.post("/api/pricing/items", headers=auth_headers, json={
        "name": "cascade-test",
        "platforms": [{"platform": "wb_cross_fbs", "price_rub": 1, "price_rmb": 1, "discount_pct": 0}],
    })
    item_id = resp.json()["id"]
    # platforms 存在
    from app.models.pricing import PricingPlatform
    assert db.query(PricingPlatform).filter_by(item_id=item_id).count() == 1
    # 删
    client.delete(f"/api/pricing/items/{item_id}", headers=auth_headers)
    db.expire_all()
    assert db.query(PricingPlatform).filter_by(item_id=item_id).count() == 0


def test_permission_required(client):
    # 无 token
    resp = client.get("/api/pricing/items")
    assert resp.status_code == 401
```

- [ ] **Step 5.2：查看项目现有 conftest，确认 `client` / `db` / 登录方式**

```bash
cat backend/tests/conftest.py
```

如果 conftest 没有 `client` / `db` fixture，按其他测试文件（如 `test_finance_endpoints.py`）的模式补齐或调整测试代码。若 `admin` 默认密码不是 `admin123`，按实际调整。

- [ ] **Step 5.3：运行测试**

```bash
cd backend && set TEST_MODE=1 && pytest tests/test_pricing.py -v
```

Expected: 5 个 test 全绿。

- [ ] **Step 5.4：Commit**

```bash
git add backend/tests/test_pricing.py
git commit -m "test(pricing): CRUD + params + 软关联快照 + FK 级联 + 权限"
```

---

## Task 6：前端路由 + 菜单入口

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Layout.vue`

- [ ] **Step 6.1：加路由**

Read `frontend/src/router/index.js`，找到 `children` 数组（`/purchase-plan` 那一行附近）。在 `purchase-plan` 条目之后插入：

```js
{ path: 'pricing', name: 'Pricing', meta: { module: 'pricing', title: '定价表' }, component: () => import('../views/Pricing.vue') },
```

- [ ] **Step 6.2：加菜单项**

Read `frontend/src/views/Layout.vue`，找到 `v-if="hasPerm('purchase_plan')"` 那个 `el-menu-item`。在它之后插入：

```vue
<el-menu-item v-if="hasPerm('pricing')" index="/pricing">
  <router-link to="/pricing" class="ts-nav-link">
    <el-icon><Money /></el-icon>
    <span>定价表</span>
  </router-link>
</el-menu-item>
```

如果 Layout.vue 顶部 `import { ... } from '@element-plus/icons-vue'` 里没有 `Money`，在 import 列表加上 `Money`。

- [ ] **Step 6.3：手工验证**

浏览器打开 http://localhost:5173。
- 以 admin 登录 → 左侧菜单看到"定价表"项
- 点进去 → 当前是 404 或占位（Pricing.vue 还没建）

这一步**允许页面空白或报错**，下一个 task 补齐。

- [ ] **Step 6.4：Commit**

```bash
git add frontend/src/router/index.js frontend/src/views/Layout.vue
git commit -m "feat(pricing): 前端路由 + 菜单入口"
```

---

## Task 7：Pricing.vue 主页 + tab 骨架

**Files:**
- Create: `frontend/src/views/Pricing.vue`
- Create: `frontend/src/components/pricing/PricingListTab.vue`（占位）
- Create: `frontend/src/components/pricing/ParamsTab.vue`（占位）

- [ ] **Step 7.1：创建 Pricing.vue**

```vue
<template>
  <el-card>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="定价表" name="list">
        <PricingListTab />
      </el-tab-pane>
      <el-tab-pane label="参数" name="params">
        <ParamsTab />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import PricingListTab from '@/components/pricing/PricingListTab.vue'
import ParamsTab from '@/components/pricing/ParamsTab.vue'

const activeTab = ref('list')
</script>
```

- [ ] **Step 7.2：创建占位 PricingListTab.vue**

```vue
<template>
  <div>定价表 — 待实现</div>
</template>

<script setup></script>
```

- [ ] **Step 7.3：创建占位 ParamsTab.vue**

```vue
<template>
  <div>参数 — 待实现</div>
</template>

<script setup></script>
```

- [ ] **Step 7.4：手工验证**

浏览器刷新 http://localhost:5173/pricing。
Expected：
- 页面不报错
- 看到两个 tab："定价表"（默认） / "参数"
- 点击切换能看到"待实现"占位文本

- [ ] **Step 7.5：Commit**

```bash
git add frontend/src/views/Pricing.vue frontend/src/components/pricing/
git commit -m "feat(pricing): 主页 + tab 骨架 (子组件占位)"
```

---

## Task 8：usePricingCalc composable

**Files:**
- Create: `frontend/src/composables/usePricingCalc.js`

- [ ] **Step 8.1：创建 composable**

```js
import { computed } from 'vue'

/**
 * 定价表计算 composable (纯函数 computed)
 *
 * @param {Ref} itemRef - reactive ref of { weight_kg, length_cm, width_cm, height_cm, purchase_cost }
 * @param {Ref} platformRef - reactive ref of { price_rub, price_rmb, discount_pct } (wb_cross_fbs 行)
 * @param {Ref} paramsRef - reactive ref of { rate_rub_cny, rate_usd_cny, order_fee_threshold_kg, order_fee_light, order_fee_heavy, withdrawal_rate }
 * @param {Ref} wbCrossRateRef - reactive ref of { id, rate, product_name, category } | null (当前 item 选的 WB 跨境佣金率对象)
 * @param {Ref} shippingRatesRef - reactive ref of Array<{density_min, density_max, price_usd}> (默认模板的 rates)
 *
 * 返回 computed<{
 *   volume, density, frontPriceRub, headPriceUsd, headFee, orderFee, tailFee,
 *   commissionRatePct, commission, withdrawalFee, profit, profitRatePct
 * }>
 *
 * null = 不可计算 (显示为 '-')
 */
export function usePricingCalc(itemRef, platformRef, paramsRef, wbCrossRateRef, shippingRatesRef) {
  return computed(() => {
    const item = itemRef.value || {}
    const pl = platformRef.value || {}
    const P = paramsRef.value || {}
    const rateEntry = wbCrossRateRef.value || null
    const sr = shippingRatesRef.value || []

    const weight = Number(item.weight_kg) || 0
    const L = Number(item.length_cm) || 0
    const W = Number(item.width_cm) || 0
    const H = Number(item.height_cm) || 0
    const purchase = Number(item.purchase_cost) || 0
    const priceRub = Number(pl.price_rub) || 0
    const priceRmb = Number(pl.price_rmb) || 0
    const discount = Number(pl.discount_pct) || 0

    // 体积 m³ (4 位小数), 密度 kg/m³ (2 位小数)
    const volumeRaw = (L * W * H) / 1_000_000
    const volume = volumeRaw > 0 ? Number(volumeRaw.toFixed(4)) : null
    const density = volume && weight > 0 ? Number((weight / volume).toFixed(2)) : null

    // 前台售价 RUB
    const frontPriceRub = priceRub * (1 - discount / 100)

    // 头程单价: 按 density 匹配 shippingRates
    let headPriceUsd = null
    if (density != null && sr.length > 0) {
      const sorted = [...sr].sort((a, b) => a.density_min - b.density_min)
      if (density < sorted[0].density_min) {
        headPriceUsd = sorted[0].price_usd  // 超小 → 第一档
      } else {
        const match = sorted.find(r => density >= r.density_min && density < r.density_max)
        if (match) {
          headPriceUsd = match.price_usd
        } else {
          headPriceUsd = sorted[sorted.length - 1].price_usd  // 超大 → 最后一档
        }
      }
    }

    // 头程费用 RMB
    const headFee = headPriceUsd != null && P.rate_usd_cny
      ? weight * headPriceUsd * P.rate_usd_cny
      : null

    // 订单处理费 (weight < threshold → light; else heavy)
    const orderFee = P.order_fee_threshold_kg != null && P.order_fee_light != null && P.order_fee_heavy != null
      ? (weight < P.order_fee_threshold_kg ? P.order_fee_light : P.order_fee_heavy)
      : null

    // 尾程运费 RMB = L×W×H/1000 + 4
    const tailFee = (L > 0 && W > 0 && H > 0) ? (L * W * H / 1000 + 4) : null

    // 佣金率 (佣金表存小数,如 0.11); rateEntry 由调用方按 id 单独 fetch 传入
    const commissionRateDecimal = rateEntry ? Number(rateEntry.rate) : null
    const commissionRatePct = commissionRateDecimal != null ? commissionRateDecimal * 100 : null

    // 佣金 RMB
    const commission = commissionRateDecimal != null ? priceRmb * commissionRateDecimal : null

    // 提现手续费 RMB = (price_rmb - 尾程 - 佣金) × withdrawal_rate
    const withdrawalFee = (tailFee != null && commission != null && P.withdrawal_rate != null)
      ? (priceRmb - tailFee - commission) * P.withdrawal_rate
      : null

    // 利润 RMB
    let profit = null
    if (headFee != null && orderFee != null && tailFee != null && commission != null && withdrawalFee != null) {
      profit = priceRmb - (purchase + headFee + orderFee + tailFee + commission + withdrawalFee)
    }

    // 利润率 %
    const profitRatePct = (profit != null && priceRmb > 0) ? (profit / priceRmb) * 100 : null

    return {
      volume, density, frontPriceRub,
      headPriceUsd, headFee,
      orderFee, tailFee,
      commissionRatePct, commission, withdrawalFee,
      profit, profitRatePct,
    }
  })
}
```

- [ ] **Step 8.2：手工自测（控制台）**

打开浏览器 DevTools 控制台（任意已登录页面），粘贴一段 sanity check：

```js
// 直接从源码 copy 函数到控制台测一次,用已知值
// 输入: weight=1.5, L=20, W=15, H=10, purchase=10
// priceRub=1000, priceRmb=80, discount=10
// rate_rub_cny=0.08, rate_usd_cny=7.2, threshold=2, light=6, heavy=10, withdrawal=0.015
// commissionRate=0.15 (wb_cross_rate_id=1 对应 {rate: 0.15})
// shippingRate: [{density_min:0, density_max:100, price_usd:3.8}]
//
// 期望:
// volume = 20*15*10/1e6 = 0.003
// density = 1.5/0.003 = 500 → 超最后一档 → 取最后一档 3.8
// frontPriceRub = 1000 * 0.9 = 900
// headFee = 1.5 * 3.8 * 7.2 = 41.04
// orderFee = 6 (1.5 < 2)
// tailFee = 20*15*10/1000 + 4 = 3 + 4 = 7
// commission = 80 * 0.15 = 12
// withdrawalFee = (80-7-12)*0.015 = 0.915
// profit = 80 - (10+41.04+6+7+12+0.915) = 80 - 76.955 = 3.045
// profitRate = 3.045/80*100 = ~3.81
```

这一步是心算校对，不用跑代码。如果后续 UI 和这个期望对不上，回来 debug。

- [ ] **Step 8.3：Commit**

```bash
git add frontend/src/composables/usePricingCalc.js
git commit -m "feat(pricing): usePricingCalc 计算 composable"
```

---

## Task 9：ParamsTab.vue 参数表单

**Files:**
- Modify: `frontend/src/components/pricing/ParamsTab.vue`（替换占位）

- [ ] **Step 9.1：实现参数表单**

完整替换占位内容：

```vue
<template>
  <div style="max-width: 500px">
    <el-form v-loading="loading" label-width="180px">
      <el-form-item label="RUB→RMB 汇率">
        <el-input-number v-model="params.rate_rub_cny" :precision="4" :step="0.001" :min="0.0001" />
        <span style="margin-left: 8px; color: #909399">1 RUB = ? RMB</span>
      </el-form-item>
      <el-form-item label="USD→RMB 汇率">
        <el-input-number v-model="params.rate_usd_cny" :precision="2" :step="0.1" :min="0.01" />
        <span style="margin-left: 8px; color: #909399">1 USD = ? RMB</span>
      </el-form-item>
      <el-form-item label="订单处理费阈值 (kg)">
        <el-input-number v-model="params.order_fee_threshold_kg" :precision="1" :step="0.1" :min="0" />
      </el-form-item>
      <el-form-item label="阈值以下 (RMB)">
        <el-input-number v-model="params.order_fee_light" :precision="2" :step="0.5" :min="0" />
      </el-form-item>
      <el-form-item label="阈值以上 (RMB)">
        <el-input-number v-model="params.order_fee_heavy" :precision="2" :step="0.5" :min="0" />
      </el-form-item>
      <el-form-item label="提现手续费率">
        <el-input-number v-model="params.withdrawal_rate" :precision="4" :step="0.001" :min="0" :max="1" />
        <span style="margin-left: 8px; color: #909399">0.015 = 1.5%</span>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

const params = reactive({
  rate_rub_cny: 0.08,
  rate_usd_cny: 7.2,
  order_fee_threshold_kg: 2,
  order_fee_light: 6,
  order_fee_heavy: 10,
  withdrawal_rate: 0.015,
})
const loading = ref(false)
const saving = ref(false)

async function fetchParams() {
  loading.value = true
  try {
    const { data } = await api.get('/api/pricing/params')
    Object.assign(params, data)
  } catch {
    ElMessage.error('加载参数失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await api.put('/api/pricing/params', params)
    ElMessage.success('参数已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(fetchParams)
</script>
```

- [ ] **Step 9.2：手工验证**

浏览器访问 `/pricing`，切到"参数"tab：
- 看到 6 个字段，默认值正确（0.08 / 7.2 / 2 / 6 / 10 / 0.015）
- 改 `rate_rub_cny` → `0.085` → 点"保存" → 看到绿色提示"参数已保存"
- 刷新页面回到这个 tab → `rate_rub_cny` 仍是 `0.085`
- 恢复 `0.08` → 保存

- [ ] **Step 9.3：Commit**

```bash
git add frontend/src/components/pricing/ParamsTab.vue
git commit -m "feat(pricing): ParamsTab 参数表单"
```

---

## Task 10：PricingListTab.vue 列表骨架（取数据 + 搜索 + 新增按钮）

**Files:**
- Modify: `frontend/src/components/pricing/PricingListTab.vue`

- [ ] **Step 10.1：实现列表骨架（卡片暂用简单版）**

替换占位：

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <el-input
        v-model="search"
        placeholder="搜索 SKU 或方案名"
        style="width: 300px"
        clearable
        @clear="fetchItems"
        @keyup.enter="fetchItems"
      />
      <el-button type="primary" @click="addDraft">新增定价方案</el-button>
    </div>

    <el-empty v-if="!loading && items.length === 0 && !hasDraft" description="暂无定价方案,点右上角新增" />

    <div v-loading="loading" style="display: flex; flex-direction: column; gap: 16px">
      <PricingCard
        v-for="it in items"
        :key="it.id"
        :item="it"
        :params="params"
        :shipping-rates="shippingRates"
        @saved="fetchItems"
        @deleted="fetchItems"
      />
      <!-- 新增草稿卡片 -->
      <PricingCard
        v-if="draftItem"
        :item="draftItem"
        :params="params"
        :shipping-rates="shippingRates"
        :is-draft="true"
        @saved="onDraftSaved"
        @cancel="draftItem = null"
      />
    </div>

    <el-pagination
      v-if="total > pageSize"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="p => { page = p; fetchItems() }"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'
import PricingCard from './PricingCard.vue'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const loading = ref(false)

const params = ref({})
const shippingRates = ref([])

const draftItem = ref(null)
const hasDraft = computed(() => !!draftItem.value)

function emptyItem() {
  return {
    id: null,
    name: '',
    sku: '',
    product_id: null,
    image_url: '',
    purchase_cost: 0,
    weight_kg: 0,
    length_cm: 0, width_cm: 0, height_cm: 0,
    wb_local_rate_id: null,
    wb_cross_rate_id: null,
    ozon_local_rate_id: null,
    platforms: [{ platform: 'wb_cross_fbs', price_rub: 0, price_rmb: 0, discount_pct: 0, extra: {} }],
  }
}

function addDraft() {
  if (draftItem.value) return  // 已有草稿,避免重复
  draftItem.value = emptyItem()
}

function onDraftSaved() {
  draftItem.value = null
  fetchItems()
}

async function fetchItems() {
  loading.value = true
  try {
    const { data } = await api.get('/api/pricing/items', {
      params: { page: page.value, page_size: pageSize.value, search: search.value },
    })
    items.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('加载定价列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchParams() {
  try {
    const { data } = await api.get('/api/pricing/params')
    params.value = data
  } catch { /* 用默认 */ }
}

async function fetchDefaultShipping() {
  try {
    const { data: d } = await api.get('/api/shipping/default-template')
    if (!d.id) return
    const { data: templates } = await api.get('/api/shipping/templates')
    const tpl = templates.find(t => t.id === d.id)
    if (tpl) shippingRates.value = tpl.rates || []
  } catch { /* 没配默认模板,shippingRates 保持 [] */ }
}

onMounted(async () => {
  await Promise.all([fetchParams(), fetchDefaultShipping()])
  await fetchItems()
})
</script>
```

- [ ] **Step 10.2：手工验证**

浏览器刷新 `/pricing`，定价表 tab：
- 页面不报错（`PricingCard` 组件还没完整，但占位没问题）
- 点击"新增定价方案" → 如果 PricingCard 还没实现完整，可能会报错；**这一步允许暂时报错，Task 11/12 补齐**

- [ ] **Step 10.3：Commit**

```bash
git add frontend/src/components/pricing/PricingListTab.vue
git commit -m "feat(pricing): 列表骨架 + 加载 params/shipping/commission"
```

---

## Task 11：PricingCard.vue 左侧商品信息区

**Files:**
- Create/Modify: `frontend/src/components/pricing/PricingCard.vue`

- [ ] **Step 11.1：实现卡片左侧（商品信息 + 类目）**

**本 task 只实现左侧 + emit 骨架，右侧定价区留空占位**（Task 12 补齐）。

```vue
<template>
  <el-card shadow="hover">
    <el-row :gutter="16">
      <!-- 左侧:商品信息 -->
      <el-col :span="10">
        <div style="display: flex; gap: 12px; margin-bottom: 12px">
          <el-input v-model="form.name" placeholder="方案名,例如 春季定价" style="flex: 1" />
          <el-select
            v-model="form.product_id"
            placeholder="搜索 SKU (可留空)"
            filterable
            remote
            clearable
            :remote-method="searchProducts"
            :loading="productLoading"
            style="flex: 1"
            @change="onProductChange"
          >
            <el-option
              v-for="p in productOptions"
              :key="p.id"
              :label="`${p.sku} ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </div>

        <div style="display: flex; gap: 12px; align-items: flex-start">
          <!-- 图片 -->
          <div style="width: 80px; height: 80px; border: 1px dashed #dcdfe6; display: flex; align-items: center; justify-content: center; overflow: hidden">
            <el-image
              v-if="form.image_url"
              :src="imgUrl(form.image_url)"
              fit="contain"
              style="width: 100%; height: 100%"
            />
            <span v-else style="color: #ccc; font-size: 12px">无图</span>
          </div>

          <el-form label-width="80px" label-position="top" style="flex: 1">
            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="采购成本 (¥)">
                  <el-input-number v-model="form.purchase_cost" :precision="2" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="重量 (kg)">
                  <el-input-number v-model="form.weight_kg" :precision="3" :step="0.1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="8">
              <el-col :span="8">
                <el-form-item label="长 (cm)">
                  <el-input-number v-model="form.length_cm" :precision="1" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="宽 (cm)">
                  <el-input-number v-model="form.width_cm" :precision="1" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="高 (cm)">
                  <el-input-number v-model="form.height_cm" :precision="1" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <div style="color: #909399; font-size: 13px; margin-top: 4px">
              体积 {{ calc.volume != null ? calc.volume.toFixed(4) : '-' }} m³
              | 密度 {{ calc.density != null ? calc.density.toFixed(2) : '-' }} kg/m³
            </div>
          </el-form>
        </div>

        <!-- 三个类目 -->
        <el-form label-width="100px" style="margin-top: 12px">
          <el-form-item label="WB 本土类目">
            <CommissionRateSelect v-model="form.wb_local_rate_id" platform="wb_local" />
          </el-form-item>
          <el-form-item label="WB 跨境类目">
            <CommissionRateSelect v-model="form.wb_cross_rate_id" platform="wb_cross_border" />
          </el-form-item>
          <el-form-item label="OZON 本土类目">
            <CommissionRateSelect v-model="form.ozon_local_rate_id" platform="ozon_local" />
          </el-form-item>
        </el-form>
      </el-col>

      <!-- 右侧:定价区 (Task 12 实现) -->
      <el-col :span="14">
        <div style="border-left: 1px solid #ebeef5; padding-left: 16px; min-height: 300px">
          <div style="color: #909399">WB 跨境 FBS 定价 (Task 12 实现)</div>
          <!-- 占位 -->
        </div>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <div style="margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px">
      <el-button v-if="isDraft" @click="$emit('cancel')">取消</el-button>
      <el-popconfirm v-if="!isDraft" title="确定删除此方案?" @confirm="remove">
        <template #reference>
          <el-button type="danger" link>删除</el-button>
        </template>
      </el-popconfirm>
      <el-button type="primary" :loading="saving" @click="save">{{ isDraft ? '保存' : '更新' }}</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { usePricingCalc } from '@/composables/usePricingCalc.js'
import CommissionRateSelect from './CommissionRateSelect.vue'

const props = defineProps({
  item: { type: Object, required: true },
  params: { type: Object, required: true },
  shippingRates: { type: Array, required: true },
  isDraft: { type: Boolean, default: false },
})

const emit = defineEmits(['saved', 'deleted', 'cancel'])

// 复制 props.item 到本地 reactive form
const form = reactive(JSON.parse(JSON.stringify(props.item)))
const saving = ref(false)

// WB 跨境佣金率对象 (按 id 单独 fetch,用于 usePricingCalc 计算)
const wbCrossRate = ref(null)
watch(() => form.wb_cross_rate_id, async (id) => {
  if (!id) { wbCrossRate.value = null; return }
  try {
    const { data } = await api.get(`/api/pricing/rate/${id}`)
    wbCrossRate.value = data
  } catch { wbCrossRate.value = null }
}, { immediate: true })

// ======== SKU/Product 搜索 ========
const productOptions = ref([])
const productLoading = ref(false)

async function searchProducts(query) {
  if (!query) { productOptions.value = []; return }
  productLoading.value = true
  try {
    const { data } = await api.get('/api/products', {
      params: { page: 1, page_size: 20, search: query },
    })
    productOptions.value = data.products || data.items || []  // 兼容两种响应形状
  } catch { productOptions.value = [] } finally { productLoading.value = false }
}

async function onProductChange(productId) {
  if (!productId) return
  const p = productOptions.value.find(x => x.id === productId)
  if (p) {
    form.sku = p.sku || form.sku
    form.image_url = p.image || p.image_url || ''
    form.purchase_cost = p.purchase_price || 0
    form.weight_kg = p.weight || 0
    form.length_cm = p.length || 0
    form.width_cm = p.width || 0
    form.height_cm = p.height || 0
  }
}

// ======== 计算 ========
const platform0 = computed(() => form.platforms[0] || {})

const calc = usePricingCalc(
  computed(() => form),
  platform0,
  computed(() => props.params),
  wbCrossRate,
  computed(() => props.shippingRates),
)

// ======== 保存/删除 ========
async function save() {
  saving.value = true
  try {
    const payload = { ...form }
    if (props.isDraft) {
      await api.post('/api/pricing/items', payload)
      ElMessage.success('保存成功')
    } else {
      await api.put(`/api/pricing/items/${form.id}`, payload)
      ElMessage.success('更新成功')
    }
    emit('saved')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally { saving.value = false }
}

async function remove() {
  try {
    await api.delete(`/api/pricing/items/${form.id}`)
    ElMessage.success('已删除')
    emit('deleted')
  } catch { ElMessage.error('删除失败') }
}

function imgUrl(u) {
  if (!u) return ''
  if (u.startsWith('http')) return u
  return u  // 相对路径直接用,由 vite proxy 处理
}
</script>
```

- [ ] **Step 11.2：创建 CommissionRateSelect 子组件**

新建 `frontend/src/components/pricing/CommissionRateSelect.vue`：

```vue
<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    placeholder="搜索商品名"
    :remote-method="search"
    :loading="loading"
    style="width: 100%"
    @update:model-value="v => $emit('update:modelValue', v)"
  >
    <el-option
      v-for="r in options"
      :key="r.id"
      :label="`${r.category} / ${r.product_name} (${(r.rate * 100).toFixed(2)}%)`"
      :value="r.id"
    />
  </el-select>
</template>

<script setup>
import { ref } from 'vue'
import api from '@/api'

const props = defineProps({
  modelValue: { type: Number, default: null },
  platform: { type: String, required: true },
})
defineEmits(['update:modelValue'])

const options = ref([])
const loading = ref(false)

async function search(query) {
  if (!query) { options.value = []; return }
  loading.value = true
  try {
    const { data } = await api.get('/api/commission/rates', {
      params: { platform: props.platform, product: query, page: 1, page_size: 30 },
    })
    options.value = data.rates || []
  } catch { options.value = [] } finally { loading.value = false }
}
</script>
```

- [ ] **Step 11.3：手工验证**

浏览器刷新 `/pricing`：
- 点"新增定价方案" → 出现一张新卡片
- 填方案名、SKU（搜索商品）→ 选一个 → 图片/采购/重量/长宽高自动填上
- 体积、密度实时计算，显示在长宽高下面
- 三个类目下拉输入关键词能搜到
- 点"保存" → 绿色提示"保存成功" → 列表刷新出现新条目

- [ ] **Step 11.4：Commit**

```bash
git add frontend/src/components/pricing/PricingCard.vue frontend/src/components/pricing/CommissionRateSelect.vue
git commit -m "feat(pricing): 卡片左侧商品信息 + SKU/类目搜索 + 新建保存"
```

---

## Task 12：PricingCard.vue 右侧 WB 跨境 FBS 定价行

**Files:**
- Modify: `frontend/src/components/pricing/PricingCard.vue`（右侧占位替换）

- [ ] **Step 12.1：实现右侧定价区**

替换右侧 `<el-col :span="14">` 内的占位 div：

```vue
<el-col :span="14">
  <div style="border-left: 1px solid #ebeef5; padding-left: 16px">
    <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px; color: #303133">
      WB 跨境 FBS
    </div>

    <!-- 第 1 行: 定价双向 + 折扣 -->
    <el-row :gutter="12">
      <el-col :span="8">
        <label style="font-size: 12px; color: #606266">定价 (RUB)</label>
        <el-input
          :model-value="platform0.price_rub"
          type="number"
          step="1"
          size="default"
          @input="onChangeRub"
        />
      </el-col>
      <el-col :span="8">
        <label style="font-size: 12px; color: #606266">定价 (RMB)</label>
        <el-input
          :model-value="platform0.price_rmb"
          type="number"
          step="0.1"
          size="default"
          @input="onChangeRmb"
        />
      </el-col>
      <el-col :span="8">
        <label style="font-size: 12px; color: #606266">平台折扣 (%)</label>
        <el-input-number
          v-model="platform0.discount_pct"
          :precision="1" :step="1" :min="0" :max="100"
          style="width: 100%"
        />
      </el-col>
    </el-row>

    <!-- 第 2 行: 派生字段 -->
    <el-descriptions :column="2" border size="small" style="margin-top: 12px">
      <el-descriptions-item label="前台售价 (RUB)">
        {{ fmt(calc.frontPriceRub, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="头程单价 (USD)">
        {{ fmt(calc.headPriceUsd, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="头程费用 (¥)">
        {{ fmt(calc.headFee, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="订单处理费 (¥)">
        {{ fmt(calc.orderFee, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="尾程运费 (¥)">
        {{ fmt(calc.tailFee, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="佣金率 (%)">
        {{ fmt(calc.commissionRatePct, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="佣金 (¥)">
        {{ fmt(calc.commission, 2) }}
      </el-descriptions-item>
      <el-descriptions-item label="提现手续费 (¥)">
        {{ fmt(calc.withdrawalFee, 2) }}
      </el-descriptions-item>
    </el-descriptions>

    <!-- 利润汇总 -->
    <div style="margin-top: 12px; padding: 10px; background: #f5f7fa; border-radius: 4px; display: flex; justify-content: space-around">
      <div>
        <div style="font-size: 12px; color: #909399">利润 (¥)</div>
        <div style="font-size: 18px; font-weight: 600" :style="{ color: profitColor }">
          {{ fmt(calc.profit, 2) }}
        </div>
      </div>
      <div>
        <div style="font-size: 12px; color: #909399">利润率</div>
        <div style="font-size: 18px; font-weight: 600" :style="{ color: profitColor }">
          {{ calc.profitRatePct != null ? calc.profitRatePct.toFixed(1) + '%' : '-' }}
        </div>
      </div>
    </div>
  </div>
</el-col>
```

在 `<script setup>` 加：

```js
// 放在现有 script setup 内,platform0 定义之后
function onChangeRub(v) {
  const num = Number(v) || 0
  form.platforms[0].price_rub = num
  form.platforms[0].price_rmb = props.params.rate_rub_cny
    ? Number((num * props.params.rate_rub_cny).toFixed(2))
    : 0
}

function onChangeRmb(v) {
  const num = Number(v) || 0
  form.platforms[0].price_rmb = num
  form.platforms[0].price_rub = props.params.rate_rub_cny
    ? Number((num / props.params.rate_rub_cny).toFixed(2))
    : 0
}

function fmt(v, digits = 2) {
  return v == null || Number.isNaN(v) ? '-' : Number(v).toFixed(digits)
}

const profitColor = computed(() => {
  const p = calc.value.profit
  if (p == null) return '#909399'
  return p >= 0 ? '#67c23a' : '#f56c6c'
})
```

- [ ] **Step 12.2：手工验证——关键用例**

浏览器刷新 `/pricing` 定价表 tab，点"新增定价方案"：

**Case A 全字段联动**：
1. 方案名填 "test"
2. 不选 SKU，手动填：采购成本 10, 重量 1.5, 长 20, 宽 15, 高 10
3. 体积显示 `0.0030 m³`, 密度显示 `500.00 kg/m³`
4. 选 WB 跨境类目（随便选一条，佣金率比如 15%）
5. 填折扣 10%
6. 填定价 RMB = 80 → RUB 自动变 1000
7. 核对右侧数字（基于 Task 8 的心算）：
   - 前台售价 RUB = 900
   - 头程单价 USD 显示模板里对应 density 500 的值
   - 订单处理费 = 6（1.5 < 2）
   - 尾程运费 = 7
   - 佣金 = 80 × 0.15 = 12
   - 利润 >= 0 绿色，< 0 红色

**Case B 双向换算**：
1. 删除 RMB 里的数字，改填 RUB = 1500
2. RMB 应自动变为 1500 × 0.08 = 120

**Case C 缺失字段**：
1. 清空 WB 跨境类目 → 佣金率、佣金、提现手续费、利润应显示 `-`

**Case D 保存**：
1. 点"保存" → 成功 → 列表刷新，新卡片 id 不再是 null

**Case E 编辑**：
1. 编辑已存在的卡片，改折扣 → 点"更新" → 成功
2. 刷新页面 → 折扣保留

**Case F 删除**：
1. 点"删除" → confirm → 成功 → 列表少一条

- [ ] **Step 12.3：Commit**

```bash
git add frontend/src/components/pricing/PricingCard.vue
git commit -m "feat(pricing): 卡片右侧 WB 跨境 FBS 定价行 + 实时联动 + 双向换算"
```

---

## Task 13：最终集成验收

**Files:**（无代码变更，纯验收）

- [ ] **Step 13.1：完整走一遍 spec 第 11 节验收标准**

按 [2026-04-23-pricing-module-design.md 第 11 节](../specs/2026-04-23-pricing-module-design.md) 的 13 条逐项勾选：

1. [ ] 左侧菜单新增"定价表"项
2. [ ] 打开页面看到 2 个 tab
3. [ ] 新建：填方案名 → 选 SKU → 自动填商品数据 → 选类目 → 填定价 → 保存
4. [ ] 不选 SKU 也能新建
5. [ ] 体积/密度实时算
6. [ ] 双向换算 RUB/RMB
7. [ ] 所有派生字段联动
8. [ ] 参数 tab 改汇率 → 定价 tab 跟着变（**刷新页面**让列表重新 fetch params）
9. [ ] 编辑卡片
10. [ ] 删除卡片（confirm 后）
11. [ ] 搜索按 SKU/方案名
12. [ ] 默认头程模板未设置时 → 头程字段显示 `-`
13. [ ] 后端 pytest 全绿（`cd backend && set TEST_MODE=1 && pytest tests/test_pricing.py -v`）

- [ ] **Step 13.2：回归验证（不破坏现有功能）**

访问现有页面快速点一遍，确认未引入 regression：
- /orders 订单管理能打开
- /finance 财务页 tab 切换正常
- /commission-shipping 佣金运费未被影响
- /purchase-plan 采购计划未被影响

- [ ] **Step 13.3：整理 + 最终 commit（如有 cleanup）**

如果在 13.1-13.2 中发现小问题，修后：

```bash
git add <改动文件>
git commit -m "fix(pricing): 验收发现的小修复"
```

---

## 执行注意事项

### 如果某个 task 卡住

1. **后端 uvicorn 报错**：保存文件后看终端栈；常见是 import 顺序或字段名错
2. **前端组件渲染不出来**：DevTools Console 看报错；常见是 props 未定义或 api 路径错
3. **SQLite database is locked**：见 CLAUDE.md 第 12 节；重启后端

### 不要做的事

- ❌ 不要为 WB 跨境 FBW / WB 本土 / OZON FBS / OZON FBO 写任何代码（本期范围外）
- ❌ 不要在前端引入 Vitest/Jest 等测试框架（spec 决定手工验收）
- ❌ 不要 push 到 GitHub（除非用户明确说"推"）

### 每个 task 之间

- 验证 OK → commit → 下一个 task
- 如果发现某个 task 的代码需要依赖后面 task 的内容，暂时用 TODO 标注并在下一个 task 里补齐
