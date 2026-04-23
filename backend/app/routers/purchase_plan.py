from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.purchase_plan import PurchasePlan, PurchasePlanItem
from app.models.product import Product
from app.utils.deps import require_module

router = APIRouter(prefix="/api/purchase-plans", tags=["purchase-plans"])


class PlanItemIn(BaseModel):
    product_id: int
    quantity: int = 0
    boxes: int = 0
    unit_price: float = 0.0


class PlanCreate(BaseModel):
    operator_name: str
    purchase_date: date
    express_fee: float = 0.0
    items: list[PlanItemIn]


class PlanUpdate(BaseModel):
    operator_name: str
    purchase_date: date
    express_fee: float = 0.0
    items: list[PlanItemIn]


class StatusUpdate(BaseModel):
    status: str


def _plan_to_dict(plan: PurchasePlan) -> dict:
    return {
        "id": plan.id,
        "operator_name": plan.operator_name,
        "purchase_date": plan.purchase_date.isoformat(),
        "express_fee": plan.express_fee,
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_sku": item.product.sku if item.product else "",
                "product_name": item.product.name if item.product else "",
                "product_image": item.product.image if item.product else "",
                "quantity": item.quantity,
                "boxes": item.boxes,
                "unit_price": item.unit_price,
            }
            for item in plan.items
        ],
    }


@router.get("")
def list_plans(
    status: str = Query("", description="Filter by status"),
    db: Session = Depends(get_db),
    _=Depends(require_module("purchase_plan")),
):
    q = db.query(PurchasePlan).order_by(PurchasePlan.purchase_date.desc(), PurchasePlan.created_at.desc())
    if status:
        q = q.filter(PurchasePlan.status == status)
    return [_plan_to_dict(p) for p in q.all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
    _=Depends(require_module("purchase_plan")),
):
    plan = PurchasePlan(
        operator_name=data.operator_name,
        purchase_date=data.purchase_date,
        express_fee=data.express_fee,
    )
    db.add(plan)
    db.flush()
    for item in data.items:
        db.add(PurchasePlanItem(
            plan_id=plan.id,
            product_id=item.product_id,
            quantity=item.quantity,
            boxes=item.boxes,
            unit_price=item.unit_price,
        ))
    db.commit()
    db.refresh(plan)
    return _plan_to_dict(plan)


@router.put("/{plan_id}")
def update_plan(
    plan_id: int,
    data: PlanUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_module("purchase_plan")),
):
    plan = db.query(PurchasePlan).filter(PurchasePlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.operator_name = data.operator_name
    plan.purchase_date = data.purchase_date
    plan.express_fee = data.express_fee
    # 删除旧明细，重建
    db.query(PurchasePlanItem).filter(PurchasePlanItem.plan_id == plan.id).delete()
    for item in data.items:
        db.add(PurchasePlanItem(
            plan_id=plan.id,
            product_id=item.product_id,
            quantity=item.quantity,
            boxes=item.boxes,
            unit_price=item.unit_price,
        ))
    db.commit()
    db.refresh(plan)
    return _plan_to_dict(plan)


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_module("purchase_plan")),
):
    plan = db.query(PurchasePlan).filter(PurchasePlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    db.commit()
    return {"detail": "Plan deleted"}


VALID_STATUSES = {"pending", "purchased", "domestic", "shipping", "arrived"}


@router.put("/{plan_id}/status")
def update_plan_status(
    plan_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_module("purchase_plan")),
):
    if data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")
    plan = db.query(PurchasePlan).filter(PurchasePlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = data.status
    db.commit()
    return {"detail": "Status updated", "status": plan.status}
