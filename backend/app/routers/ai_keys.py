from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_api_key import AiApiKey
from app.utils.security import encrypt_token, decrypt_token
from app.utils.deps import require_role

router = APIRouter(prefix="/api/ai-keys", tags=["ai-keys"])


class AiKeyCreate(BaseModel):
    name: str
    model: str
    api_key: str


class AiKeyUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    api_key: str | None = None


def _mask(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "****"
    return token[:4] + "****" + token[-4:]


@router.get("")
def list_ai_keys(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.query(AiApiKey).order_by(AiApiKey.id.desc()).all()
    result = []
    for r in rows:
        try:
            plain = decrypt_token(r.api_key)
        except Exception:
            plain = ""
        result.append({
            "id": r.id,
            "name": r.name,
            "model": r.model,
            "api_key_masked": _mask(plain),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return result


@router.post("", status_code=201)
def create_ai_key(body: AiKeyCreate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    if not body.name or not body.model or not body.api_key:
        raise HTTPException(status_code=400, detail="name/model/api_key 不能为空")
    row = AiApiKey(name=body.name, model=body.model, api_key=encrypt_token(body.api_key))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.put("/{key_id}")
def update_ai_key(key_id: int, body: AiKeyUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    row = db.query(AiApiKey).filter(AiApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if body.name is not None:
        row.name = body.name
    if body.model is not None:
        row.model = body.model
    if body.api_key:
        row.api_key = encrypt_token(body.api_key)
    db.commit()
    return {"ok": True}


@router.delete("/{key_id}")
def delete_ai_key(key_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    row = db.query(AiApiKey).filter(AiApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
