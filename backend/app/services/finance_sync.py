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


SALE_OPS = {"Продажа", "销售"}
LOGISTICS_OPS = {"Логистика", "物流"}
RETURN_OPS = {"Возврат", "退货"}


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
        # 跳过没有销售行也没有退货行的 group（纯物流/扣款补差，归到 OtherFee 处理）
        if not any(r.get("supplier_oper_name") in SALE_OPS or r.get("supplier_oper_name") in RETURN_OPS for r in group):
            continue
        # 优先按 supplier_oper_name 找"销售"行；找不到时退而求其次：
        # 选 group 里第一条 quantity > 0 或 retail_amount > 0 的行（避免拿到物流/修正行的 qty=0）
        sale_row = next((r for r in group if r.get("supplier_oper_name") in SALE_OPS), None)
        if sale_row is None:
            sale_row = next(
                (r for r in group if _int(r.get("quantity")) > 0 or _num(r.get("retail_amount")) > 0),
                group[0],
            )
        delivery_fee = sum(_num(r.get("delivery_rub")) for r in group if r.get("supplier_oper_name") in LOGISTICS_OPS)
        fine = sum(_num(r.get("penalty")) for r in group)
        storage = sum(_num(r.get("storage_fee")) for r in group)
        deduction = sum(_num(r.get("deduction")) for r in group)
        returns = [r for r in group if r.get("supplier_oper_name") in RETURN_OPS]
        has_return = bool(returns)
        return_qty = sum(_int(r.get("quantity")) for r in returns)

        # net_to_seller: 销售行 ppvz_for_pay 累加，退货行取负（WB 财报里退货行是正数，语义为"扣回"）
        net_to_seller = sum(
            (-_num(r.get("ppvz_for_pay")) if r.get("supplier_oper_name") in RETURN_OPS else _num(r.get("ppvz_for_pay")))
            for r in group
        )

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
    "Платная приёмка": "storage",
    "Платная приемка": "storage",
    "仓储": "storage",
    "Штраф": "fine",
    "罚款": "fine",
    "Удержания": "deduction",
    "Удержание": "deduction",
    "扣款": "deduction",
    "扣除": "deduction",
    "Логистика": "logistics_adjust",
    "Возмещение издержек по перевозке": "logistics_adjust",
    "Возмещение за выдачу и возврат": "logistics_adjust",
    "物流": "logistics_adjust",
}


def _infer_fee_type(row: dict) -> str:
    op = row.get("supplier_oper_name") or ""
    for key, val in FEE_TYPE_MAP.items():
        if key in op:
            return val
    return "other"


def _fee_amount(row: dict) -> float:
    for field in (
        "penalty", "storage_fee", "deduction", "delivery_rub", "ppvz_for_pay",
        "rebill_logistic_cost", "ppvz_reward", "acceptance",
    ):
        v = _num(row.get(field))
        if v:
            return v
    return 0.0


