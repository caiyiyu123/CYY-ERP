import threading
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.shop import Shop
from app.schemas.shop import ShopCreate, ShopUpdate, ShopOut
from app.utils.security import encrypt_token, decrypt_token
from app.utils.deps import require_role, get_current_user, get_accessible_shop_ids, require_module

router = APIRouter(prefix="/api/shops", tags=["shops"])

# Track running sync tasks: shop_id → {"status": "running"|"done"|"error", "detail": str}
_sync_status: dict[int, dict] = {}
_sync_lock = threading.Lock()


@router.get("", response_model=list[ShopOut])
def list_shops(db: Session = Depends(get_db), shop_ids: list[int] | None = Depends(get_accessible_shop_ids)):
    query = db.query(Shop)
    if shop_ids is not None:
        query = query.filter(Shop.id.in_(shop_ids))
    return query.all()


@router.post("", response_model=ShopOut, status_code=status.HTTP_201_CREATED)
def create_shop(data: ShopCreate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    shop = Shop(name=data.name, type=data.type, api_token=encrypt_token(data.api_token))
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.put("/{shop_id}", response_model=ShopOut)
def update_shop(shop_id: int, data: ShopUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if data.name is not None:
        shop.name = data.name
    if data.type is not None:
        shop.type = data.type
    if data.api_token is not None:
        shop.api_token = encrypt_token(data.api_token)
    if data.is_active is not None:
        shop.is_active = data.is_active
    db.commit()
    db.refresh(shop)
    return shop


@router.delete("/{shop_id}")
def delete_shop(shop_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    db.delete(shop)
    db.commit()
    return {"detail": "Shop deleted"}


from app.services.sync import sync_shop_orders, sync_shop_inventory, sync_shop_ads


def _run_sync(shop_id: int):
    """Run sync in background thread with its own DB session."""
    db = SessionLocal()
    try:
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            with _sync_lock:
                _sync_status[shop_id] = {"status": "error", "detail": "Shop not found"}
            return
        cards = sync_shop_orders(db, shop)
        sync_shop_inventory(db, shop)
        sync_shop_ads(db, shop, cards=cards)
        with _sync_lock:
            _sync_status[shop_id] = {"status": "done", "detail": f"Sync completed for {shop.name}"}
    except Exception as e:
        with _sync_lock:
            _sync_status[shop_id] = {"status": "error", "detail": str(e)}
    finally:
        db.close()


@router.post("/{shop_id}/sync")
def trigger_sync(shop_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "operator"))):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    with _sync_lock:
        current = _sync_status.get(shop_id)
        if current and current["status"] == "running":
            return {"status": "running", "detail": "Sync already in progress"}
        _sync_status[shop_id] = {"status": "running", "detail": ""}

    thread = threading.Thread(target=_run_sync, args=(shop_id,), daemon=True)
    thread.start()
    return {"status": "running", "detail": "Sync started"}


@router.get("/{shop_id}/sync-status")
def get_sync_status(shop_id: int, _=Depends(require_role("admin", "operator"))):
    with _sync_lock:
        info = _sync_status.get(shop_id)
    if not info:
        return {"status": "idle", "detail": ""}
    return info
