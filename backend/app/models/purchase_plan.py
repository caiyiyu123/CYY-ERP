from datetime import datetime, date, timezone
from sqlalchemy import String, Float, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PurchasePlan(Base):
    __tablename__ = "purchase_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    operator_name: Mapped[str] = mapped_column(String(50), default="")
    purchase_date: Mapped[date] = mapped_column(Date)
    express_fee: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    items: Mapped[list["PurchasePlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchasePlanItem(Base):
    __tablename__ = "purchase_plan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_plans.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    boxes: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    plan: Mapped["PurchasePlan"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="selectin")
