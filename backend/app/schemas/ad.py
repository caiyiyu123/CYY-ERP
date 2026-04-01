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
