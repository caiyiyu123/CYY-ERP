"""Finance module sync service — fetch WB reports, merge by srid, persist.

Layers:
- merge_rows_by_srid   : pure function, row list -> dict list (1 per srid)
- extract_other_fees   : pure function, row list -> dict list (1 per fee row)
- fill_purchase_cost_and_profit : (records, db, shop_id) -> None, mutates in place
- sync_shop            : end-to-end pipeline, calls WB API and persists
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from app.services.wb_api import fetch_finance_report
from app.utils.security import decrypt_token


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


SALE_OPS = {"Продажа"}
LOGISTICS_OPS = {"Логистика"}
RETURN_OPS = {"Возврат"}


def merge_rows_by_srid(
    rows: list[dict], *, shop_id: int, currency: str,
    period_start: Optional[date], period_end: Optional[date],
) -> list[dict]:
    """Merge rows sharing the same srid into one record per srid.

    Row semantics:
      - Sale row (Продажа): primary product info + net_to_seller
      - Logistics row (Логистика): delivery_fee accumulates
      - Return row (Возврат): has_return_row, return_quantity
      - Other (Штраф, Хранение, Удержание with srid): accumulate into fine/storage/deduction
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        srid = (r.get("srid") or "").strip()
        if srid:
            groups[srid].append(r)

    result: list[dict] = []
    for srid, group in groups.items():
        sale_row = next((r for r in group if r.get("supplier_oper_name") in SALE_OPS), group[0])
        delivery_fee = sum(_num(r.get("delivery_rub")) for r in group if r.get("supplier_oper_name") in LOGISTICS_OPS)
        fine = sum(_num(r.get("penalty")) for r in group)
        storage = sum(_num(r.get("storage_fee")) for r in group)
        deduction = sum(_num(r.get("deduction")) for r in group)
        returns = [r for r in group if r.get("supplier_oper_name") in RETURN_OPS]
        has_return = bool(returns)
        return_qty = sum(_int(r.get("quantity")) for r in returns)

        # net_to_seller: sales + return negatives (if any)
        net_to_seller = sum(_num(r.get("ppvz_for_pay")) for r in group)

        rec = {
            "shop_id": shop_id,
            "srid": srid,
            "currency": currency,
            "order_date": _parse_date(sale_row.get("order_dt")),
            "sale_date": _parse_date(sale_row.get("sale_dt") or sale_row.get("rr_dt")),
            "report_period_start": period_start,
            "report_period_end": period_end,
            "nm_id": str(sale_row.get("nm_id") or ""),
            "shop_sku": sale_row.get("sa_name") or "",
            "product_name": "",  # set below
            "barcode": sale_row.get("barcode") or "",
            "category": sale_row.get("subject_name") or "",
            "size": sale_row.get("ts_name") or "",
            "quantity": _int(sale_row.get("quantity")),
            "return_quantity": return_qty,
            "retail_price": _num(sale_row.get("retail_price")),
            "sold_price": _num(sale_row.get("retail_amount")),
            "commission_rate": _num(sale_row.get("commission_percent")),
            "commission_amount": _num(sale_row.get("ppvz_vw")) + _num(sale_row.get("ppvz_vw_nds")),
            "net_to_seller": net_to_seller,
            "delivery_fee": delivery_fee,
            "fine": fine,
            "storage_fee": storage,
            "deduction": deduction,
            "purchase_cost": 0.0,
            "net_profit": 0.0,
            "has_sku_mapping": False,
            "warehouse": sale_row.get("office_name") or "",
            "country": sale_row.get("site_country") or "",
            "sale_type": sale_row.get("srv_dbs") or "",
            "has_return_row": has_return,
        }
        # product_name: WB 财报没有单独字段，用 subject_name + sa_name fallback
        rec["product_name"] = sale_row.get("brand_name") or sale_row.get("subject_name") or ""
        result.append(rec)
    return result


FEE_TYPE_MAP = {
    "Хранение": "storage",
    "Штраф": "fine",
    "Удержания": "deduction",
    "Удержание": "deduction",
    "Логистика": "logistics_adjust",
}


def _infer_fee_type(row: dict) -> str:
    op = row.get("supplier_oper_name") or ""
    for key, val in FEE_TYPE_MAP.items():
        if key in op:
            return val
    return "other"


def _fee_amount(row: dict) -> float:
    for field in ("penalty", "storage_fee", "deduction", "delivery_rub", "ppvz_for_pay"):
        v = _num(row.get(field))
        if v:
            return v
    return 0.0


