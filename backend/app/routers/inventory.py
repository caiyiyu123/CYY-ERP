from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryOut
from app.utils.deps import get_current_user, get_accessible_shop_ids, require_module

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryOut])
def list_inventory(shop_id: Optional[int] = Query(None), db: Session = Depends(get_db), accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _=Depends(require_module("inventory"))):
    query = db.query(Inventory)
    if accessible_shops is not None:
        query = query.filter(Inventory.shop_id.in_(accessible_shops))
    if shop_id:
        query = query.filter(Inventory.shop_id == shop_id)
    return query.all()


@router.get("/low-stock", response_model=list[InventoryOut])
def low_stock_alerts(db: Session = Depends(get_db), accessible_shops: list[int] | None = Depends(get_accessible_shop_ids), _=Depends(require_module("inventory"))):
    query = db.query(Inventory).filter(
        (Inventory.stock_fbs + Inventory.stock_fbw) < Inventory.low_stock_threshold
    )
    if accessible_shops is not None:
        query = query.filter(Inventory.shop_id.in_(accessible_shops))
    return query.all()
