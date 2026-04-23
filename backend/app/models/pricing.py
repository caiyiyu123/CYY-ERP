from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PricingItem(Base):
    __tablename__ = "pricing_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    sku: Mapped[str] = mapped_column(String(200), default="", index=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    image_url: Mapped[str] = mapped_column(String(500), default="")
    purchase_cost: Mapped[float] = mapped_column(Float, default=0.0)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    length_cm: Mapped[float] = mapped_column(Float, default=0.0)
    width_cm: Mapped[float] = mapped_column(Float, default=0.0)
    height_cm: Mapped[float] = mapped_column(Float, default=0.0)
    wb_local_rate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commission_rates.id", ondelete="SET NULL"), nullable=True
    )
    wb_cross_rate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commission_rates.id", ondelete="SET NULL"), nullable=True
    )
    ozon_local_rate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commission_rates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    platforms: Mapped[list["PricingPlatform"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class PricingPlatform(Base):
    __tablename__ = "pricing_platforms"
    __table_args__ = (
        UniqueConstraint("item_id", "platform", name="uq_pricing_item_platform"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pricing_items.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(30))
    price_rub: Mapped[float] = mapped_column(Float, default=0.0)
    price_rmb: Mapped[float] = mapped_column(Float, default=0.0)
    discount_pct: Mapped[float] = mapped_column(Float, default=0.0)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    item: Mapped["PricingItem"] = relationship(back_populates="platforms")
