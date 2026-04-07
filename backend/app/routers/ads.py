import threading
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, SessionLocal
from app.models.ad import AdCampaign, AdDailyStat
from app.models.order import Order, OrderItem
from app.models.shop import Shop
from app.schemas.ad import (
    AdOverview, AdCampaignWithStats, AdDailyStatOut, AdProductStats,
)
from app.utils.deps import get_current_user, get_accessible_shop_ids, require_module, require_role

router = APIRouter(prefix="/api/ads", tags=["ads"])

_ad_sync_status = {"status": "idle"}
_ad_sync_lock = threading.Lock()


def _run_ad_sync():
    db = SessionLocal()
    try:
        from app.services.sync import sync_shop_ads
        from app.services.wb_api import fetch_cards
        from app.utils.security import decrypt_token
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        synced = 0
        for shop in shops:
            api_token = decrypt_token(shop.api_token)
            cards = fetch_cards(api_token)
            sync_shop_ads(db, shop, cards=cards)
            synced += 1
        with _ad_sync_lock:
            _ad_sync_status["status"] = "done"
            _ad_sync_status["detail"] = f"已同步 {synced}/{len(shops)} 个店铺的广告"
    except Exception as e:
        with _ad_sync_lock:
            _ad_sync_status["status"] = "error"
            _ad_sync_status["detail"] = str(e)
    finally:
        db.close()


@router.post("/sync")
def trigger_ad_sync(_=Depends(require_role("admin", "operator"))):
    with _ad_sync_lock:
        if _ad_sync_status["status"] == "running":
            return {"detail": "广告同步正在进行中"}
        _ad_sync_status["status"] = "running"
        _ad_sync_status["detail"] = ""
    thread = threading.Thread(target=_run_ad_sync, daemon=True)
    thread.start()
    return {"detail": "广告同步已开始"}


@router.get("/sync/status")
def ad_sync_status(_=Depends(require_role("admin", "operator"))):
    with _ad_sync_lock:
        return dict(_ad_sync_status)


def _default_dates(date_from: Optional[date], date_to: Optional[date]):
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=6)
    return date_from, date_to


@router.get("/overview", response_model=AdOverview)
def ads_overview(
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _perm=Depends(require_module("ads")),
):
    date_from, date_to = _default_dates(date_from, date_to)
    query = db.query(
        func.coalesce(func.sum(AdDailyStat.spend), 0),
        func.coalesce(func.sum(AdDailyStat.views), 0),
        func.coalesce(func.sum(AdDailyStat.clicks), 0),
        func.coalesce(func.sum(AdDailyStat.orders), 0),
        func.coalesce(func.sum(AdDailyStat.order_amount), 0),
    ).join(AdCampaign).filter(
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
    )
    if accessible_shops is not None:
        query = query.filter(AdCampaign.shop_id.in_(accessible_shops))
    if shop_id:
        query = query.filter(AdCampaign.shop_id == shop_id)
    row = query.one()
    total_spend = float(row[0])
    total_order_amount = float(row[4])
    roas = round(total_order_amount / total_spend, 2) if total_spend > 0 else 0.0

    # Query total order amount in RUB — convert date range to UTC (ad dates are Moscow UTC+3)
    msk = timezone(timedelta(hours=3))
    utc_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=msk).astimezone(timezone.utc).replace(tzinfo=None)
    utc_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=msk).astimezone(timezone.utc).replace(tzinfo=None)
    order_q = db.query(
        func.count(Order.id),
        func.coalesce(func.sum(Order.price_rub), 0),
    ).filter(
        Order.created_at >= utc_from,
        Order.created_at <= utc_to,
    )
    if accessible_shops is not None:
        order_q = order_q.filter(Order.shop_id.in_(accessible_shops))
    if shop_id:
        order_q = order_q.filter(Order.shop_id == shop_id)
    order_row = order_q.one()
    overall_orders = int(order_row[0])
    overall_order_amount = float(order_row[1])
    overall_roas = round(overall_order_amount / total_spend, 2) if total_spend > 0 else 0.0

    return AdOverview(
        total_spend=total_spend,
        total_views=int(row[1]),
        total_clicks=int(row[2]),
        total_orders=int(row[3]),
        total_order_amount=total_order_amount,
        roas=roas,
        overall_orders=overall_orders,
        overall_order_amount=overall_order_amount,
        overall_roas=overall_roas,
    )


