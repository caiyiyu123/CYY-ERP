from app.models.user import User
from app.utils.security import hash_password


def _get_admin_token(client, db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    db.add(user)
    db.commit()
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_shop(client, db):
    token = _get_admin_token(client, db)
    resp = client.post("/api/shops", json={
        "name": "本土店A", "type": "local", "api_token": "test_wb_token_123"
    }, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "本土店A"
    assert data["type"] == "local"
    assert "api_token" not in data


def test_list_shops(client, db):
    token = _get_admin_token(client, db)
    client.post("/api/shops", json={"name": "店铺A", "type": "local", "api_token": "tok1"}, headers=_auth(token))
    client.post("/api/shops", json={"name": "店铺B", "type": "cross_border", "api_token": "tok2"}, headers=_auth(token))
    resp = client.get("/api/shops", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_shop(client, db):
    token = _get_admin_token(client, db)
    create = client.post("/api/shops", json={"name": "店铺A", "type": "local", "api_token": "tok"}, headers=_auth(token))
    shop_id = create.json()["id"]
    resp = client.put(f"/api/shops/{shop_id}", json={"name": "店铺A-改名"}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "店铺A-改名"


def test_delete_shop(client, db):
    token = _get_admin_token(client, db)
    create = client.post("/api/shops", json={"name": "店铺A", "type": "local", "api_token": "tok"}, headers=_auth(token))
    shop_id = create.json()["id"]
    resp = client.delete(f"/api/shops/{shop_id}", headers=_auth(token))
    assert resp.status_code == 200
