from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.ad import AdCampaign, AdDailyStat
from app.models.order import OrderItem
from app.schemas.ad import (
    AdOverview, AdCampaignWithStats, AdDailyStatOut, AdProductStats,
)
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/ads", tags=["ads"])


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
    _=Depends(get_current_user),
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
    if shop_id:
        query = query.filter(AdCampaign.shop_id == shop_id)
    row = query.one()
    total_spend = float(row[0])
    total_order_amount = float(row[4])
    roas = round(total_order_amount / total_spend, 2) if total_spend > 0 else 0.0
    return AdOverview(
        total_spend=total_spend,
        total_views=int(row[1]),
        total_clicks=int(row[2]),
        total_orders=int(row[3]),
        total_order_amount=total_order_amount,
        roas=roas,
    )


@router.get("/campaigns", response_model=list[AdCampaignWithStats])
def ads_campaigns(
    shop_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    date_from, date_to = _default_dates(date_from, date_to)
    q = db.query(AdCampaign)
    if shop_id:
        q = q.filter(AdCampaign.shop_id == shop_id)
    if status is not None:
        q = q.filter(AdCampaign.status == status)
    campaigns = q.order_by(AdCampaign.status.asc(), AdCampaign.updated_at.desc()).all()

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
    _=Depends(get_current_user),
):
    date_from, date_to = _default_dates(date_from, date_to)
    stats = db.query(AdDailyStat).filter(
        AdDailyStat.campaign_id == campaign_id,
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
    ).order_by(AdDailyStat.date.desc(), AdDailyStat.nm_id).all()
    return stats


@router.get("/product-stats", response_model=list[AdProductStats])
def ads_product_stats(
    shop_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    date_from, date_to = _default_dates(date_from, date_to)
    query = db.query(
        AdDailyStat.nm_id,
        func.sum(AdDailyStat.spend),
        func.sum(AdDailyStat.views),
        func.sum(AdDailyStat.clicks),
        func.sum(AdDailyStat.orders),
        func.sum(AdDailyStat.order_amount),
    ).join(AdCampaign).filter(
        AdDailyStat.date >= date_from,
        AdDailyStat.date <= date_to,
    )
    if shop_id:
        query = query.filter(AdCampaign.shop_id == shop_id)
    rows = query.group_by(AdDailyStat.nm_id).all()

    nm_ids = [str(row[0]) for row in rows]
    items = db.query(OrderItem).filter(OrderItem.wb_product_id.in_(nm_ids)).all()
    nm_info = {}
    for item in items:
        if item.wb_product_id not in nm_info:
            nm_info[item.wb_product_id] = {
                "product_name": item.product_name,
                "sku": item.sku,
                "image_url": item.image_url,
            }

    result = []
    for row in rows:
        nm_id = row[0]
        spend = float(row[1] or 0)
        order_amt = float(row[5] or 0)
        info = nm_info.get(str(nm_id), {})
        result.append(AdProductStats(
            nm_id=nm_id,
            product_name=info.get("product_name", ""),
            sku=info.get("sku", ""),
            image_url=info.get("image_url", ""),
            total_spend=spend,
            total_views=int(row[2] or 0),
            total_clicks=int(row[3] or 0),
            total_orders=int(row[4] or 0),
            total_order_amount=order_amt,
            roas=round(order_amt / spend, 2) if spend > 0 else 0.0,
        ))
    result.sort(key=lambda x: x.total_spend, reverse=True)
    return result