@router.get("/campaigns", response_model=list[AdCampaignWithStats])
def ads_campaigns(
    shop_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _perm=Depends(require_module("ads")),
):
    date_from, date_to = _default_dates(date_from, date_to)
    q = db.query(AdCampaign)
    if accessible_shops is not None:
        q = q.filter(AdCampaign.shop_id.in_(accessible_shops))
    if shop_id:
        q = q.filter(AdCampaign.shop_id == shop_id)
    if status is not None:
        if status == 9:
            # "已暂停" includes both paused (9) and archived (11)
            q = q.filter(AdCampaign.status.in_([9, 11]))
        else:
            q = q.filter(AdCampaign.status == status)
    campaigns = q.order_by(AdCampaign.create_time.desc()).all()

    stats_q = db.query(
        AdDailyStat.campaign_id,
        func.sum(AdDailyStat.spend),
        func.sum(AdDailyStat.views),
        func.sum(AdDailyStat.clicks),
        func.sum(AdDailyStat.orders),
        func.sum(AdDailyStat.order_amount),
    ).filter(
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
    ).group_by(AdDailyStat.campaign_id).all()

    stats_map = {}
    for row in stats_q:
        spend = float(row[1] or 0)
        order_amt = float(row[5] or 0)
        stats_map[row[0]] = {
            "total_spend": spend,
            "total_views": int(row[2] or 0),
            "total_clicks": int(row[3] or 0),
            "total_orders": int(row[4] or 0),
            "total_order_amount": order_amt,
            "roas": round(order_amt / spend, 2) if spend > 0 else 0.0,
        }

    result = []
    for c in campaigns:
        s = stats_map.get(c.id, {})
        result.append(AdCampaignWithStats(
            id=c.id, shop_id=c.shop_id, wb_advert_id=c.wb_advert_id,
            name=c.name, type=c.type, status=c.status,
            daily_budget=c.daily_budget, create_time=c.create_time,
            updated_at=c.updated_at, **s,
        ))
    return result


@router.get("/campaigns/{campaign_id}/stats", response_model=list[AdDailyStatOut])
def campaign_stats(
    campaign_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _perm=Depends(require_module("ads")),
):
    date_from, date_to = _default_dates(date_from, date_to)
    stats = db.query(AdDailyStat).filter(
        AdDailyStat.campaign_id == campaign_id,
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
    ).order_by(AdDailyStat.date.desc(), AdDailyStat.nm_id).all()
    return stats


@router.get("/product-campaigns/{nm_id}")
def product_campaigns(
    nm_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: list[int] | None = Depends(get_accessible_shop_ids),
    _perm=Depends(require_module("ads")),
):
    """Get campaigns associated with a product (nm_id) and their stats in date range."""
    date_from, date_to = _default_dates(date_from, date_to)
    # Find campaigns that have stats for this nm_id
    rows = db.query(
        AdCampaign.id,
        AdCampaign.wb_advert_id,
        AdCampaign.name,
        AdCampaign.status,
        func.sum(AdDailyStat.spend),
        func.sum(AdDailyStat.views),
        func.sum(AdDailyStat.clicks),
        func.sum(AdDailyStat.orders),
        func.sum(AdDailyStat.order_amount),
    ).join(AdDailyStat).filter(
        AdDailyStat.nm_id == nm_id,
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
    )
    if accessible_shops is not None:
        rows = rows.filter(AdCampaign.shop_id.in_(accessible_shops))
    rows = rows.group_by(AdCampaign.id).all()

    result = []
    for r in rows:
        spend = float(r[4] or 0)
        views = int(r[5] or 0)
        # Skip campaigns with no actual activity for this product
        if spend == 0 and views == 0:
            continue
        order_amt = float(r[8] or 0)
        result.append({
            "campaign_id": r[0],
            "wb_advert_id": r[1],
            "name": r[2],
            "status": r[3],
            "spend": spend,
            "views": views,
            "clicks": int(r[6] or 0),
            "orders": int(r[7] or 0),
            "order_amount": order_amt,
            "roas": round(order_amt / spend, 2) if spend > 0 else 0.0,
        })
    result.sort(key=lambda x: x["spend"], reverse=True)
    return result


