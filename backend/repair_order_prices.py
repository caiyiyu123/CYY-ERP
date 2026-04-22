"""一次性修复脚本：把 orders.price_rub=0 但 finance_order_records 已有 retail_price 的订单回填。

背景：Marketplace /api/v3/orders 对已完成的 FBS 订单常常返回 salePrice=0，
而 finance_sync 过去只写 finance_order_records，不反哺 orders 表，
导致订单列表金额长期为 0。本脚本按 (shop_id, srid) 把财务记录里的
retail_price 回填到 orders.price_rub / total_price。

用法：
    cd backend
    python repair_order_prices.py                  # 修复所有启用中的店铺
    python repair_order_prices.py --shop 1         # 仅修复店铺 1
    python repair_order_prices.py --dry-run        # 只打印，不真写
"""
from __future__ import annotations
import argparse

from sqlalchemy import func

from app.database import SessionLocal
from app.models.finance import FinanceOrderRecord
from app.models.shop import Shop
from app.services.finance_sync import apply_srid_price_map


def _collect_srid_price_map(db, shop_id: int) -> dict[str, float]:
    """Build srid→max(retail_price) map from FinanceOrderRecord for one shop."""
    rows = db.query(
        FinanceOrderRecord.srid,
        func.max(FinanceOrderRecord.retail_price),
    ).filter(
        FinanceOrderRecord.shop_id == shop_id,
        FinanceOrderRecord.srid != "",
        FinanceOrderRecord.retail_price > 0,
    ).group_by(FinanceOrderRecord.srid).all()
    return {srid: float(price) for srid, price in rows if srid and price}


def repair(shop_id: int | None = None, dry_run: bool = False) -> dict[str, str]:
    db = SessionLocal()
    try:
        q = db.query(Shop).filter(Shop.is_active == True)
        if shop_id is not None:
            q = q.filter(Shop.id == shop_id)
        shops = q.all()
        if not shops:
            return {}

        summary: dict[str, str] = {}
        for shop in shops:
            try:
                srid_to_price = _collect_srid_price_map(db, shop.id)
                if not srid_to_price:
                    summary[shop.name] = "0/0"
                    print(f"店铺 {shop.name}: finance 表无可用价格")
                    continue

                if dry_run:
                    # 仅统计匹配数，不走写入路径
                    from app.models.order import Order
                    matched = db.query(Order).filter(
                        Order.shop_id == shop.id,
                        Order.total_price == 0,
                        Order.srid.in_(list(srid_to_price.keys())),
                    ).count()
                    summary[shop.name] = f"{matched} (dry-run)"
                    print(f"[DRY-RUN] 店铺 {shop.name}: 可回填 {matched} 单")
                else:
                    updated = apply_srid_price_map(db, shop.id, srid_to_price)
                    if updated:
                        db.commit()
                    summary[shop.name] = str(updated)
                    print(f"店铺 {shop.name}: 回填 {updated} 单")
            except Exception as e:
                db.rollback()
                summary[shop.name] = f"ERROR: {e}"
                print(f"店铺 {shop.name} 失败: {e}")
                continue
        return summary
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="修复 orders 表零金额订单")
    parser.add_argument("--shop", type=int, default=None, help="只修复指定店铺 ID")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = parser.parse_args()

    print("开始检查订单金额...")
    result = repair(shop_id=args.shop, dry_run=args.dry_run)
    print("\n=== 汇总 ===")
    for name, count in result.items():
        print(f"  {name}: {count}")
    print("\n完成。")
