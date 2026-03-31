from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.shop import Shop
from app.schemas.shop import ShopCreate, ShopUpdate, ShopOut
from app.utils.security import encrypt_token, decrypt_token
from app.utils.deps import require_role, get_current_user

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.get("", response_model=list[ShopOut])
def list_shops(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Shop).all()


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
