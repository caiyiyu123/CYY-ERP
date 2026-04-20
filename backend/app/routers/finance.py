from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.shop import Shop
from app.models.order import Order
from app.models.finance import FinanceOrderRecord, FinanceOtherFee, FinanceSyncLog
from app.utils.deps import get_accessible_shop_ids, require_module

router = APIRouter(prefix="/api/finance", tags=["finance"])


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
    date_from: date = Query(...),
    date_to: date = Query(...),
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
            "total_other_fees": 0, "final_profit": 0,
            "missing_mapping_count": 0,
        }

    base = db.query(FinanceOrderRecord).filter(
        FinanceOrderRecord.shop_id.in_(sids),
        FinanceOrderRecord.sale_date.between(date_from, date_to),
    )
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

    other_total = db.query(func.coalesce(func.sum(FinanceOtherFee.amount), 0)).filter(
        FinanceOtherFee.shop_id.in_(sids),
        FinanceOtherFee.sale_date.between(date_from, date_to),
    ).scalar() or 0

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
        "final_profit": float(net_profit) - float(other_total),
        "missing_mapping_count": int(missing),
    }


@router.get("/orders")
def finance_orders(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: date = Query(...),
    date_to: date = Query(...),
    has_return: Optional[bool] = Query(None),
    has_mapping: Optional[bool] = Query(None),
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
    q = db.query(FinanceOrderRecord).filter(
        FinanceOrderRecord.shop_id.in_(sids),
        FinanceOrderRecord.sale_date.between(date_from, date_to),
    )
    if has_return is not None:
        q = q.filter(FinanceOrderRecord.has_return_row == has_return)
    if has_mapping is not None:
        q = q.filter(FinanceOrderRecord.has_sku_mapping == has_mapping)

    total = q.count()
    sort_col = sort.lstrip("-+")
    order_col = getattr(FinanceOrderRecord, sort_col, FinanceOrderRecord.sale_date)
    if sort.startswith("-"):
        order_col = order_col.desc()
    q = q.order_by(order_col).offset((page - 1) * page_size).limit(page_size)

    shops = {s.id: s.name for s in db.query(Shop).filter(Shop.id.in_(sids)).all()}
    items = []
    for r in q.all():
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
        })
    return {"items": items, "total": total}


@router.get("/other-fees")
def finance_other_fees(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: date = Query(...),
    date_to: date = Query(...),
    fee_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    sids = _shop_ids_filter(db, shop_type, shop_id, accessible_shops)
    if not sids:
        return {"items": [], "total": 0}
    q = db.query(FinanceOtherFee).filter(
        FinanceOtherFee.shop_id.in_(sids),
        FinanceOtherFee.sale_date.between(date_from, date_to),
    )
    if fee_type:
        q = q.filter(FinanceOtherFee.fee_type == fee_type)
    total = q.count()
    items = []
    for f in q.order_by(FinanceOtherFee.sale_date.desc()).all():
        items.append({
            "id": f.id, "shop_id": f.shop_id, "currency": f.currency,
            "sale_date": f.sale_date.isoformat() if f.sale_date else None,
            "fee_type": f.fee_type, "fee_description": f.fee_description,
            "amount": f.amount,
        })
    return {"items": items, "total": total}


@router.get("/reconciliation")
def finance_reconciliation(
    shop_type: str = Query(...),
    shop_id: Optional[int] = Query(None),
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    accessible_shops: Optional[list[int]] = Depends(get_accessible_shop_ids),
    _=Depends(require_module("finance")),
):
    sids = _shop_ids_filter(db, shop_type, shop_id, accessible_shops)
    if not sids:
        return {"missing_in_orders": [], "missing_in_finance": []}

    shops = {s.id: s.name for s in db.query(Shop).filter(Shop.id.in_(sids)).all()}

    missing_in_orders_rows = (
        db.query(FinanceOrderRecord)
        .outerjoin(Order, and_(Order.srid == FinanceOrderRecord.srid,
                               Order.shop_id == FinanceOrderRecord.shop_id))
        .filter(
            Order.id.is_(None),
            FinanceOrderRecord.shop_id.in_(sids),
            FinanceOrderRecord.sale_date.between(date_from, date_to),
        ).all()
    )
    missing_in_orders = [
        {"srid": r.srid, "shop_name": shops.get(r.shop_id, ""),
         "sale_date": r.sale_date.isoformat() if r.sale_date else None,
         "net_to_seller": r.net_to_seller, "currency": r.currency}
        for r in missing_in_orders_rows
    ]

    missing_in_finance_rows = (
        db.query(Order)
        .outerjoin(FinanceOrderRecord, and_(
            FinanceOrderRecord.srid == Order.srid,
            FinanceOrderRecord.shop_id == Order.shop_id))
        .filter(
            FinanceOrderRecord.id.is_(None),
            Order.srid != "",
            Order.shop_id.in_(sids),
            Order.created_at.between(date_from, date_to),
        ).all()
    )
    missing_in_finance = [
        {"wb_order_id": o.wb_order_id, "srid": o.srid,
         "shop_name": shops.get(o.shop_id, ""),
         "created_at": o.created_at.isoformat() if o.created_at else None,
         "total_price": o.total_price}
        for o in missing_in_finance_rows
    ]

    return {"missing_in_orders": missing_in_orders, "missing_in_finance": missing_in_finance}
