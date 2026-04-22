from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date, timedelta

from app.database import SessionLocal
from app.models.shop import Shop
from app.services.sync import sync_shop_orders, sync_shop_inventory, sync_shop_ads, sync_shop_products
from app.services.backfill import backfill_tick
from app.config import SYNC_INTERVAL_MINUTES

scheduler = BackgroundScheduler()


def sync_all_shops():
    db = SessionLocal()
    try:
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        for shop in shops:
            try:
                cards = sync_shop_orders(db, shop)
                sync_shop_inventory(db, shop)
                sync_shop_ads(db, shop, cards=cards)
                sync_shop_products(db, shop, cards=cards)
                print(f"[Scheduler] Synced shop: {shop.name}")
            except Exception as e:
                print(f"[Scheduler] Error syncing shop {shop.name}: {e}")
    finally:
        db.close()


def weekly_finance_sync():
    """Cron job: every Monday 03:00 Moscow, sync last week (Mon..Sun) for all active shops."""
    from app.services.finance_sync import sync_shop

    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    db = SessionLocal()
    try:
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        for shop in shops:
            try:
                sync_shop(db, shop, date_from=last_monday, date_to=last_sunday,
                          triggered_by="cron", user_id=None)
                print(f"[Finance] Weekly sync done: {shop.name}")
            except Exception as e:
                print(f"[Finance] Weekly sync failed for {shop.name}: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(sync_all_shops, "interval", minutes=SYNC_INTERVAL_MINUTES, id="sync_all")
    scheduler.add_job(
        weekly_finance_sync,
        "cron",
        day_of_week="mon",
        hour=3,
        minute=0,
        timezone="Europe/Moscow",
        id="weekly_finance_sync",
        replace_existing=True,
    )
    # 每小时慢速回溯一个窗口（订单 30 天 + 财报 89 天），最多回溯 2 年。
    # 错开整点 15 分启动，避开常规 sync_all 的高频区。
    scheduler.add_job(
        backfill_tick,
        "cron",
        minute=15,
        id="backfill_tick",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[Scheduler] Started — sync every {SYNC_INTERVAL_MINUTES} min, backfill hourly at :15")


def stop_scheduler():
    scheduler.shutdown(wait=False)
