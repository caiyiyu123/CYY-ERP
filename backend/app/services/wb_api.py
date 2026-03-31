import httpx
import time
from typing import Optional
from datetime import datetime

# WB API base URLs
MARKETPLACE_API = "https://marketplace-api.wildberries.ru"
STATISTICS_API = "https://statistics-api.wildberries.ru"

# Rate limit: min 200ms between requests
_last_request_time = 0.0
_MIN_INTERVAL = 0.2


def _throttle():
    """Ensure minimum interval between API requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.time()


def _headers(api_token: str) -> dict:
    return {"Authorization": api_token, "Content-Type": "application/json"}


def fetch_new_orders(api_token: str) -> list[dict]:
    """GET /api/v3/orders/new — fetch new FBS orders awaiting processing."""
    url = f"{MARKETPLACE_API}/api/v3/orders/new"
    try:
        _throttle()
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=_headers(api_token))
            resp.raise_for_status()
            data = resp.json()
            return data.get("orders", [])
    except Exception as e:
        print(f"[WB API] Error fetching new orders: {e}")
        return []


def fetch_orders(api_token: str, date_from: Optional[datetime] = None) -> list[dict]:
    """GET /api/v3/orders — fetch historical orders with pagination.

    Each order has: id, createdAt, warehouseId, nmId, chrtId, price,
    convertedPrice, currencyCode, cargoType, skus[], article, etc.
    """
    url = f"{MARKETPLACE_API}/api/v3/orders"
    all_orders = []
    next_cursor = 0

    try:
        with httpx.Client(timeout=30) as client:
            while True:
                params = {"limit": 1000, "next": next_cursor}
                if date_from:
                    params["dateFrom"] = int(date_from.timestamp())

                _throttle()
                resp = client.get(url, headers=_headers(api_token), params=params)
                resp.raise_for_status()
                data = resp.json()

                orders = data.get("orders", [])
                all_orders.extend(orders)

                # Pagination: if next is 0 or no more orders, stop
                next_cursor = data.get("next", 0)
                if not orders or next_cursor == 0:
                    break

    except Exception as e:
        print(f"[WB API] Error fetching orders: {e}")

    return all_orders


def fetch_order_statuses(api_token: str, order_ids: list[int]) -> list[dict]:
    """POST /api/v3/orders/status — batch query order statuses.

    Request: {"orders": [id1, id2, ...]}  (max 1000)
    Response: {"orders": [{"id": ..., "supplierStatus": "...", "wbStatus": "..."}]}
    """
    if not order_ids:
        return []

    url = f"{MARKETPLACE_API}/api/v3/orders/status"
    all_statuses = []

    try:
        with httpx.Client(timeout=30) as client:
            # Process in batches of 1000
            for i in range(0, len(order_ids), 1000):
                batch = order_ids[i:i + 1000]
                _throttle()
                resp = client.post(url, headers=_headers(api_token), json={"orders": batch})
                resp.raise_for_status()
                data = resp.json()
                all_statuses.extend(data.get("orders", []))
    except Exception as e:
        print(f"[WB API] Error fetching order statuses: {e}")

    return all_statuses


def fetch_warehouses(api_token: str) -> list[dict]:
    """GET /api/v3/warehouses — get seller's FBS warehouses.

    Response: [{"id": 123, "name": "My Warehouse", ...}]
    """
    url = f"{MARKETPLACE_API}/api/v3/warehouses"
    try:
        _throttle()
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=_headers(api_token))
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[WB API] Error fetching warehouses: {e}")
        return []


def fetch_stocks(api_token: str, warehouse_id: int, skus: list[str]) -> list[dict]:
    """POST /api/v3/stocks/{warehouseId} — query stock for specific SKUs.

    Request: {"skus": ["barcode1", "barcode2"]}
    Response: {"stocks": [{"sku": "...", "amount": 10}]}
    """
    if not skus:
        return []

    url = f"{MARKETPLACE_API}/api/v3/stocks/{warehouse_id}"
    all_stocks = []

    try:
        with httpx.Client(timeout=30) as client:
            # Process in batches of 1000
            for i in range(0, len(skus), 1000):
                batch = skus[i:i + 1000]
                _throttle()
                resp = client.post(url, headers=_headers(api_token), json={"skus": batch})
                resp.raise_for_status()
                data = resp.json()
                for stock in data.get("stocks", []):
                    stock["warehouseId"] = warehouse_id
                all_stocks.extend(data.get("stocks", []))
    except Exception as e:
        print(f"[WB API] Error fetching stocks for warehouse {warehouse_id}: {e}")

    return all_stocks


def fetch_cards(api_token: str) -> list[dict]:
    """POST /content/v2/get/cards/list — fetch product cards for names/photos.

    This uses the content API to get product info (nmID, title, photos, etc.)
    """
    url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
    all_cards = []
    cursor = {"limit": 100}

    try:
        with httpx.Client(timeout=30) as client:
            while True:
                _throttle()
                body = {"settings": {"cursor": cursor, "filter": {"withPhoto": -1}}}
                resp = client.post(url, headers=_headers(api_token), json=body)
                resp.raise_for_status()
                data = resp.json()

                cards = data.get("cards", [])
                all_cards.extend(cards)

                cursor_resp = data.get("cursor", {})
                if not cards or cursor_resp.get("total", 0) < cursor.get("limit", 100):
                    break
                cursor = {
                    "limit": 100,
                    "updatedAt": cursor_resp.get("updatedAt"),
                    "nmID": cursor_resp.get("nmID"),
                }
    except Exception as e:
        print(f"[WB API] Error fetching cards: {e}")

    return all_cards
