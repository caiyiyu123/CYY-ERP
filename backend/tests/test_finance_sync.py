from datetime import date, datetime
from unittest.mock import patch, MagicMock
from app.models.finance import FinanceOrderRecord, FinanceOtherFee, FinanceSyncLog
from app.models.shop import Shop
from app.utils.security import encrypt_token


def test_finance_order_record_model(db):
    shop = Shop(name="S", type="local", api_token=encrypt_token("t"), is_active=True)
    db.add(shop); db.commit()
    rec = FinanceOrderRecord(
        shop_id=shop.id, srid="abc123", currency="RUB",
        sale_date=date(2026, 4, 13), order_date=date(2026, 4, 8),
        report_period_start=date(2026, 4, 6), report_period_end=date(2026, 4, 12),
        nm_id="507336942", shop_sku="SKU-1",
        quantity=1, net_to_seller=90.01, delivery_fee=13.04,
        purchase_cost=30.0, net_profit=46.97, has_sku_mapping=True,
    )
    db.add(rec); db.commit()
    assert rec.id > 0
    assert rec.currency == "RUB"


def test_finance_other_fee_model(db):
    shop = Shop(name="S", type="cross_border", api_token=encrypt_token("t"), is_active=True)
    db.add(shop); db.commit()
    fee = FinanceOtherFee(
        shop_id=shop.id, currency="CNY",
        sale_date=date(2026, 4, 10),
        report_period_start=date(2026, 4, 6), report_period_end=date(2026, 4, 12),
        fee_type="storage", fee_description="Хранение", amount=100.0,
        raw_row={"foo": "bar"},
    )
    db.add(fee); db.commit()
    assert fee.raw_row == {"foo": "bar"}


def test_finance_sync_log_model(db):
    shop = Shop(name="S", type="local", api_token=encrypt_token("t"), is_active=True)
    db.add(shop); db.commit()
    log = FinanceSyncLog(
        shop_id=shop.id, triggered_by="cron",
        date_from=date(2026, 4, 6), date_to=date(2026, 4, 12),
        status="running",
    )
    db.add(log); db.commit()
    assert log.status == "running"
    assert log.started_at is not None


def test_fetch_finance_report_paginates():
    """fetch_finance_report 按 rrdid 分页直到返回空。"""
    from app.services.wb_api import fetch_finance_report

    pages = [
        [{"rrd_id": 1, "srid": "s1", "supplier_oper_name": "Продажа"},
         {"rrd_id": 2, "srid": "s2", "supplier_oper_name": "Логистика"}],
        [{"rrd_id": 3, "srid": "s3", "supplier_oper_name": "Продажа"}],
        [],
    ]
    call_log = []

    class FakeResp:
        def __init__(self, data):
            self.status_code = 200
            self._data = data
        def json(self):
            return self._data

    def fake_get(url, params=None, headers=None, timeout=None):
        call_log.append(params.get("rrdid"))
        idx = len(call_log) - 1
        return FakeResp(pages[idx])

    with patch("app.services.wb_api.httpx.Client") as mock_client:
        ctx = mock_client.return_value.__enter__.return_value
        ctx.get.side_effect = fake_get
        rows = fetch_finance_report("fake_token", "2026-04-01", "2026-04-07")

    assert len(rows) == 3
    assert call_log == [0, 2, 3]   # 首页 0，下一页用上一页最后 rrd_id


def test_fetch_finance_report_handles_429():
    """遇 429 指数退避重试，最终成功。"""
    from app.services.wb_api import fetch_finance_report

    class FakeResp:
        def __init__(self, status, data=None):
            self.status_code = status
            self._data = data or []
        def json(self):
            return self._data

    responses = [FakeResp(429), FakeResp(200, [])]

    with patch("app.services.wb_api.httpx.Client") as mock_client, \
         patch("app.services.wb_api.time.sleep") as mock_sleep:
        ctx = mock_client.return_value.__enter__.return_value
        ctx.get.side_effect = responses
        rows = fetch_finance_report("fake_token", "2026-04-01", "2026-04-07")

    assert rows == []
    assert mock_sleep.called
