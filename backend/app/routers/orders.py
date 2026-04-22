import threading
import traceback
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.shop import Shop
from app.models.setting import SystemSetting
from app.schemas.order import OrderOut, OrderListOut
from app.utils.deps import get_current_user, get_accessible_shop_ids, require_module, require_role
from app.services.sync import sync_shop_orders

router = APIRouter(prefix="/api/orders", tags=["orders"])

_order_sync_status = {"status": "idle"}
_order_sync_lock = threading.Lock()


@router.get("", response_model=OrderListOut)
def list_orders(
    shop_id: Optional[int] = Query(None),
    order_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="搜索订单号或产品SKU"),
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    accessible_shops: list[int] | None = Depends(get_accessible_shop_ids),
    _=Depends(require_module("orders")),
):
    query = db.query(Order)
    if accessible_shops is not None:
        query = query.filter(Order.shop_id.in_(accessible_shops))
    if shop_id:
        query = query.filter(Order.shop_id == shop_id)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    if status:
        query = query.filter(Order.status == status)
    if date_from:
        from datetime import datetime, timedelta, timezone
        _MSK = timezone(timedelta(hours=3))
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=_MSK)
            query = query.filter(Order.created_at >= d.astimezone(timezone.utc).replace(tzinfo=None))
        except ValueError:
            pass
    if date_to:
        from datetime import datetime, timedelta, timezone
        _MSK = timezone(timedelta(hours=3))
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=_MSK) + timedelta(days=1)
            query = query.filter(Order.created_at < d.astimezone(timezone.utc).replace(tzinfo=None))
        except ValueError:
            pass
    if search:
        keyword = f"%{search}%"
        # Find order IDs matching by SKU
        sku_order_ids = [
            row[0] for row in
            db.query(OrderItem.order_id).filter(OrderItem.sku.like(keyword)).all()
        ]
        # Search by order number, srid, or product SKU
        if sku_order_ids:
            query = query.filter(
                Order.wb_order_id.like(keyword) | Order.srid.like(keyword) | Order.id.in_(sku_order_ids)
            )
        else:
            query = query.filter(Order.wb_order_id.like(keyword) | Order.srid.like(keyword))
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Get exchange rate and shop types for CNY calculation
    rate_setting = db.query(SystemSetting).filter(SystemSetting.key == "exchange_rate_cny_rub").first()
    exchange_rate = float(rate_setting.value) if rate_setting and rate_setting.value else 0

    shop_ids = list({o.shop_id for o in orders})
    shop_types = {}
    if shop_ids:
        for s in db.query(Shop.id, Shop.type).filter(Shop.id.in_(shop_ids)).all():
            shop_types[s.id] = s.type

    items = []
    for o in orders:
        data = OrderOut.model_validate(o).model_dump()
        stype = shop_types.get(o.shop_id, "local")
        if stype == "local":
            # Local shop: price_cny = price_rub / exchange_rate
            data["price_cny"] = round(o.price_rub / exchange_rate, 2) if exchange_rate > 0 and o.price_rub > 0 else 0
        else:
            # Cross-border: total_price is already CNY
            data["price_cny"] = o.total_price
        items.append(data)

    return OrderListOut(items=items, total=total)


# --- Sync endpoints (must be before /{order_id} to avoid route conflict) ---

def _run_order_sync(shop_ids: list[int], days_back: int, clear: bool):
    db = SessionLocal()
    try:
        shops = db.query(Shop).filter(
            Shop.is_active == True, Shop.id.in_(shop_ids)
        ).all()
        if not shops:
            with _order_sync_lock:
                _order_sync_status["status"] = "error"
                _order_sync_status["detail"] = "所选店铺均不存在或未启用"
            return

        if clear:
            with _order_sync_lock:
                _order_sync_status["detail"] = "正在清除所选店铺的旧订单数据..."
            sids = [s.id for s in shops]
            order_ids = [r[0] for r in db.query(Order.id).filter(Order.shop_id.in_(sids)).all()]
            if order_ids:
                db.query(OrderStatusLog).filter(OrderStatusLog.order_id.in_(order_ids)).delete(synchronize_session=False)
                db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).delete(synchronize_session=False)
                db.query(Order).filter(Order.id.in_(order_ids)).delete(synchronize_session=False)
            for shop in shops:
                shop.last_sync_at = None
            db.commit()

        with _order_sync_lock:
            _order_sync_status["detail"] = f"正在同步订单（回溯 {days_back} 天，{len(shops)} 店铺）..."

        date_from = datetime.now(timezone.utc) - timedelta(days=days_back)
        synced = 0
        for shop in shops:
            try:
                sync_shop_orders(db, shop, date_from=date_from)
                synced += 1
            except Exception as e:
                print(f"[OrderSync] Failed for {shop.name}: {e}")
                traceback.print_exc()
        with _order_sync_lock:
            _order_sync_status["status"] = "done"
            _order_sync_status["detail"] = f"已同步 {synced}/{len(shops)} 个店铺的订单（回溯 {days_back} 天）"
    except Exception as e:
        print(f"[OrderSync] Fatal error: {e}")
        traceback.print_exc()
        with _order_sync_lock:
            _order_sync_status["status"] = "error"
            _order_sync_status["detail"] = str(e)
    finally:
        db.close()


class SyncBody(BaseModel):
    shop_ids: list[int]
    days_back: int = 90
    clear: bool = False


@router.post("/sync")
def trigger_order_sync(
    body: SyncBody,
    _=Depends(require_role("admin", "operator")),
):
    if not body.shop_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个店铺")
    if body.days_back < 1 or body.days_back > 3650:
        raise HTTPException(status_code=400, detail="回溯天数需在 1 ~ 3650 之间")
    with _order_sync_lock:
        if _order_sync_status["status"] == "running":
            return {"status": "running", "detail": "订单同步进行中，请稍候"}
        _order_sync_status["status"] = "running"
        _order_sync_status["detail"] = ""
    thread = threading.Thread(
        target=_run_order_sync,
        args=(body.shop_ids, body.days_back, body.clear),
        daemon=True,
    )
    thread.start()
    return {"status": "running", "detail": "订单同步已启动"}


@router.get("/sync/status")
def order_sync_status(_=Depends(require_role("admin", "operator"))):
    with _order_sync_lock:
        return dict(_order_sync_status)


# --- Single order detail ---

@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _=Depends(require_module("orders"))):
    query = db.query(Order).filter(Order.id == order_id)
    if accessible_shops is not None:
        query = query.filter(Order.shop_id.in_(accessible_shops))
    order = query.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