def extract_other_fees(
    rows: list[dict], *, shop_id: int, currency: str,
    period_start: Optional[date], period_end: Optional[date],
) -> list[dict]:
    """Rows without srid → standalone fee records (one per row)."""
    result: list[dict] = []
    for r in rows:
        srid = (r.get("srid") or "").strip() if r.get("srid") else ""
        if srid:
            continue
        result.append({
            "shop_id": shop_id,
            "currency": currency,
            "sale_date": _parse_date(r.get("sale_dt") or r.get("rr_dt")),
            "report_period_start": period_start,
            "report_period_end": period_end,
            "fee_type": _infer_fee_type(r),
            "fee_description": r.get("supplier_oper_name") or "",
            "amount": _fee_amount(r),
            "raw_row": r,
        })
    return result


def fill_purchase_cost_and_profit(records: list[dict], db, shop_id: int) -> None:
    """Mutate records in place: set purchase_cost, has_sku_mapping, net_profit.

    Lookup via SkuMapping(shop_id, shop_sku) -> Product.purchase_price.
    Missing mapping or NULL product_id → purchase_cost=0, has_sku_mapping=False.
    """
    from app.models.product import SkuMapping, Product

    skus = {r["shop_sku"] for r in records if r.get("shop_sku")}
    if skus:
        rows = (
            db.query(SkuMapping.shop_sku, Product.purchase_price)
            .outerjoin(Product, Product.id == SkuMapping.product_id)
            .filter(SkuMapping.shop_id == shop_id, SkuMapping.shop_sku.in_(skus))
            .all()
        )
        price_map = {sku: (price or 0) for sku, price in rows if price is not None}
    else:
        price_map = {}

    for r in records:
        sku = r.get("shop_sku") or ""
        qty = r.get("quantity", 0)
        price = price_map.get(sku)
        if price is not None and price > 0:
            r["purchase_cost"] = price * qty
            r["has_sku_mapping"] = True
        else:
            r["purchase_cost"] = 0.0
            r["has_sku_mapping"] = False
        r["net_profit"] = (
            r.get("net_to_seller", 0)
            - r.get("delivery_fee", 0)
            - r.get("fine", 0)
            - r.get("storage_fee", 0)
            - r.get("deduction", 0)
            - r["purchase_cost"]
        )


def sync_shop(db, shop, *, date_from: date, date_to: date,
              triggered_by: str, user_id: Optional[int],
              log_id: Optional[int] = None) -> "FinanceSyncLog":
    """Full pipeline for one shop. Returns the FinanceSyncLog row.

    If log_id is provided, updates that existing log (created by the caller,
    typically the /sync router so it can return the id immediately). Otherwise
    creates a new running log.
    """
    from app.models.finance import FinanceOrderRecord, FinanceOtherFee, FinanceSyncLog

    if log_id is not None:
        log = db.query(FinanceSyncLog).get(log_id)
    else:
        log = FinanceSyncLog(
            shop_id=shop.id, triggered_by=triggered_by, user_id=user_id,
            date_from=date_from, date_to=date_to, status="running",
        )
        db.add(log); db.commit()

    try:
        token = decrypt_token(shop.api_token)
        rows = fetch_finance_report(
            token, date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")
        )
        currency = "CNY" if shop.type == "cross_border" else "RUB"

        merged = merge_rows_by_srid(
            rows, shop_id=shop.id, currency=currency,
            period_start=date_from, period_end=date_to,
        )
        fill_purchase_cost_and_profit(merged, db, shop_id=shop.id)

        other_fees = extract_other_fees(
            rows, shop_id=shop.id, currency=currency,
            period_start=date_from, period_end=date_to,
        )

        # Idempotent: delete existing rows within the date window, then insert.
        # Both deletes and inserts share one transaction; rollback on any error.
        db.query(FinanceOrderRecord).filter(
            FinanceOrderRecord.shop_id == shop.id,
            FinanceOrderRecord.sale_date >= date_from,
            FinanceOrderRecord.sale_date <= date_to,
        ).delete(synchronize_session=False)
        db.query(FinanceOtherFee).filter(
            FinanceOtherFee.shop_id == shop.id,
            FinanceOtherFee.sale_date >= date_from,
            FinanceOtherFee.sale_date <= date_to,
        ).delete(synchronize_session=False)

        for rec in merged:
            db.add(FinanceOrderRecord(**rec))
        for fee in other_fees:
            db.add(FinanceOtherFee(**fee))

        log.status = "success"
        log.rows_fetched = len(rows)
        log.orders_merged = len(merged)
        log.other_fees_count = len(other_fees)
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        # rollback may detach `log`; re-fetch to ensure attached state.
        log = db.query(FinanceSyncLog).get(log.id)
        log.status = "failed"
        log.error_message = str(e)[:2000]
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
    return log
