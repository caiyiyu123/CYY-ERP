from app.models.user import User
from app.utils.security import hash_password


def _create_admin(db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    db.add(user)
    db.commit()
    return user


def test_login_success(client, db):
    _create_admin(db)
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, db):
    _create_admin(db)
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/auth/login", data={"username": "nobody", "password": "pass"})
    assert resp.status_code == 401


def test_get_current_user(client, db):
    _create_admin(db)
    login = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    token = login.json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_access_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
