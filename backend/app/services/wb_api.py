import httpx
from typing import Optional
from datetime import datetime

WB_API_BASE = "https://marketplace-api.wildberries.ru"


def _headers(api_token: str) -> dict:
    return {"Authorization": api_token, "Content-Type": "application/json"}


def fetch_orders(api_token: str, date_from: Optional[datetime] = None) -> list[dict]:
    url = f"{WB_API_BASE}/api/v3/orders"
    params = {"limit": 1000, "next": 0}
    if date_from:
        params["dateFrom"] = int(date_from.timestamp())
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=_headers(api_token), params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("orders", [])
    except Exception as e:
        print(f"[WB API] Error fetching orders: {e}")
        return []


def fetch_stocks(api_token: str) -> list[dict]:
    url = f"{WB_API_BASE}/api/v3/stocks/{0}"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=_headers(api_token), json={"skus": []})
            resp.raise_for_status()
            return resp.json().get("stocks", [])
    except Exception as e:
        print(f"[WB API] Error fetching stocks: {e}")
        return []