@router.get("/product-stats", response_model=list[AdProductStats])
def ads_product_stats(
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _perm=Depends(require_module("ads")),
):
    """Product stats: show shop products with their ad performance."""
    date_from, date_to = _default_dates(date_from, date_to)

    def _wb_image_url(nm_id_str: str) -> str:
        """Generate WB product image URL from nm_id using standard basket mapping."""
        if not nm_id_str.isdigit():
            return ""
        nm = int(nm_id_str)
        vol = nm // 100000
        part = nm // 1000
        # WB basket number mapping (vol → basket), derived from real CDN data
        _BASKET_RANGES = [
            (143, 1), (287, 2), (431, 3), (719, 4), (1007, 5),
            (1061, 6), (1115, 7), (1169, 8), (1313, 9), (1601, 10),
            (1655, 11), (1919, 12), (2045, 13), (2189, 14), (2405, 15),
            (2621, 16), (2837, 17), (3053, 18), (3269, 19), (3485, 20),
            (3701, 21), (3917, 22), (4133, 23), (4349, 24), (4565, 25),
            (4781, 26), (5213, 27), (5645, 28), (6077, 29), (6509, 30),
            (6941, 31), (7373, 32), (7805, 33), (8237, 34), (8669, 35),
            (9101, 36), (9533, 37), (9965, 38), (10397, 39), (10829, 40),
        ]
        basket = 41  # default for very high vol
        for max_vol, b in _BASKET_RANGES:
            if vol <= max_vol:
                basket = b
                break
        return f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm}/images/c246x328/1.webp"

    # Step 1: Get active products — those with orders in the last 90 days
    msk = timezone(timedelta(hours=3))
    cutoff_90d = datetime.now(msk) - timedelta(days=90)
    cutoff_utc = cutoff_90d.astimezone(timezone.utc).replace(tzinfo=None)
    product_q = db.query(
        OrderItem.wb_product_id,
        OrderItem.product_name,
        OrderItem.sku,
        OrderItem.image_url,
    ).join(Order).filter(Order.created_at >= cutoff_utc)
    if accessible_shops is not None:
        product_q = product_q.filter(Order.shop_id.in_(accessible_shops))
    if shop_id:
        product_q = product_q.filter(Order.shop_id == shop_id)
    product_q = product_q.group_by(OrderItem.wb_product_id, OrderItem.product_name, OrderItem.sku, OrderItem.image_url)
    all_products = product_q.all()

    # Build product info map: nm_id → {name, sku, image}
    # Skip products where product_name equals sku (means card was not found — likely in recycle bin)
    product_map = {}
    for p in all_products:
        if not p.wb_product_id or p.wb_product_id in product_map:
            continue
        if p.product_name and p.sku and p.product_name == p.sku:
            continue  # Recycled product: name was never resolved from cards API
        product_map[p.wb_product_id] = {
            "product_name": p.product_name or "",
            "sku": p.sku or "",
            "image_url": p.image_url or _wb_image_url(p.wb_product_id),
        }

    nm_ids = list(product_map.keys())

    # Step 2: Get ad stats for these products in the date range
    ad_q = db.query(
        AdDailyStat.nm_id,
        func.sum(AdDailyStat.spend),
        func.sum(AdDailyStat.views),
        func.sum(AdDailyStat.clicks),
        func.sum(AdDailyStat.orders),
        func.sum(AdDailyStat.order_amount),
    ).join(AdCampaign).filter(
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
        AdDailyStat.nm_id.in_([int(n) for n in nm_ids if n.isdigit()]),
    )
    if accessible_shops is not None:
        ad_q = ad_q.filter(AdCampaign.shop_id.in_(accessible_shops))
    if shop_id:
        ad_q = ad_q.filter(AdCampaign.shop_id == shop_id)
    ad_rows = ad_q.group_by(AdDailyStat.nm_id).all()
    ad_stats = {}
    for row in ad_rows:
        ad_stats[str(row[0])] = {
            "spend": float(row[1] or 0),
            "views": int(row[2] or 0),
            "clicks": int(row[3] or 0),
            "orders": int(row[4] or 0),
            "order_amount": float(row[5] or 0),
        }

    # Step 3: Get total RUB sales per product in date range
    msk = timezone(timedelta(hours=3))
    utc_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=msk).astimezone(timezone.utc).replace(tzinfo=None)
    utc_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=msk).astimezone(timezone.utc).replace(tzinfo=None)
    rub_q = db.query(
        OrderItem.wb_product_id,
        func.count(Order.id),
        func.coalesce(func.sum(Order.price_rub), 0),
    ).join(Order).filter(
        Order.created_at >= utc_from,
        Order.created_at <= utc_to,
        OrderItem.wb_product_id.in_(nm_ids),
    )
    if accessible_shops is not None:
        rub_q = rub_q.filter(Order.shop_id.in_(accessible_shops))
    if shop_id:
        rub_q = rub_q.filter(Order.shop_id == shop_id)
    rub_rows = rub_q.group_by(OrderItem.wb_product_id).all()
    rub_by_nm = {str(r[0]): {"orders": int(r[1]), "amount": float(r[2])} for r in rub_rows}

    # Step 4: Build result — only products with ad data or orders in date range
    result = []
    for nm_id, info in product_map.items():
        ad = ad_stats.get(nm_id, {})
        spend = ad.get("spend", 0.0)
        order_amt = ad.get("order_amount", 0.0)
        rub_data = rub_by_nm.get(nm_id, {"orders": 0, "amount": 0.0})
        result.append(AdProductStats(
            nm_id=int(nm_id) if nm_id.isdigit() else 0,
            product_name=info["product_name"],
            sku=info["sku"],
            image_url=info["image_url"],
            total_spend=spend,
            total_views=ad.get("views", 0),
            total_clicks=ad.get("clicks", 0),
            total_orders=ad.get("orders", 0),
            total_order_amount=order_amt,
            roas=round(order_amt / spend, 2) if spend > 0 else 0.0,
            overall_orders=rub_data["orders"],
            overall_order_amount=rub_data["amount"],
            overall_roas=round(rub_data["amount"] / spend, 2) if spend > 0 else 0.0,
        ))
    result.sort(key=lambda x: x.total_spend, reverse=True)
    return result