def extract_other_fees(
    rows: list[dict], *, shop_id: int, currency: str,
    period_start: Optional[date], period_end: Optional[date],
) -> list[dict]:
    """Rows without srid → standalone fee records (one per row).

    有 srid 但 group 里完全没有销售行/退货行的 srid（纯物流/扣款补差，
    通常是上一结算周期已结算订单的费用补算），其每行也作为 OtherFee 抓出来。
    """
    # 找出"纯费用 srid"——和 merge_rows_by_srid 跳过的判断条件保持一致
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        srid = (r.get("srid") or "").strip() if r.get("srid") else ""
        if srid:
            groups[srid].append(r)
    fee_only_srids = {
        srid for srid, group in groups.items()
        if not any(r.get("supplier_oper_name") in SALE_OPS or r.get("supplier_oper_name") in RETURN_OPS for r in group)
    }

    result: list[dict] = []
    for r in rows:
        srid = (r.get("srid") or "").strip() if r.get("srid") else ""
        if srid and srid not in fee_only_srids:
            continue
        result.append({
            "shop_id": shop_id,
            "currency": currency,
            "srid": srid or "",
            "order_date": _parse_date(r.get("order_dt")),
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


_SRID_BATCH_SIZE = 500  # SQLite 默认参数上限是 999，留余量给其他 WHERE 绑定参数


def apply_srid_price_map(db, shop_id: int, srid_to_price: dict[str, float]) -> int:
    """Write srid→price map into Order.price_rub / total_price for zero-price rows.

    Only touches rows where total_price == 0, so it's safe to run multiple times.
    Returns number of orders updated.
    """
    from app.models.order import Order

    if not srid_to_price:
        return 0

    srids = list(srid_to_price)
    updated = 0
    now = datetime.now(timezone.utc)
    for i in range(0, len(srids), _SRID_BATCH_SIZE):
        chunk = srids[i:i + _SRID_BATCH_SIZE]
        zero_orders = db.query(Order).filter(
            Order.shop_id == shop_id,
            Order.total_price == 0,
            Order.srid.in_(chunk),
        ).all()
        for o in zero_orders:
            price = srid_to_price[o.srid]
            o.price_rub = price
            o.total_price = price
            o.updated_at = now
            updated += 1
    return updated


def backfill_order_prices(db, shop_id: int, merged: list[dict]) -> int:
    """Fill Order.price_rub / total_price from merged finance records.

    Marketplace /api/v3/orders often returns salePrice=0 for completed FBS orders;
    the Statistics / Report-Detail fallbacks in sync.py miss orders whose settlement
    week falls outside the orders-sync window. Finance reports always carry the real
    retail_price by srid, so use them as the last-resort price source.
    """
    srid_to_price = {
        r["srid"]: _num(r.get("retail_price"))
        for r in merged
        if r.get("srid") and _num(r.get("retail_price")) > 0
    }
    return apply_srid_price_map(db, shop_id, srid_to_price)


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
        # WB 报告按结算周期返回，可能包含 sale_date 早于本次范围的订单（往期销售本期结算），
        # 所以除了按日期窗口删，还要按本次拿到的 srid 集合删，避免唯一约束冲突。
        new_srids = [r["srid"] for r in merged if r.get("srid")]
        db.query(FinanceOrderRecord).filter(
            FinanceOrderRecord.shop_id == shop.id,
            FinanceOrderRecord.sale_date >= date_from,
            FinanceOrderRecord.sale_date <= date_to,
        ).delete(synchronize_session=False)
        if new_srids:
            db.query(FinanceOrderRecord).filter(
                FinanceOrderRecord.shop_id == shop.id,
                FinanceOrderRecord.srid.in_(new_srids),
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

        backfilled = backfill_order_prices(db, shop.id, merged)
        if backfilled:
            print(f"[FinanceSync] Backfilled Order.price_rub for {backfilled} orders in shop {shop.id}")

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


def sync_shop_all_history(db, shop, *, triggered_by: str, user_id: Optional[int],
                          log_id: Optional[int] = None,
                          window_days: int = 89,
                          max_windows: int = 30,
                          stop_after_empty: int = 2) -> "FinanceSyncLog":
    """Iterate 90-day windows backward from today until WB returns nothing.

    WB 单次 API 上限 90 天，本函数循环最多 max_windows 个窗口，
    遇到连续 stop_after_empty 个空窗口即认为已抵达店铺最早账单。
    所有窗口的拉取/合并/插入都更新到同一个 log（累计计数）。
    """
    from app.models.finance import FinanceOrderRecord, FinanceOtherFee, FinanceSyncLog

    today = date.today()
    if log_id is not None:
        log = db.query(FinanceSyncLog).get(log_id)
    else:
        log = FinanceSyncLog(
            shop_id=shop.id, triggered_by=triggered_by, user_id=user_id,
            date_from=today, date_to=today, status="running",
        )
        db.add(log); db.commit()

    try:
        token = decrypt_token(shop.api_token)
        currency = "CNY" if shop.type == "cross_border" else "RUB"

        cursor_to = today
        empty_streak = 0
        total_rows = 0
        total_orders = 0
        total_fees = 0
        earliest_from = today

        for _ in range(max_windows):
            window_from = cursor_to.fromordinal(max(cursor_to.toordinal() - window_days, 1))
            rows = fetch_finance_report(
                token, window_from.strftime("%Y-%m-%d"), cursor_to.strftime("%Y-%m-%d")
            )

            if not rows:
                empty_streak += 1
                if empty_streak >= stop_after_empty:
                    break
            else:
                empty_streak = 0
                merged = merge_rows_by_srid(
                    rows, shop_id=shop.id, currency=currency,
                    period_start=window_from, period_end=cursor_to,
                )
                fill_purchase_cost_and_profit(merged, db, shop_id=shop.id)
                other_fees = extract_other_fees(
                    rows, shop_id=shop.id, currency=currency,
                    period_start=window_from, period_end=cursor_to,
                )

                new_srids = [r["srid"] for r in merged if r.get("srid")]
                db.query(FinanceOrderRecord).filter(
                    FinanceOrderRecord.shop_id == shop.id,
                    FinanceOrderRecord.sale_date >= window_from,
                    FinanceOrderRecord.sale_date <= cursor_to,
                ).delete(synchronize_session=False)
                if new_srids:
                    db.query(FinanceOrderRecord).filter(
                        FinanceOrderRecord.shop_id == shop.id,
                        FinanceOrderRecord.srid.in_(new_srids),
                    ).delete(synchronize_session=False)
                db.query(FinanceOtherFee).filter(
                    FinanceOtherFee.shop_id == shop.id,
                    FinanceOtherFee.sale_date >= window_from,
                    FinanceOtherFee.sale_date <= cursor_to,
                ).delete(synchronize_session=False)

                for rec in merged:
                    db.add(FinanceOrderRecord(**rec))
                for fee in other_fees:
                    db.add(FinanceOtherFee(**fee))

                backfilled = backfill_order_prices(db, shop.id, merged)
                if backfilled:
                    print(f"[FinanceSync] Backfilled Order.price_rub for {backfilled} orders in shop {shop.id} window {window_from}~{cursor_to}")

                db.commit()

                total_rows += len(rows)
                total_orders += len(merged)
                total_fees += len(other_fees)
                earliest_from = window_from

                # 累计写入 log，方便前端实时显示进度
                log.rows_fetched = total_rows
                log.orders_merged = total_orders
                log.other_fees_count = total_fees
                log.date_from = earliest_from
                db.commit()

            # 下一个窗口起点 = 当前窗口起点前一天
            cursor_to = window_from.fromordinal(window_from.toordinal() - 1)
            if cursor_to.toordinal() <= 1:
                break

        log.status = "success"
        log.date_from = earliest_from
        log.date_to = today
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        log = db.query(FinanceSyncLog).get(log.id)
        log.status = "failed"
        log.error_message = str(e)[:2000]
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
    return log
