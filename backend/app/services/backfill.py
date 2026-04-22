"""Background slow backfill of historical orders and finance reports.

Each tick advances every active shop by ONE window backward until hitting the
2-year limit. Runs once per hour to spread load and avoid WB API rate limits.

Cursors live on Shop:
  - orders_backfill_cursor    : earliest date already synced (exclusive upper bound
                                of the next window)
  - finance_backfill_cursor   : same, for finance reports

NULL cursor → start from today - 90 days (日常同步已覆盖最近 90 天，再往前才是回溯区间)
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.shop import Shop
from app.services.sync import sync_shop_orders
from app.services.finance_sync import sync_shop as sync_shop_finance

MAX_BACKFILL_DAYS = 730       # 2 年
ORDERS_WINDOW_DAYS = 30
FINANCE_WINDOW_DAYS = 89
DAILY_SYNC_COVERAGE_DAYS = 90 # 日常同步已覆盖的窗口；回溯从这里之前开始


def _advance_orders(db, shop: Shop, today: date) -> str:
    """Advance orders backfill by one window. Returns status."""
    limit = today - timedelta(days=MAX_BACKFILL_DAYS)
    cursor = shop.orders_backfill_cursor or (today - timedelta(days=DAILY_SYNC_COVERAGE_DAYS))
    if cursor <= limit:
        return "done"

    window_to = cursor
    window_from = max(window_to - timedelta(days=ORDERS_WINDOW_DAYS), limit)
    dt_from = datetime.combine(window_from, datetime.min.time(), tzinfo=timezone.utc)
    dt_to = datetime.combine(window_to, datetime.min.time(), tzinfo=timezone.utc)

    try:
        sync_shop_orders(db, shop, date_from=dt_from, date_to=dt_to, backfill=True)
    except Exception as e:
        print(f"[Backfill] orders shop={shop.name} {window_from}~{window_to}: {e}")
        return "error"

    shop.orders_backfill_cursor = window_from
    db.commit()
    return f"{window_from}~{window_to}"


def _advance_finance(db, shop: Shop, today: date) -> str:
    """Advance finance backfill by one 89-day window."""
    limit = today - timedelta(days=MAX_BACKFILL_DAYS)
    cursor = shop.finance_backfill_cursor or (today - timedelta(days=DAILY_SYNC_COVERAGE_DAYS))
    if cursor <= limit:
        return "done"

    window_to = cursor
    window_from = max(window_to - timedelta(days=FINANCE_WINDOW_DAYS), limit)

    try:
        sync_shop_finance(db, shop, date_from=window_from, date_to=window_to,
                          triggered_by="backfill", user_id=None)
    except Exception as e:
        print(f"[Backfill] finance shop={shop.name} {window_from}~{window_to}: {e}")
        return "error"

    shop.finance_backfill_cursor = window_from
    db.commit()
    return f"{window_from}~{window_to}"


def backfill_tick():
    """Hourly entry point: advance one window per shop for both orders and finance."""
    today = date.today()
    db = SessionLocal()
    try:
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        for shop in shops:
            o = _advance_orders(db, shop, today)
            f = _advance_finance(db, shop, today)
            print(f"[Backfill] shop={shop.name} orders={o} finance={f}")
    finally:
        db.close()
