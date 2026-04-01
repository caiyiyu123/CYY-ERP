# 推广数据模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WB advertising data sync and ROAS analytics to 韬盛ERP, with campaign-level and product-level views.

**Architecture:** New `ad_campaigns` and `ad_daily_stats` database tables, synced from WB Advert API (`advert-api.wildberries.ru`) on the existing 30-min scheduler. Four new API endpoints serve overview, campaign list, campaign detail, and product-level stats. Two new Vue pages (AdsOverview + AdDetail) added under "商品管理" submenu.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, httpx, Vue 3 Composition API, Element Plus, ECharts (vue-echarts)

---

### Task 1: Backend — Ad Data Models

**Files:**
- Create: `backend/app/models/ad.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the ad models file**

Create `backend/app/models/ad.py`:

```python
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(Integer, ForeignKey("shops.id"))
    wb_advert_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), default="")
    type: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=0)
    daily_budget: Mapped[float] = mapped_column(Float, default=0.0)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    daily_stats: Mapped[list["AdDailyStat"]] = relationship(back_populates="campaign", lazy="select")


class AdDailyStat(Base):
    __tablename__ = "ad_daily_stats"
    __table_args__ = (
        UniqueConstraint("campaign_id", "nm_id", "date", name="uq_campaign_nm_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_campaigns.id"))
    nm_id: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(Date)
    views: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cpc: Mapped[float] = mapped_column(Float, default=0.0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    order_amount: Mapped[float] = mapped_column(Float, default=0.0)
    atbs: Mapped[int] = mapped_column(Integer, default=0)
    cr: Mapped[float] = mapped_column(Float, default=0.0)
    campaign: Mapped["AdCampaign"] = relationship(back_populates="daily_stats")
```

- [ ] **Step 2: Register models in __init__.py**

Edit `backend/app/models/__init__.py` — add two lines:

```python
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product, SkuMapping
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory
from app.models.ad import AdCampaign, AdDailyStat

__all__ = ["User", "Shop", "Product", "SkuMapping", "Order", "OrderItem", "OrderStatusLog", "Inventory", "AdCampaign", "AdDailyStat"]
```

- [ ] **Step 3: Verify tables can be created**

Run:
```bash
cd backend && python -c "from app.database import Base, engine; import app.models; Base.metadata.create_all(bind=engine); print('Tables created OK')"
```
Expected: `Tables created OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/ad.py backend/app/models/__init__.py
git commit -m "feat(ads): add AdCampaign and AdDailyStat data models"
```

---

### Task 2: Backend — Ad Schemas

**Files:**
- Create: `backend/app/schemas/ad.py`

- [ ] **Step 1: Create the schemas file**

Create `backend/app/schemas/ad.py`:

```python
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


class AdCampaignOut(BaseModel):
    id: int
    shop_id: int
    wb_advert_id: int
    name: str
    type: int
    status: int
    daily_budget: float
    create_time: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class AdCampaignWithStats(AdCampaignOut):
    """Campaign with aggregated stats for a date range."""
    total_spend: float = 0.0
    total_views: int = 0
    total_clicks: int = 0
    total_orders: int = 0
    total_order_amount: float = 0.0
    roas: float = 0.0


class AdDailyStatOut(BaseModel):
    id: int
    campaign_id: int
    nm_id: int
    date: date
    views: int
    clicks: int
    ctr: float
    cpc: float
    spend: float
    orders: int
    order_amount: float
    atbs: int
    cr: float

    class Config:
        from_attributes = True


class AdOverview(BaseModel):
    total_spend: float = 0.0
    total_views: int = 0
    total_clicks: int = 0
    total_orders: int = 0
    total_order_amount: float = 0.0
    roas: float = 0.0


class AdProductStats(BaseModel):
    nm_id: int
    product_name: str = ""
    sku: str = ""
    image_url: str = ""
    total_spend: float = 0.0
    total_views: int = 0
    total_clicks: int = 0
    total_orders: int = 0
    total_order_amount: float = 0.0
    roas: float = 0.0
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/ad.py
git commit -m "feat(ads): add Pydantic schemas for ad endpoints"
```

---

### Task 3: Backend — WB Advert API Client Functions

**Files:**
- Modify: `backend/app/services/wb_api.py`

- [ ] **Step 1: Add ADVERT_API constant and three new functions**

Append to `backend/app/services/wb_api.py` — first add the constant near the top (after line 8, after `STATISTICS_API`):

```python
ADVERT_API = "https://advert-api.wildberries.ru"
```

Then append these three functions at the end of the file:

```python
def fetch_ad_campaign_ids(api_token: str) -> list[int]:
    """GET /adv/v1/promotion/count — get all campaign IDs across all statuses."""
    url = f"{ADVERT_API}/adv/v1/promotion/count"
    try:
        _throttle()
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=_headers(api_token))
            resp.raise_for_status()
            data = resp.json()
            # Response: {"adverts": [{"type": 5, "status": 7, "count": 2, "advert_list": [{"advertId": 123, ...}]}, ...]}
            all_ids = []
            for group in data.get("adverts", []):
                for item in group.get("advert_list", []):
                    advert_id = item.get("advertId")
                    if advert_id:
                        all_ids.append(advert_id)
            return all_ids
    except Exception as e:
        print(f"[WB API] Error fetching ad campaign IDs: {e}")
        return []


