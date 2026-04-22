from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Shop(Base):
    __tablename__ = "shops"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    api_token: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # 后台慢速回溯游标：已回溯到的最早日期（NULL = 尚未开始）
    orders_backfill_cursor: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    finance_backfill_cursor: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
