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
    platform: str
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
    """全量替换 platforms (简单处理:删除再插入)"""
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