def fetch_ad_details(api_token: str, advert_ids: list[int]) -> list[dict]:
    """POST /adv/v1/promotion/adverts — batch fetch campaign details.

    Request body: list of advert IDs (max 50 per request).
    Response: list of campaign objects with name, type, status, dailyBudget, createTime, etc.
    """
    if not advert_ids:
        return []

    url = f"{ADVERT_API}/adv/v1/promotion/adverts"
    all_details = []

    try:
        with httpx.Client(timeout=30) as client:
            for i in range(0, len(advert_ids), 50):
                batch = advert_ids[i:i + 50]
                _throttle()
                resp = client.post(url, headers=_headers(api_token), json=batch)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    all_details.extend(data)
    except Exception as e:
        print(f"[WB API] Error fetching ad details: {e}")

    return all_details


def fetch_ad_fullstats(api_token: str, campaign_ids: list[int], date_from: str, date_to: str) -> list[dict]:
    """POST /adv/v2/fullstats — fetch daily stats per campaign per nmId.

    Args:
        campaign_ids: List of WB advert IDs.
        date_from: Start date as 'YYYY-MM-DD'.
        date_to: End date as 'YYYY-MM-DD'.

    Request body: [{"id": advertId, "interval": {"begin": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}]
    Response: list of objects with advertId, days[{date, apps[{nmId, views, clicks, sum, orders, ...}]}]
    """
    if not campaign_ids:
        return []

    url = f"{ADVERT_API}/adv/v2/fullstats"
    all_stats = []

    try:
        with httpx.Client(timeout=60) as client:
            # Process in batches of 100
            for i in range(0, len(campaign_ids), 100):
                batch = campaign_ids[i:i + 100]
                payload = [
                    {"id": cid, "interval": {"begin": date_from, "end": date_to}}
                    for cid in batch
                ]
                _throttle()
                resp = client.post(url, headers=_headers(api_token), json=payload)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    all_stats.extend(data)
    except Exception as e:
        print(f"[WB API] Error fetching ad fullstats: {e}")

    return all_stats
