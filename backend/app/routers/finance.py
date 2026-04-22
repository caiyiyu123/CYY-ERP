from datetime import date
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.shop import Shop
from app.models.order import Order
from app.models.finance import FinanceOrderRecord, FinanceOtherFee, FinanceSyncLog
from app.models.user import User
from app.services.finance_sync import sync_shop, sync_shop_all_history, fill_purchase_cost_and_profit
from app.utils.deps import get_accessible_shop_ids, require_module, get_current_user

router = APIRouter(prefix="/api/finance", tags=["finance"])


_sync_pool = ThreadPoolExecutor(max_workers=2)


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _sync_shop_blocking(db, shop, *, date_from, date_to, triggered_by, user_id, log_id=None):
    """Indirection so tests can monkeypatch without touching the service module."""
    return sync_shop(db, shop, date_from=date_from, date_to=date_to,
                     triggered_by=triggered_by, user_id=user_id, log_id=log_id)


def _sync_shop_in_background(shop_id: int, date_from: date, date_to: date,
                             user_id: Optional[int], log_id: int):
    db = SessionLocal()
    try:
        shop = db.query(Shop).get(shop_id)
        if not shop:
            return
        _sync_shop_blocking(db, shop, date_from=date_from, date_to=date_to,
                            triggered_by="manual", user_id=user_id, log_id=log_id)
    finally:
        db.close()


def _sync_shop_all_history_in_background(shop_id: int, user_id: Optional[int], log_id: int):
    db = SessionLocal()
    try:
        shop = db.query(Shop).get(shop_id)
        if not shop:
            return
        sync_shop_all_history(db, shop, triggered_by="manual_all",
                              user_id=user_id, log_id=log_id)
    finally:
        db.close()


_ORDERS_SORT_WHITELIST = {
    "sale_date", "order_date", "net_to_seller", "net_profit",
    "purchase_cost", "quantity", "commission_amount", "delivery_fee",
}


class SyncBody(BaseModel):
    shop_ids: list[int]
    date_from: date
    date_to: date


class SyncAllBody(BaseModel):
    shop_ids: list[int]


class RecalcBody(BaseModel):
    shop_id: int


def _currency_for(shop_type: str) -> str:
    return "CNY" if shop_type == "cross_border" else "RUB"


def _shop_ids_filter(db: Session, shop_type: str, shop_id: Optional[int],
                     accessible_shops: Optional[list[int]]) -> list[int]:
    q = db.query(Shop.id).filter(Shop.type == shop_type)
    if shop_id:
        q = q.filter(Shop.id == shop_id)
    if accessible_shops is not None:
        q = q.filter(Shop.id.in_(accessible_shops))
    return [row[0] for row in q.all()]