```

- [ ] **Step 2: Verify imports work**

Run:
```bash
cd backend && python -c "from app.services.wb_api import fetch_ad_campaign_ids, fetch_ad_details, fetch_ad_fullstats; print('Imports OK')"
```
Expected: `Imports OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/wb_api.py
git commit -m "feat(ads): add WB Advert API client functions"
```

---

### Task 4: Backend — Ad Sync Logic

**Files:**
- Modify: `backend/app/services/sync.py`
- Modify: `backend/app/services/scheduler.py`
- Modify: `backend/app/routers/shops.py`

- [ ] **Step 1: Add sync_shop_ads function to sync.py**

Add these imports at the top of `backend/app/services/sync.py` (merge with existing imports):

```python
from datetime import datetime, timezone, timedelta, date
from app.models.ad import AdCampaign, AdDailyStat
from app.services.wb_api import (
    fetch_new_orders, fetch_orders, fetch_order_statuses,
    fetch_warehouses, fetch_stocks, fetch_cards,
    fetch_statistics_orders,
    fetch_ad_campaign_ids, fetch_ad_details, fetch_ad_fullstats,
)
```

Then append this function at the end of `sync.py`:

```python
def sync_shop_ads(db: Session, shop: Shop):
    """Sync advertising campaigns and daily stats from WB Advert API."""
    api_token = decrypt_token(shop.api_token)

    # Step 1: Get all campaign IDs
    all_ids = fetch_ad_campaign_ids(api_token)
    if not all_ids:
        print(f"[Sync] No ad campaigns found for shop {shop.name}")
        return

    # Step 2: Fetch campaign details and upsert
    details = fetch_ad_details(api_token, all_ids)
    campaign_map = {}  # wb_advert_id → db campaign

    for d in details:
        wb_id = d.get("advertId")
        if not wb_id:
            continue

        existing = db.query(AdCampaign).filter(AdCampaign.wb_advert_id == wb_id).first()

        # Parse create time
        create_time_str = d.get("createTime", "")
        create_time = None
        if create_time_str:
            try:
                create_time = datetime.fromisoformat(create_time_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        if existing:
            existing.name = d.get("name", existing.name)
            existing.type = d.get("type", existing.type)
            existing.status = d.get("status", existing.status)
            existing.daily_budget = d.get("dailyBudget", existing.daily_budget) or 0
            if create_time:
                existing.create_time = create_time
            existing.updated_at = datetime.now(timezone.utc)
            campaign_map[wb_id] = existing
        else:
            campaign = AdCampaign(
                shop_id=shop.id,
                wb_advert_id=wb_id,
                name=d.get("name", ""),
                type=d.get("type", 0),
                status=d.get("status", 0),
                daily_budget=d.get("dailyBudget", 0) or 0,
                create_time=create_time,
            )
            db.add(campaign)
            db.flush()
            campaign_map[wb_id] = campaign

    # Step 3: Fetch daily stats for active campaigns (status 7=active, 9=paused, 11=ended)
    stat_campaign_ids = [
        wb_id for wb_id, c in campaign_map.items()
        if c.status in (7, 9, 11)
    ]

    if not stat_campaign_ids:
        db.commit()
        return

    # Determine date range: first sync = 30 days, incremental = 7 days
    has_any_stats = db.query(AdDailyStat).join(AdCampaign).filter(
        AdCampaign.shop_id == shop.id
    ).first()
    days_back = 7 if has_any_stats else 30

    today = date.today()
    date_from = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    date_to = today.strftime("%Y-%m-%d")

    raw_stats = fetch_ad_fullstats(api_token, stat_campaign_ids, date_from, date_to)

    # Step 4: Parse and upsert daily stats
    for entry in raw_stats:
        wb_advert_id = entry.get("advertId")
        campaign = campaign_map.get(wb_advert_id)
        if not campaign:
            continue

        for day_data in entry.get("days", []):
            day_date_str = day_data.get("date", "")[:10]  # "YYYY-MM-DD"
            if not day_date_str:
                continue
            try:
                stat_date = date.fromisoformat(day_date_str)
            except ValueError:
                continue

            for app_data in day_data.get("apps", []):
                for nm_data in app_data.get("nm", []):
                    nm_id = nm_data.get("nmId", 0)
                    if not nm_id:
                        continue

                    existing_stat = db.query(AdDailyStat).filter(
                        AdDailyStat.campaign_id == campaign.id,
                        AdDailyStat.nm_id == nm_id,
                        AdDailyStat.date == stat_date,
                    ).first()

                    views = nm_data.get("views", 0)
                    clicks = nm_data.get("clicks", 0)
                    spend = nm_data.get("sum", 0.0)
                    orders_count = nm_data.get("orders", 0)
                    order_amount = nm_data.get("sum_price", 0.0)
                    atbs = nm_data.get("atbs", 0)
                    ctr = nm_data.get("ctr", 0.0)
                    cpc = nm_data.get("cpc", 0.0)
                    cr = nm_data.get("cr", 0.0)

                    if existing_stat:
                        existing_stat.views = views
                        existing_stat.clicks = clicks
                        existing_stat.spend = spend
                        existing_stat.orders = orders_count
                        existing_stat.order_amount = order_amount
                        existing_stat.atbs = atbs
                        existing_stat.ctr = ctr
                        existing_stat.cpc = cpc
                        existing_stat.cr = cr
                    else:
                        stat = AdDailyStat(
                            campaign_id=campaign.id,
                            nm_id=nm_id,
                            date=stat_date,
                            views=views,
                            clicks=clicks,
                            ctr=ctr,
                            cpc=cpc,
                            spend=spend,
                            orders=orders_count,
                            order_amount=order_amount,
                            atbs=atbs,
                            cr=cr,
                        )
                        db.add(stat)

    db.commit()
    print(f"[Sync] Ad sync complete for shop {shop.name}: {len(campaign_map)} campaigns")
```

- [ ] **Step 2: Add sync_shop_ads to scheduler**

Edit `backend/app/services/scheduler.py` — update the import and add the call:

```python
from app.services.sync import sync_shop_orders, sync_shop_inventory, sync_shop_ads
```

In the `sync_all_shops` function, add after `sync_shop_inventory(db, shop)`:

```python
                sync_shop_ads(db, shop)
```

Full updated function:

```python
def sync_all_shops():
    db = SessionLocal()
    try:
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        for shop in shops:
            try:
                sync_shop_orders(db, shop)
                sync_shop_inventory(db, shop)
                sync_shop_ads(db, shop)
                print(f"[Scheduler] Synced shop: {shop.name}")
            except Exception as e:
                print(f"[Scheduler] Error syncing shop {shop.name}: {e}")
    finally:
        db.close()
```

- [ ] **Step 3: Add sync_shop_ads to manual sync endpoint**

Edit `backend/app/routers/shops.py` — update the import (line 55):

```python
from app.services.sync import sync_shop_orders, sync_shop_inventory, sync_shop_ads
```

In the `trigger_sync` function, add after `sync_shop_inventory(db, shop)`:

```python
        sync_shop_ads(db, shop)
```

- [ ] **Step 4: Verify sync imports work**

Run:
```bash
cd backend && python -c "from app.services.sync import sync_shop_ads; print('Import OK')"
```
Expected: `Import OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sync.py backend/app/services/scheduler.py backend/app/routers/shops.py
git commit -m "feat(ads): add ad sync logic, integrate with scheduler and manual sync"
```

---

### Task 5: Backend — Ad API Router

**Files:**
- Create: `backend/app/routers/ads.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the ads router**

Create `backend/app/routers/ads.py`:

```python
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
    """Default to last 7 days if no dates provided."""
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

    # Fetch campaigns
    q = db.query(AdCampaign)
    if shop_id:
        q = q.filter(AdCampaign.shop_id == shop_id)
    if status is not None:
        q = q.filter(AdCampaign.status == status)
    campaigns = q.order_by(AdCampaign.status.asc(), AdCampaign.updated_at.desc()).all()

    # Fetch aggregated stats per campaign
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
            id=c.id,
            shop_id=c.shop_id,
            wb_advert_id=c.wb_advert_id,
            name=c.name,
            type=c.type,
            status=c.status,
            daily_budget=c.daily_budget,
            create_time=c.create_time,
            updated_at=c.updated_at,
            **s,
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

    # Lookup product info from order_items (nm_id = wb_product_id)
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
```

- [ ] **Step 2: Register ads router in main.py**

Edit `backend/app/main.py` — add import and include:

After line 9 (`from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance, dashboard`), change to:

```python
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance, dashboard, ads
```

After line 42 (`app.include_router(dashboard.router)`), add:

```python
app.include_router(ads.router)
```

- [ ] **Step 3: Verify server starts**

Run:
```bash
cd backend && python -c "from app.main import app; print('App OK, routes:', [r.path for r in app.routes if hasattr(r, 'path') and '/ads' in r.path])"
```
Expected: Shows the 4 `/api/ads/*` routes.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/ads.py backend/app/main.py
git commit -m "feat(ads): add API router with overview, campaigns, stats, product-stats endpoints"
```

---

### Task 6: Frontend — Router and Navigation

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Layout.vue`

- [ ] **Step 1: Add routes for ads pages**

Edit `frontend/src/router/index.js` — add two routes inside the `children` array, after the `products` route:

```javascript
      { path: 'products', name: 'Products', component: () => import('../views/Products.vue') },
      { path: 'ads', name: 'AdsOverview', component: () => import('../views/AdsOverview.vue') },
      { path: 'ads/:id', name: 'AdDetail', component: () => import('../views/AdDetail.vue') },
```

- [ ] **Step 2: Update sidebar navigation in Layout.vue**

In `frontend/src/views/Layout.vue`, replace the 商品管理 menu item (lines 27-30):

```html
        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <span>商品管理</span>
        </el-menu-item>
```

With a submenu:

```html
        <el-sub-menu index="products-sub">
          <template #title>
            <el-icon><Goods /></el-icon>
            <span>商品管理</span>
          </template>
          <el-menu-item index="/products">商品列表</el-menu-item>
          <el-menu-item index="/ads">推广数据</el-menu-item>
        </el-sub-menu>
```

Also add `TrendCharts` to the icon imports (line 66):

```javascript
import { DataAnalysis, Box, Goods, Money, List, Shop, User, TrendCharts } from '@element-plus/icons-vue'
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.js frontend/src/views/Layout.vue
git commit -m "feat(ads): add ads routes and sidebar navigation under 商品管理"
```

---

### Task 7: Frontend — AdsOverview Page

**Files:**
- Create: `frontend/src/views/AdsOverview.vue`

- [ ] **Step 1: Create the AdsOverview page**

Create `frontend/src/views/AdsOverview.vue`:

```vue
<template>
  <div>
    <!-- 日期筛选 -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;">
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <el-button v-for="preset in presets" :key="preset.label"
          :type="activePreset === preset.label ? 'primary' : 'default'" size="small"
          @click="applyPreset(preset)">{{ preset.label }}</el-button>
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
          start-placeholder="开始日期" end-placeholder="结束日期" size="small"
          value-format="YYYY-MM-DD" @change="onDateChange" />
      </div>
    </div>

    <!-- KPI 卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="5" v-for="kpi in kpis" :key="kpi.label">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 13px">{{ kpi.label }}</div>
          <div :style="{ fontSize: '24px', fontWeight: 'bold', marginTop: '6px', color: kpi.color || '' }">
            {{ kpi.prefix }}{{ kpi.value?.toLocaleString() }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-card style="margin-bottom: 20px">
      <template #header>推广趋势</template>
      <v-chart :option="chartOption" style="height: 280px" autoresize />
    </el-card>

    <!-- 广告活动列表 -->
    <el-card style="margin-bottom: 20px">
      <template #header>广告活动</template>
      <el-table :data="campaigns" stripe>
        <el-table-column prop="name" label="活动名称" min-width="180" />
        <el-table-column prop="type" label="类型" min-width="80">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: statusColor(row.status), fontWeight: 'bold' }">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_spend" label="花费" min-width="100">
          <template #default="{ row }">¥ {{ row.total_spend?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_views" label="展示" min-width="90">
          <template #default="{ row }">{{ row.total_views?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_clicks" label="点击" min-width="80">
          <template #default="{ row }">{{ row.total_clicks?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_orders" label="订单" min-width="70" />
        <el-table-column prop="roas" label="ROAS" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: row.roas >= 2 ? '#67c23a' : row.roas >= 1 ? '#e6a23c' : '#f56c6c', fontWeight: 'bold' }">
              {{ row.roas }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="$router.push(`/ads/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 商品推广排行 -->
    <el-card>
      <template #header>商品推广排行</template>
      <el-table :data="productStats" stripe>
        <el-table-column label="商品" min-width="200">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-image v-if="row.image_url" :src="row.image_url" style="width: 36px; height: 36px; border-radius: 4px" fit="cover">
                <template #error><span style="color: #ccc; font-size: 12px">无图</span></template>
              </el-image>
              <span>{{ row.product_name || '-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sku" label="产品SKU" min-width="120" />
        <el-table-column prop="total_spend" label="花费" min-width="100">
          <template #default="{ row }">¥ {{ row.total_spend?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_views" label="展示" min-width="90">
          <template #default="{ row }">{{ row.total_views?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_clicks" label="点击" min-width="80">
          <template #default="{ row }">{{ row.total_clicks?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_orders" label="订单" min-width="70" />
        <el-table-column prop="total_order_amount" label="订单金额" min-width="100">
          <template #default="{ row }">¥ {{ row.total_order_amount?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="roas" label="ROAS" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: row.roas >= 2 ? '#67c23a' : row.roas >= 1 ? '#e6a23c' : '#f56c6c', fontWeight: 'bold' }">
              {{ row.roas }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const overview = ref({})
const campaigns = ref([])
const productStats = ref([])
const dailyStats = ref([])
const dateRange = ref(null)
const activePreset = ref('近7天')

const today = new Date()
function fmt(d) { return d.toISOString().slice(0, 10) }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r }

const presets = [
  { label: '今日', from: fmt(today), to: fmt(today) },
  { label: '昨日', from: fmt(addDays(today, -1)), to: fmt(addDays(today, -1)) },
  { label: '近7天', from: fmt(addDays(today, -6)), to: fmt(today) },
  { label: '近30天', from: fmt(addDays(today, -29)), to: fmt(today) },
]

let currentFrom = presets[2].from
let currentTo = presets[2].to

function applyPreset(preset) {
  activePreset.value = preset.label
  currentFrom = preset.from
  currentTo = preset.to
  dateRange.value = null
  fetchAll()
}

function onDateChange(val) {
  if (val && val.length === 2) {
    activePreset.value = ''
    currentFrom = val[0]
    currentTo = val[1]
    fetchAll()
  }
}

const kpis = computed(() => [
  { label: '推广花费', value: overview.value.total_spend, prefix: '¥ ' },
  { label: '展示量', value: overview.value.total_views, prefix: '' },
  { label: '点击量', value: overview.value.total_clicks, prefix: '' },
  { label: '推广订单', value: overview.value.total_orders, prefix: '' },
  { label: 'ROAS', value: overview.value.roas, prefix: '', color: '#67c23a' },
])

const TYPE_MAP = { 5: '自动', 6: '搜索', 7: '卡片', 8: '推荐', 9: '搜索+推荐' }
const TYPE_TAG = { 5: 'success', 6: '', 7: 'warning', 8: '', 9: 'info' }
const STATUS_MAP = { 4: '准备中', 7: '进行中', 8: '审核中', 9: '已暂停', 11: '已结束' }
const STATUS_COLOR = { 4: '#909399', 7: '#67c23a', 8: '#e6a23c', 9: '#909399', 11: '#606266' }

function typeLabel(t) { return TYPE_MAP[t] || t }
function typeTagType(t) { return TYPE_TAG[t] || '' }
function statusLabel(s) { return STATUS_MAP[s] || s }
function statusColor(s) { return STATUS_COLOR[s] || '#606266' }

// Chart: aggregate dailyStats by date for trend
const chartOption = computed(() => {
  const byDate = {}
  for (const s of dailyStats.value) {
    const d = s.date
    if (!byDate[d]) byDate[d] = { spend: 0, order_amount: 0 }
    byDate[d].spend += s.spend
    byDate[d].order_amount += s.order_amount
  }
  const dates = Object.keys(byDate).sort()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['花费', '订单金额'] },
    grid: { left: 50, right: 30, bottom: 30, top: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: [
      { name: '花费', type: 'bar', data: dates.map(d => byDate[d].spend.toFixed(2)), itemStyle: { color: '#409eff' } },
      { name: '订单金额', type: 'line', data: dates.map(d => byDate[d].order_amount.toFixed(2)), itemStyle: { color: '#67c23a' } },
    ],
  }
})

async function fetchAll() {
  const params = { date_from: currentFrom, date_to: currentTo }
  const [ovRes, campRes, prodRes] = await Promise.all([
    api.get('/api/ads/overview', { params }),
    api.get('/api/ads/campaigns', { params }),
    api.get('/api/ads/product-stats', { params }),
  ])
  overview.value = ovRes.data
  campaigns.value = campRes.data
  productStats.value = prodRes.data

  // Fetch daily stats for all campaigns (for chart)
  const allStats = []
  for (const c of campRes.data) {
    try {
      const res = await api.get(`/api/ads/campaigns/${c.id}/stats`, { params })
      allStats.push(...res.data)
    } catch (e) { /* skip */ }
  }
  dailyStats.value = allStats
}

onMounted(fetchAll)
</script>
```

- [ ] **Step 2: Verify the page renders without errors**

Start the dev server and navigate to `/ads` in the browser. The page should load without JS errors (data will be empty until sync runs).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AdsOverview.vue
git commit -m "feat(ads): add AdsOverview page with KPIs, chart, campaigns, and product stats"
```

---

### Task 8: Frontend — AdDetail Page

**Files:**
- Create: `frontend/src/views/AdDetail.vue`

- [ ] **Step 1: Create the AdDetail page**

Create `frontend/src/views/AdDetail.vue`:

```vue
<template>
  <div>
    <!-- 返回 + 活动信息 -->
    <el-page-header @back="$router.push('/ads')" style="margin-bottom: 20px">
      <template #content>
        <span style="font-size: 18px; font-weight: bold">{{ campaign.name || '广告活动详情' }}</span>
        <el-tag :type="typeTagType(campaign.type)" size="small" style="margin-left: 10px">{{ typeLabel(campaign.type) }}</el-tag>
        <span :style="{ color: statusColor(campaign.status), fontWeight: 'bold', marginLeft: '10px' }">{{ statusLabel(campaign.status) }}</span>
      </template>
    </el-page-header>

    <!-- 日期筛选 -->
    <div style="display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap;">
      <el-button v-for="preset in presets" :key="preset.label"
        :type="activePreset === preset.label ? 'primary' : 'default'" size="small"
        @click="applyPreset(preset)">{{ preset.label }}</el-button>
      <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
        start-placeholder="开始日期" end-placeholder="结束日期" size="small"
        value-format="YYYY-MM-DD" @change="onDateChange" />
    </div>

    <!-- KPI 卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="4" v-for="kpi in kpis" :key="kpi.label">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 12px">{{ kpi.label }}</div>
          <div :style="{ fontSize: '20px', fontWeight: 'bold', marginTop: '4px', color: kpi.color || '' }">
            {{ kpi.prefix }}{{ kpi.value?.toLocaleString() }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-card style="margin-bottom: 20px">
      <template #header>每日趋势</template>
      <v-chart :option="chartOption" style="height: 280px" autoresize />
    </el-card>

    <!-- 商品明细 -->
    <el-card>
      <template #header>商品明细</template>
      <el-table :data="productAgg" stripe>
        <el-table-column prop="nm_id" label="商品ID" min-width="100" />
        <el-table-column prop="spend" label="花费" min-width="90">
          <template #default="{ row }">¥ {{ row.spend?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="views" label="展示" min-width="90">
          <template #default="{ row }">{{ row.views?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="clicks" label="点击" min-width="80" />
        <el-table-column prop="ctr" label="CTR" min-width="70">
          <template #default="{ row }">{{ row.ctr }}%</template>
        </el-table-column>
        <el-table-column prop="orders" label="订单" min-width="70" />
        <el-table-column prop="order_amount" label="订单金额" min-width="100">
          <template #default="{ row }">¥ {{ row.order_amount?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="roas" label="ROAS" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: row.roas >= 2 ? '#67c23a' : row.roas >= 1 ? '#e6a23c' : '#f56c6c', fontWeight: 'bold' }">
              {{ row.roas }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const route = useRoute()
const campaignId = route.params.id

const campaign = ref({})
const stats = ref([])
const dateRange = ref(null)
const activePreset = ref('近7天')

const today = new Date()
function fmt(d) { return d.toISOString().slice(0, 10) }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r }

const presets = [
  { label: '今日', from: fmt(today), to: fmt(today) },
  { label: '昨日', from: fmt(addDays(today, -1)), to: fmt(addDays(today, -1)) },
  { label: '近7天', from: fmt(addDays(today, -6)), to: fmt(today) },
  { label: '近30天', from: fmt(addDays(today, -29)), to: fmt(today) },
]

let currentFrom = presets[2].from
let currentTo = presets[2].to

function applyPreset(preset) {
  activePreset.value = preset.label
  currentFrom = preset.from
  currentTo = preset.to
  dateRange.value = null
  fetchData()
}

function onDateChange(val) {
  if (val && val.length === 2) {
    activePreset.value = ''
    currentFrom = val[0]
    currentTo = val[1]
    fetchData()
  }
}

const TYPE_MAP = { 5: '自动', 6: '搜索', 7: '卡片', 8: '推荐', 9: '搜索+推荐' }
const TYPE_TAG = { 5: 'success', 6: '', 7: 'warning', 8: '', 9: 'info' }
const STATUS_MAP = { 4: '准备中', 7: '进行中', 8: '审核中', 9: '已暂停', 11: '已结束' }
const STATUS_COLOR = { 4: '#909399', 7: '#67c23a', 8: '#e6a23c', 9: '#909399', 11: '#606266' }

function typeLabel(t) { return TYPE_MAP[t] || t }
function typeTagType(t) { return TYPE_TAG[t] || '' }
function statusLabel(s) { return STATUS_MAP[s] || s }
function statusColor(s) { return STATUS_COLOR[s] || '#606266' }

// Aggregate stats
const totals = computed(() => {
  let spend = 0, views = 0, clicks = 0, orders = 0, order_amount = 0, atbs = 0
  for (const s of stats.value) {
    spend += s.spend; views += s.views; clicks += s.clicks
    orders += s.orders; order_amount += s.order_amount; atbs += s.atbs
  }
  const roas = spend > 0 ? (order_amount / spend).toFixed(2) : 0
  const ctr = views > 0 ? (clicks / views * 100).toFixed(2) : 0
  return { spend, views, clicks, orders, order_amount, atbs, roas: Number(roas), ctr: Number(ctr) }
})

const kpis = computed(() => [
  { label: '花费', value: totals.value.spend, prefix: '¥ ' },
  { label: '展示', value: totals.value.views, prefix: '' },
  { label: '点击', value: totals.value.clicks, prefix: '' },
  { label: 'CTR', value: totals.value.ctr, prefix: '', color: '#409eff' },
  { label: '订单', value: totals.value.orders, prefix: '' },
  { label: 'ROAS', value: totals.value.roas, prefix: '', color: '#67c23a' },
])

// Aggregate by nm_id for product table
const productAgg = computed(() => {
  const map = {}
  for (const s of stats.value) {
    if (!map[s.nm_id]) map[s.nm_id] = { nm_id: s.nm_id, spend: 0, views: 0, clicks: 0, orders: 0, order_amount: 0 }
    const m = map[s.nm_id]
    m.spend += s.spend; m.views += s.views; m.clicks += s.clicks
    m.orders += s.orders; m.order_amount += s.order_amount
  }
  return Object.values(map).map(m => ({
    ...m,
    spend: Math.round(m.spend * 100) / 100,
    order_amount: Math.round(m.order_amount * 100) / 100,
    ctr: m.views > 0 ? (m.clicks / m.views * 100).toFixed(2) : '0.00',
    roas: m.spend > 0 ? (m.order_amount / m.spend).toFixed(2) : '0.00',
  })).sort((a, b) => b.spend - a.spend)
})

// Chart by date
const chartOption = computed(() => {
  const byDate = {}
  for (const s of stats.value) {
    if (!byDate[s.date]) byDate[s.date] = { spend: 0, order_amount: 0 }
    byDate[s.date].spend += s.spend
    byDate[s.date].order_amount += s.order_amount
  }
  const dates = Object.keys(byDate).sort()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['花费', '订单金额'] },
    grid: { left: 50, right: 30, bottom: 30, top: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: [
      { name: '花费', type: 'bar', data: dates.map(d => byDate[d].spend.toFixed(2)), itemStyle: { color: '#409eff' } },
      { name: '订单金额', type: 'line', data: dates.map(d => byDate[d].order_amount.toFixed(2)), itemStyle: { color: '#67c23a' } },
    ],
  }
})

async function fetchData() {
  const params = { date_from: currentFrom, date_to: currentTo }

  // Fetch campaign info from campaigns list
  try {
    const campRes = await api.get('/api/ads/campaigns', { params })
    campaign.value = campRes.data.find(c => c.id === Number(campaignId)) || {}
  } catch (e) { /* skip */ }

  // Fetch daily stats
  try {
    const res = await api.get(`/api/ads/campaigns/${campaignId}/stats`, { params })
    stats.value = res.data
  } catch (e) {
    stats.value = []
  }
}

onMounted(fetchData)
</script>
```

- [ ] **Step 2: Verify the page renders**

Navigate to `/ads/1` (or any campaign ID). The page should load without JS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AdDetail.vue
git commit -m "feat(ads): add AdDetail page with campaign stats, chart, and product breakdown"
```

---

### Task 9: Integration Test — End-to-End Sync and Display

**Files:** No new files — manual verification.

- [ ] **Step 1: Restart backend to pick up all changes**

```bash
taskkill /F /IM python.exe 2>/dev/null
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Trigger manual sync to fetch ad data**

Either click "同步" on the shop management page, or run:

```bash
cd backend && python -c "
from app.database import SessionLocal
from app.models.shop import Shop
from app.services.sync import sync_shop_ads
db = SessionLocal()
shop = db.query(Shop).first()
if shop:
    sync_shop_ads(db, shop)
    print('Ad sync done')
db.close()
"
```

- [ ] **Step 3: Verify API returns data**

```bash
# Get a token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -d "username=admin&password=YOUR_PASSWORD" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Test overview endpoint
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/ads/overview?date_from=2026-03-01&date_to=2026-04-01" | python -m json.tool
```

Expected: JSON with `total_spend`, `total_views`, `total_clicks`, `total_orders`, `total_order_amount`, `roas`.

- [ ] **Step 4: Verify frontend pages**

1. Open browser → navigate to `/ads` → verify KPI cards, chart, campaign table, product ranking all show data
2. Click "详情" on a campaign → verify AdDetail page shows campaign stats and product breakdown
3. Switch date presets → verify data updates correctly

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(ads): complete advertising data module — sync, API, overview and detail pages"
```