@router.get("/summary")
def finance_summary(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    order_date_from: Optional[date] = Query(None),
    order_date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    currency = _currency_for(shop_type)
    sids = _shop_ids_filter(db, shop_type, shop_id, accessible_shops)
    if not sids:
        return {
            "currency": currency, "order_count": 0,
            "total_net_to_seller": 0, "total_commission": 0,
            "total_delivery_fee": 0, "total_fine": 0,
            "total_storage": 0, "total_deduction": 0,
            "total_purchase_cost": 0, "total_net_profit": 0,
            "total_other_fees": 0,
            "other_fees_by_type": {"storage": 0, "fine": 0, "deduction": 0, "logistics_adjust": 0, "other": 0},
            "final_profit": 0,
            "missing_mapping_count": 0,
        }

    base = db.query(FinanceOrderRecord).filter(FinanceOrderRecord.shop_id.in_(sids))
    if date_from:
        base = base.filter(FinanceOrderRecord.sale_date >= date_from)
    if date_to:
        base = base.filter(FinanceOrderRecord.sale_date <= date_to)
    if order_date_from:
        base = base.filter(FinanceOrderRecord.order_date >= order_date_from)
    if order_date_to:
        base = base.filter(FinanceOrderRecord.order_date <= order_date_to)
    agg = base.with_entities(
        func.count(FinanceOrderRecord.id),
        func.coalesce(func.sum(FinanceOrderRecord.net_to_seller), 0),
        func.coalesce(func.sum(FinanceOrderRecord.commission_amount), 0),
        func.coalesce(func.sum(FinanceOrderRecord.delivery_fee), 0),
        func.coalesce(func.sum(FinanceOrderRecord.fine), 0),
        func.coalesce(func.sum(FinanceOrderRecord.storage_fee), 0),
        func.coalesce(func.sum(FinanceOrderRecord.deduction), 0),
        func.coalesce(func.sum(FinanceOrderRecord.purchase_cost), 0),
        func.coalesce(func.sum(FinanceOrderRecord.net_profit), 0),
    ).one()
    (order_count, net_to_seller, commission, delivery, fine, storage,
     deduction, purchase_cost, net_profit) = agg

    missing = base.filter(FinanceOrderRecord.has_sku_mapping == False).count()

    ofq = db.query(
        FinanceOtherFee.fee_type,
        func.coalesce(func.sum(FinanceOtherFee.amount), 0),
    ).filter(FinanceOtherFee.shop_id.in_(sids))
    if date_from:
        ofq = ofq.filter(FinanceOtherFee.sale_date >= date_from)
    if date_to:
        ofq = ofq.filter(FinanceOtherFee.sale_date <= date_to)
    if order_date_from:
        ofq = ofq.filter(FinanceOtherFee.order_date >= order_date_from)
    if order_date_to:
        ofq = ofq.filter(FinanceOtherFee.order_date <= order_date_to)
    other_fees_by_type = {"storage": 0.0, "fine": 0.0, "deduction": 0.0, "logistics_adjust": 0.0, "other": 0.0}
    for ft, amt in ofq.group_by(FinanceOtherFee.fee_type).all():
        key = ft if ft in other_fees_by_type else "other"
        other_fees_by_type[key] += float(amt or 0)
    other_total = sum(other_fees_by_type.values())

    return {
        "currency": currency,
        "order_count": int(order_count),
        "total_net_to_seller": float(net_to_seller),
        "total_commission": float(commission),
        "total_delivery_fee": float(delivery),
        "total_fine": float(fine),
        "total_storage": float(storage),
        "total_deduction": float(deduction),
        "total_purchase_cost": float(purchase_cost),
        "total_net_profit": float(net_profit),
        "total_other_fees": float(other_total),
        "other_fees_by_type": other_fees_by_type,
        "final_profit": float(net_profit) - float(other_total),
        "missing_mapping_count": int(missing),
    }


@router.get("/orders")
def finance_orders(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    order_date_from: Optional[date] = Query(None),
    order_date_to: Optional[date] = Query(None),
    has_return: Optional[bool] = Query(None),
    has_mapping: Optional[bool] = Query(None),
    srid: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort: str = Query("-sale_date"),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    sids = _shop_ids_filter(db, shop_type, shop_id, accessible_shops)
    if not sids:
        return {"items": [], "total": 0}
    q = db.query(FinanceOrderRecord).filter(FinanceOrderRecord.shop_id.in_(sids))
    if date_from:
        q = q.filter(FinanceOrderRecord.sale_date >= date_from)
    if date_to:
        q = q.filter(FinanceOrderRecord.sale_date <= date_to)
    if order_date_from:
        q = q.filter(FinanceOrderRecord.order_date >= order_date_from)
    if order_date_to:
        q = q.filter(FinanceOrderRecord.order_date <= order_date_to)
    if has_return is not None:
        q = q.filter(FinanceOrderRecord.has_return_row == has_return)
    if has_mapping is not None:
        q = q.filter(FinanceOrderRecord.has_sku_mapping == has_mapping)
    if srid:
        q = q.filter(FinanceOrderRecord.srid.like(f"%{srid.strip()}%"))

    total = q.count()
    sort_col = sort.lstrip("-+")
    if sort_col not in _ORDERS_SORT_WHITELIST:
        sort_col = "sale_date"
    order_col = getattr(FinanceOrderRecord, sort_col)
    if sort.startswith("-"):
        order_col = order_col.desc()
    q = q.order_by(order_col).offset((page - 1) * page_size).limit(page_size)

    shops = {s.id: s.name for s in db.query(Shop).filter(Shop.id.in_(sids)).all()}
    rows = q.all()
    # 按 srid 关联 Order 表取真实订单状态
    srids = [r.srid for r in rows if r.srid]
    status_map: dict[str, str] = {}
    if srids:
        for srid_val, status_val in (
            db.query(Order.srid, Order.status)
            .filter(Order.shop_id.in_(sids), Order.srid.in_(srids))
            .all()
        ):
            status_map[srid_val] = status_val
    items = []
    for r in rows:
        items.append({
            "id": r.id, "srid": r.srid,
            "shop_id": r.shop_id, "shop_name": shops.get(r.shop_id, ""),
            "sale_date": r.sale_date.isoformat() if r.sale_date else None,
            "order_date": r.order_date.isoformat() if r.order_date else None,
            "nm_id": r.nm_id, "shop_sku": r.shop_sku,
            "product_name": r.product_name,
            "quantity": r.quantity, "return_quantity": r.return_quantity,
            "retail_price": r.retail_price, "sold_price": r.sold_price,
            "net_to_seller": r.net_to_seller,
            "commission_rate": r.commission_rate,
            "commission_amount": r.commission_amount,
            "delivery_fee": r.delivery_fee,
            "fine": r.fine, "storage_fee": r.storage_fee, "deduction": r.deduction,
            "purchase_cost": r.purchase_cost, "net_profit": r.net_profit,
            "has_sku_mapping": r.has_sku_mapping, "has_return_row": r.has_return_row,
            "warehouse": r.warehouse, "country": r.country, "sale_type": r.sale_type,
            "barcode": r.barcode, "category": r.category, "size": r.size,
            "currency": r.currency,
            "order_status": status_map.get(r.srid),
        })
    return {"items": items, "total": total}


@router.get("/other-fees")
def finance_other_fees(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    order_date_from: Optional[date] = Query(None),
    order_date_to: Optional[date] = Query(None),
    fee_type: Optional[str] = Query(None),
    srid: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    sids = _shop_ids_filter(db, shop_type, shop_id, accessible_shops)
    if not sids:
        return {"items": [], "total": 0}
    q = db.query(FinanceOtherFee).filter(FinanceOtherFee.shop_id.in_(sids))
    if date_from:
        q = q.filter(FinanceOtherFee.sale_date >= date_from)
    if date_to:
        q = q.filter(FinanceOtherFee.sale_date <= date_to)
    if order_date_from:
        q = q.filter(FinanceOtherFee.order_date >= order_date_from)
    if order_date_to:
        q = q.filter(FinanceOtherFee.order_date <= order_date_to)
    if fee_type:
        q = q.filter(FinanceOtherFee.fee_type == fee_type)
    if srid and srid.strip():
        q = q.filter(FinanceOtherFee.srid.ilike(f"%{srid.strip()}%"))
    total = q.count()
    rows = (
        q.order_by(FinanceOtherFee.sale_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for f in rows:
        items.append({
            "id": f.id, "shop_id": f.shop_id, "currency": f.currency,
            "srid": f.srid or "",
            "order_date": f.order_date.isoformat() if f.order_date else None,
            "sale_date": f.sale_date.isoformat() if f.sale_date else None,
            "fee_type": f.fee_type, "fee_description": f.fee_description,
            "amount": f.amount,
        })
    return {"items": items, "total": total}


@router.get("/reconciliation")
def finance_reconciliation(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    order_date_from: Optional[date] = Query(None),
    order_date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    sids = _shop_ids_filter(db, shop_type, shop_id, accessible_shops)
    if not sids:
        return {"missing_in_orders": [], "missing_in_finance": []}

    shops = {s.id: s.name for s in db.query(Shop).filter(Shop.id.in_(sids)).all()}

    missing_in_orders_q = (
        db.query(FinanceOrderRecord)
        .outerjoin(Order, and_(Order.srid == FinanceOrderRecord.srid,
                               Order.shop_id == FinanceOrderRecord.shop_id))
        .filter(
            Order.id.is_(None),
            FinanceOrderRecord.shop_id.in_(sids),
        )
    )
    if date_from:
        missing_in_orders_q = missing_in_orders_q.filter(FinanceOrderRecord.sale_date >= date_from)
    if date_to:
        missing_in_orders_q = missing_in_orders_q.filter(FinanceOrderRecord.sale_date <= date_to)
    if order_date_from:
        missing_in_orders_q = missing_in_orders_q.filter(FinanceOrderRecord.order_date >= order_date_from)
    if order_date_to:
        missing_in_orders_q = missing_in_orders_q.filter(FinanceOrderRecord.order_date <= order_date_to)
    missing_in_orders_rows = missing_in_orders_q.all()
    missing_in_orders = [
        {"srid": r.srid, "shop_name": shops.get(r.shop_id, ""),
         "sale_date": r.sale_date.isoformat() if r.sale_date else None,
         "order_date": r.order_date.isoformat() if r.order_date else None,
         "net_to_seller": r.net_to_seller, "currency": r.currency}
        for r in missing_in_orders_rows
    ]

    missing_in_finance_q = (
        db.query(Order)
        .outerjoin(FinanceOrderRecord, and_(
            FinanceOrderRecord.srid == Order.srid,
            FinanceOrderRecord.shop_id == Order.shop_id))
        .filter(
            FinanceOrderRecord.id.is_(None),
            Order.srid != "",
            Order.shop_id.in_(sids),
        )
    )
    # Order 表用 created_at 作为下单日期，没有结算日期，所以这里只看下单日期 + 兼容历史的 created_at
    if date_from:
        missing_in_finance_q = missing_in_finance_q.filter(Order.created_at >= date_from)
    if date_to:
        missing_in_finance_q = missing_in_finance_q.filter(func.date(Order.created_at) <= date_to)
    if order_date_from:
        missing_in_finance_q = missing_in_finance_q.filter(Order.created_at >= order_date_from)
    if order_date_to:
        missing_in_finance_q = missing_in_finance_q.filter(func.date(Order.created_at) <= order_date_to)
    missing_in_finance_rows = missing_in_finance_q.all()
    missing_in_finance = [
        {"wb_order_id": o.wb_order_id, "srid": o.srid,
         "shop_name": shops.get(o.shop_id, ""),
         "created_at": o.created_at.isoformat() if o.created_at else None,
         "total_price": o.total_price,
         "status": o.status}
        for o in missing_in_finance_rows
    ]

    return {"missing_in_orders": missing_in_orders, "missing_in_finance": missing_in_finance}


@router.post("/sync")
def finance_sync(
    body: SyncBody,
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    user: User = Depends(_require_admin),
    _=Depends(require_module("finance")),
):
    if accessible_shops is not None:
        body.shop_ids = [s for s in body.shop_ids if s in accessible_shops]
    if not body.shop_ids:
        raise HTTPException(status_code=400, detail="No accessible shops selected")

    log_ids: list[int] = []
    for sid in body.shop_ids:
        log = FinanceSyncLog(
            shop_id=sid, triggered_by="manual", user_id=user.id,
            date_from=body.date_from, date_to=body.date_to, status="running",
        )
        db.add(log); db.commit()
        log_ids.append(log.id)
        _sync_pool.submit(_sync_shop_in_background, sid, body.date_from, body.date_to, user.id, log.id)

    return {"sync_log_ids": log_ids}


@router.post("/sync-all")
def finance_sync_all(
    body: SyncAllBody,
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    user: User = Depends(_require_admin),
    _=Depends(require_module("finance")),
):
    """同步所选店铺的全部历史账单（突破 WB 单次 90 天上限）。"""
    if accessible_shops is not None:
        body.shop_ids = [s for s in body.shop_ids if s in accessible_shops]
    if not body.shop_ids:
        raise HTTPException(status_code=400, detail="No accessible shops selected")

    today = date.today()
    log_ids: list[int] = []
    for sid in body.shop_ids:
        log = FinanceSyncLog(
            shop_id=sid, triggered_by="manual_all", user_id=user.id,
            date_from=today, date_to=today, status="running",
        )
        db.add(log); db.commit()
        log_ids.append(log.id)
        _sync_pool.submit(_sync_shop_all_history_in_background, sid, user.id, log.id)

    return {"sync_log_ids": log_ids}


@router.get("/sync-logs")
def finance_sync_logs(
    ids: Optional[str] = Query(None, description="逗号分隔的 log id"),
    shop_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    q = db.query(FinanceSyncLog)
    if accessible_shops is not None:
        q = q.filter(FinanceSyncLog.shop_id.in_(accessible_shops))
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        q = q.filter(FinanceSyncLog.id.in_(id_list))
    if shop_id:
        q = q.filter(FinanceSyncLog.shop_id == shop_id)
    q = q.order_by(FinanceSyncLog.started_at.desc()).limit(limit)

    shops = {s.id: s.name for s in db.query(Shop).all()}
    return [
        {
            "id": l.id, "shop_id": l.shop_id, "shop_name": shops.get(l.shop_id, ""),
            "triggered_by": l.triggered_by, "status": l.status,
            "date_from": l.date_from.isoformat(), "date_to": l.date_to.isoformat(),
            "rows_fetched": l.rows_fetched, "orders_merged": l.orders_merged,
            "other_fees_count": l.other_fees_count, "error_message": l.error_message,
            "started_at": l.started_at.isoformat() if l.started_at else None,
            "finished_at": l.finished_at.isoformat() if l.finished_at else None,
        }
        for l in q.all()
    ]


@router.post("/recalc-profit")
def finance_recalc_profit(
    body: RecalcBody,
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _user: User = Depends(_require_admin),
    _=Depends(require_module("finance")),
):
    if accessible_shops is not None and body.shop_id not in accessible_shops:
        raise HTTPException(status_code=403, detail="No access to this shop")

    records = db.query(FinanceOrderRecord).filter(
        FinanceOrderRecord.shop_id == body.shop_id
    ).all()
    dicts = [
        {
            "shop_id": r.shop_id, "shop_sku": r.shop_sku, "quantity": r.quantity,
            "net_to_seller": r.net_to_seller, "delivery_fee": r.delivery_fee,
            "fine": r.fine, "storage_fee": r.storage_fee, "deduction": r.deduction,
            "purchase_cost": 0.0, "net_profit": 0.0, "has_sku_mapping": False,
        }
        for r in records
    ]
    fill_purchase_cost_and_profit(dicts, db, shop_id=body.shop_id)
    for r, d in zip(records, dicts):
        r.purchase_cost = d["purchase_cost"]
        r.has_sku_mapping = d["has_sku_mapping"]
        r.net_profit = d["net_profit"]
    db.commit()
    return {"updated": len(dicts)}
