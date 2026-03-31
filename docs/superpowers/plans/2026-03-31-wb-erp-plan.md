# Wildberries ERP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建本地运行的 Wildberries 订单管理 ERP 系统，支持多店铺、多用户、自动 API 同步。

**Architecture:** FastAPI 后端提供 REST API + JWT 认证，Vue 3 前端 SPA 通过 Element Plus 渲染 UI。SQLite 存储数据，APScheduler 定时抓取 WB API。前后端分离开发，生产模式下前端构建产物由 FastAPI 静态文件服务。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, APScheduler, Vue 3, Element Plus, Pinia, ECharts, Vite

**Spec:** `docs/superpowers/specs/2026-03-31-wb-erp-design.md`

---

## Phase 1: 后端基础设施

### Task 1: 后端项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
pydantic[email]==2.9.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
cryptography==43.0.0
python-multipart==0.0.12
apscheduler==3.10.4
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

- [ ] **Step 2: 创建 config.py**

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "wb-erp-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

FERNET_KEY = "wb-erp-fernet-key-must-be-32-bytes="

DATABASE_URL = f"sqlite:///{BASE_DIR / 'wb_erp.db'}"

UPLOAD_DIR = BASE_DIR / "app" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SYNC_INTERVAL_MINUTES = 30
```

- [ ] **Step 3: 创建 database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 创建 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_DIR
from app.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WB-ERP", description="Wildberries 订单管理系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 5: 创建 conftest.py 测试基础设施**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_wb_erp.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 6: 创建 __init__.py 文件**

创建空文件 `backend/app/__init__.py` 和 `backend/tests/__init__.py`。

- [ ] **Step 7: 验证项目启动**

Run: `cd backend && pip install -r requirements.txt && python -m pytest tests/ -v`
Expected: 0 tests collected, no import errors

- [ ] **Step 8: 提交**

```bash
git add backend/
git commit -m "feat: initialize backend project with FastAPI, SQLAlchemy, test infrastructure"
```

---

### Task 2: 数据库模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/shop.py`
- Create: `backend/app/models/product.py`
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/inventory.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: 编写模型测试**

```python
# backend/tests/test_models.py
from datetime import datetime
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product, SkuMapping
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory


def test_create_user(db):
    user = User(username="admin", password_hash="hashed", role="admin", is_active=True)
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.username == "admin"
    assert user.role == "admin"


def test_create_shop(db):
    shop = Shop(name="本土店A", type="local", api_token="encrypted_token", is_active=True)
    db.add(shop)
    db.commit()
    assert shop.id is not None
    assert shop.type == "local"


def test_create_product(db):
    product = Product(
        sku="SYS-001", name="测试商品", image="",
        purchase_price=100.0, weight=500, length=30, width=20, height=10,
    )
    db.add(product)
    db.commit()
    assert product.id is not None
    assert product.sku == "SYS-001"


def test_sku_mapping(db):
    shop = Shop(name="店铺A", type="local", api_token="token", is_active=True)
    product = Product(sku="SYS-001", name="商品A", purchase_price=50.0, weight=100, length=10, width=10, height=10)
    db.add_all([shop, product])
    db.commit()

    mapping = SkuMapping(shop_id=shop.id, shop_sku="WB-SKU-001", product_id=product.id, wb_product_name="WB商品A", wb_barcode="123456")
    db.add(mapping)
    db.commit()
    assert mapping.id is not None
    assert mapping.product_id == product.id


def test_create_order_with_items(db):
    shop = Shop(name="店铺A", type="local", api_token="token", is_active=True)
    db.add(shop)
    db.commit()

    order = Order(
        wb_order_id="WB-ORD-001", shop_id=shop.id, order_type="FBS",
        status="pending", total_price=2350.0, currency="RUB",
    )
    db.add(order)
    db.commit()

    item = OrderItem(
        order_id=order.id, wb_product_id="WB-P-001", product_name="鞋子",
        sku="WB-SKU-001", barcode="123", quantity=1, price=2350.0,
        commission=235.0, logistics_cost=150.0,
    )
    db.add(item)
    db.commit()
    assert len(order.items) == 1


def test_create_inventory(db):
    shop = Shop(name="店铺A", type="local", api_token="token", is_active=True)
    db.add(shop)
    db.commit()

    inv = Inventory(
        shop_id=shop.id, wb_product_id="WB-P-001", product_name="鞋子",
        sku="WB-SKU-001", barcode="123", stock_fbs=50, stock_fbw=30,
        low_stock_threshold=10,
    )
    db.add(inv)
    db.commit()
    assert inv.stock_fbs == 50
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL — modules not found

- [ ] **Step 3: 创建 User 模型**

```python
# backend/app/models/user.py
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # admin/operator/viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: 创建 Shop 模型**

```python
# backend/app/models/shop.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))  # cross_border / local
    api_token: Mapped[str] = mapped_column(String(500))  # Fernet encrypted
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 5: 创建 Product 和 SkuMapping 模型**

```python
# backend/app/models/product.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    image: Mapped[str] = mapped_column(String(500), default="")
    purchase_price: Mapped[float] = mapped_column(Float, default=0.0)
    weight: Mapped[float] = mapped_column(Float, default=0.0)  # grams
    length: Mapped[float] = mapped_column(Float, default=0.0)  # cm
    width: Mapped[float] = mapped_column(Float, default=0.0)   # cm
    height: Mapped[float] = mapped_column(Float, default=0.0)  # cm
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sku_mappings: Mapped[list["SkuMapping"]] = relationship(back_populates="product")


class SkuMapping(Base):
    __tablename__ = "sku_mappings"
    __table_args__ = (UniqueConstraint("shop_id", "shop_sku", name="uq_shop_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(Integer, ForeignKey("shops.id"))
    shop_sku: Mapped[str] = mapped_column(String(200))
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)
    wb_product_name: Mapped[str] = mapped_column(String(500), default="")
    wb_barcode: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product: Mapped[Optional["Product"]] = relationship(back_populates="sku_mappings")
```

- [ ] **Step 6: 创建 Order, OrderItem, OrderStatusLog 模型**

```python
# backend/app/models/order.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    wb_order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    shop_id: Mapped[int] = mapped_column(Integer, ForeignKey("shops.id"))
    order_type: Mapped[str] = mapped_column(String(10))  # FBS / FBW
    status: Mapped[str] = mapped_column(String(50), default="pending")
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    customer_name: Mapped[str] = mapped_column(String(200), default="")
    delivery_address: Mapped[str] = mapped_column(Text, default="")
    warehouse_name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", lazy="selectin")
    status_logs: Mapped[list["OrderStatusLog"]] = relationship(back_populates="order", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    wb_product_id: Mapped[str] = mapped_column(String(100), default="")
    product_name: Mapped[str] = mapped_column(String(500), default="")
    sku: Mapped[str] = mapped_column(String(200), default="")
    barcode: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    logistics_cost: Mapped[float] = mapped_column(Float, default=0.0)

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusLog(Base):
    __tablename__ = "order_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(50))
    wb_status: Mapped[str] = mapped_column(String(100), default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str] = mapped_column(Text, default="")

    order: Mapped["Order"] = relationship(back_populates="status_logs")
```

- [ ] **Step 7: 创建 Inventory 模型**

```python
# backend/app/models/inventory.py
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Inventory(Base):
    __tablename__ = "inventories"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(Integer, ForeignKey("shops.id"))
    wb_product_id: Mapped[str] = mapped_column(String(100), default="")
    product_name: Mapped[str] = mapped_column(String(500), default="")
    sku: Mapped[str] = mapped_column(String(200), default="")
    barcode: Mapped[str] = mapped_column(String(100), default="")
    stock_fbs: Mapped[int] = mapped_column(Integer, default=0)
    stock_fbw: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 8: 创建 models/__init__.py 导出所有模型**

```python
# backend/app/models/__init__.py
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product, SkuMapping
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory

__all__ = ["User", "Shop", "Product", "SkuMapping", "Order", "OrderItem", "OrderStatusLog", "Inventory"]
```

- [ ] **Step 9: 更新 main.py 导入模型**

在 `main.py` 的 `Base.metadata.create_all` 之前添加：

```python
import app.models  # noqa: F401 — ensure all models are registered
```

- [ ] **Step 10: 运行测试**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: 6 passed

- [ ] **Step 11: 提交**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat: add all database models — User, Shop, Product, SkuMapping, Order, OrderItem, OrderStatusLog, Inventory"
```

---

### Task 3: 安全工具 (JWT + bcrypt + Fernet)

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: 编写安全工具测试**

```python
# backend/tests/test_security.py
from app.utils.security import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
    encrypt_token, decrypt_token,
)


def test_password_hash_and_verify():
    password = "test_password_123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_create_and_decode():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_jwt_invalid_token():
    payload = decode_access_token("invalid.token.here")
    assert payload is None


def test_fernet_encrypt_decrypt():
    original = "wb_api_token_abc123"
    encrypted = encrypt_token(original)
    assert encrypted != original
    decrypted = decrypt_token(encrypted)
    assert decrypted == original
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: 实现 security.py**

```python
# backend/app/utils/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import hashlib

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, FERNET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Derive a valid Fernet key from our secret
_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(FERNET_KEY.encode()).digest())
_fernet = Fernet(_fernet_key)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def encrypt_token(plain_text: str) -> str:
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_token(encrypted_text: str) -> str:
    return _fernet.decrypt(encrypted_text.encode()).decode()
```

- [ ] **Step 4: 创建空 __init__.py**

创建空文件 `backend/app/utils/__init__.py`。

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: 4 passed

- [ ] **Step 6: 提交**

```bash
git add backend/app/utils/ backend/tests/test_security.py
git commit -m "feat: add security utilities — JWT, bcrypt password hashing, Fernet encryption"
```

---

### Task 4: 认证依赖与权限控制

**Files:**
- Create: `backend/app/utils/deps.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: 编写认证 API 测试**

```python
# backend/tests/test_auth.py
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 auth schema**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True
```

创建空文件 `backend/app/schemas/__init__.py`。

- [ ] **Step 4: 创建 deps.py 权限依赖**

```python
# backend/app/utils/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(*roles: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return role_checker
```

- [ ] **Step 5: 创建 auth 路由**

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserOut
from app.utils.security import verify_password, create_access_token
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token(data={"sub": user.username, "role": user.role})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

创建空文件 `backend/app/routers/__init__.py`。

- [ ] **Step 6: 在 main.py 注册路由**

在 `main.py` 中添加：

```python
from app.routers import auth
app.include_router(auth.router)
```

- [ ] **Step 7: 运行测试**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: 5 passed

- [ ] **Step 8: 提交**

```bash
git add backend/app/schemas/ backend/app/utils/deps.py backend/app/routers/ backend/tests/test_auth.py backend/app/main.py
git commit -m "feat: add JWT authentication — login, current user, role-based access control"
```

---

### Task 5: 用户管理 API

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/routers/users.py`
- Create: `backend/tests/test_users.py`

- [ ] **Step 1: 编写用户管理测试**

```python
# backend/tests/test_users.py
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


def test_list_users(client, db):
    token = _get_admin_token(client, db)
    resp = client.get("/api/users", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_user(client, db):
    token = _get_admin_token(client, db)
    resp = client.post("/api/users", json={
        "username": "operator1", "password": "pass123", "role": "operator"
    }, headers=_auth(token))
    assert resp.status_code == 201
    assert resp.json()["username"] == "operator1"


def test_create_duplicate_user(client, db):
    token = _get_admin_token(client, db)
    client.post("/api/users", json={"username": "op1", "password": "pass", "role": "operator"}, headers=_auth(token))
    resp = client.post("/api/users", json={"username": "op1", "password": "pass", "role": "operator"}, headers=_auth(token))
    assert resp.status_code == 400


def test_update_user(client, db):
    token = _get_admin_token(client, db)
    create = client.post("/api/users", json={"username": "op1", "password": "pass", "role": "operator"}, headers=_auth(token))
    user_id = create.json()["id"]
    resp = client.put(f"/api/users/{user_id}", json={"role": "viewer"}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


def test_delete_user(client, db):
    token = _get_admin_token(client, db)
    create = client.post("/api/users", json={"username": "op1", "password": "pass", "role": "operator"}, headers=_auth(token))
    user_id = create.json()["id"]
    resp = client.delete(f"/api/users/{user_id}", headers=_auth(token))
    assert resp.status_code == 200


def test_non_admin_cannot_manage_users(client, db):
    token = _get_admin_token(client, db)
    client.post("/api/users", json={"username": "viewer1", "password": "pass", "role": "viewer"}, headers=_auth(token))
    viewer_login = client.post("/api/auth/login", data={"username": "viewer1", "password": "pass"})
    viewer_token = viewer_login.json()["access_token"]
    resp = client.get("/api/users", headers=_auth(viewer_token))
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_users.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 user schema**

```python
# backend/app/schemas/user.py
from typing import Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
```

- [ ] **Step 4: 创建 users 路由**

```python
# backend/app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import hash_password
from app.utils.deps import require_role

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return db.query(User).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.username is not None:
        user.username = data.username
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}
```

- [ ] **Step 5: 在 main.py 注册路由**

```python
from app.routers import auth, users
app.include_router(users.router)
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_users.py -v`
Expected: 6 passed

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/user.py backend/app/routers/users.py backend/tests/test_users.py backend/app/main.py
git commit -m "feat: add user management API — CRUD with admin-only access"
```

---

### Task 6: 店铺管理 API

**Files:**
- Create: `backend/app/schemas/shop.py`
- Create: `backend/app/routers/shops.py`
- Create: `backend/tests/test_shops.py`

- [ ] **Step 1: 编写店铺管理测试**

```python
# backend/tests/test_shops.py
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
    assert "api_token" not in data  # token should not be exposed


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_shops.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 shop schema**

```python
# backend/app/schemas/shop.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ShopCreate(BaseModel):
    name: str
    type: str  # cross_border / local
    api_token: str


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    api_token: Optional[str] = None
    is_active: Optional[bool] = None


class ShopOut(BaseModel):
    id: int
    name: str
    type: str
    is_active: bool
    last_sync_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 创建 shops 路由**

```python
# backend/app/routers/shops.py
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
    shop = Shop(
        name=data.name,
        type=data.type,
        api_token=encrypt_token(data.api_token),
    )
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
```

- [ ] **Step 5: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops
app.include_router(shops.router)
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_shops.py -v`
Expected: 4 passed

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/shop.py backend/app/routers/shops.py backend/tests/test_shops.py backend/app/main.py
git commit -m "feat: add shop management API — CRUD with encrypted API token storage"
```

---

### Task 7: 商品管理 API

**Files:**
- Create: `backend/app/schemas/product.py`
- Create: `backend/app/routers/products.py`
- Create: `backend/tests/test_products.py`

- [ ] **Step 1: 编写商品管理测试**

```python
# backend/tests/test_products.py
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


def test_create_product(client, db):
    token = _get_admin_token(client, db)
    resp = client.post("/api/products", json={
        "sku": "SYS-001", "name": "运动鞋", "purchase_price": 150.0,
        "weight": 800, "length": 35, "width": 25, "height": 15,
    }, headers=_auth(token))
    assert resp.status_code == 201
    assert resp.json()["sku"] == "SYS-001"


def test_list_products(client, db):
    token = _get_admin_token(client, db)
    client.post("/api/products", json={"sku": "SYS-001", "name": "商品A", "purchase_price": 100}, headers=_auth(token))
    client.post("/api/products", json={"sku": "SYS-002", "name": "商品B", "purchase_price": 200}, headers=_auth(token))
    resp = client.get("/api/products", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_product(client, db):
    token = _get_admin_token(client, db)
    create = client.post("/api/products", json={"sku": "SYS-001", "name": "商品A", "purchase_price": 100}, headers=_auth(token))
    pid = create.json()["id"]
    resp = client.put(f"/api/products/{pid}", json={"purchase_price": 180.0}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["purchase_price"] == 180.0


def test_delete_product(client, db):
    token = _get_admin_token(client, db)
    create = client.post("/api/products", json={"sku": "SYS-001", "name": "商品A", "purchase_price": 100}, headers=_auth(token))
    pid = create.json()["id"]
    resp = client.delete(f"/api/products/{pid}", headers=_auth(token))
    assert resp.status_code == 200


def test_duplicate_sku_rejected(client, db):
    token = _get_admin_token(client, db)
    client.post("/api/products", json={"sku": "SYS-001", "name": "A", "purchase_price": 100}, headers=_auth(token))
    resp = client.post("/api/products", json={"sku": "SYS-001", "name": "B", "purchase_price": 200}, headers=_auth(token))
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_products.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 product schema**

```python
# backend/app/schemas/product.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ProductCreate(BaseModel):
    sku: str
    name: str = ""
    purchase_price: float = 0.0
    weight: float = 0.0
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    name: Optional[str] = None
    purchase_price: Optional[float] = None
    weight: Optional[float] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    image: str
    purchase_price: float
    weight: float
    length: float
    width: float
    height: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 创建 products 路由**

```python
# backend/app/routers/products.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
import shutil
import uuid

from app.config import UPLOAD_DIR
from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut
from app.utils.deps import get_current_user, require_role

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Product).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: Session = Depends(get_db), _=Depends(require_role("admin", "operator"))):
    if db.query(Product).filter(Product.sku == data.sku).first():
        raise HTTPException(status_code=400, detail="SKU already exists")
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin", "operator"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"detail": "Product deleted"}


@router.post("/{product_id}/image", response_model=ProductOut)
def upload_product_image(product_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), _=Depends(require_role("admin", "operator"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    product.image = f"/uploads/{filename}"
    db.commit()
    db.refresh(product)
    return product
```

- [ ] **Step 5: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops, products
app.include_router(products.router)
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_products.py -v`
Expected: 5 passed

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/product.py backend/app/routers/products.py backend/tests/test_products.py backend/app/main.py
git commit -m "feat: add product management API — CRUD with image upload"
```

---

### Task 8: SKU 关联 API

**Files:**
- Create: `backend/app/schemas/sku_mapping.py`
- Create: `backend/app/routers/sku_mappings.py`
- Create: `backend/tests/test_sku_mappings.py`

- [ ] **Step 1: 编写 SKU 关联测试**

```python
# backend/tests/test_sku_mappings.py
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product, SkuMapping
from app.utils.security import hash_password, encrypt_token


def _setup(client, db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("tok"), is_active=True)
    product = Product(sku="SYS-001", name="商品A", purchase_price=100)
    db.add_all([user, shop, product])
    db.commit()
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"], shop.id, product.id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_list_shop_sku_mappings(client, db):
    token, shop_id, _ = _setup(client, db)
    mapping = SkuMapping(shop_id=shop_id, shop_sku="WB-001", wb_product_name="WB商品", wb_barcode="123")
    db.add(mapping)
    db.commit()
    resp = client.get(f"/api/shops/{shop_id}/sku-mappings", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["shop_sku"] == "WB-001"


def test_update_sku_mapping_link_product(client, db):
    token, shop_id, product_id = _setup(client, db)
    mapping = SkuMapping(shop_id=shop_id, shop_sku="WB-001", wb_product_name="WB商品", wb_barcode="123")
    db.add(mapping)
    db.commit()
    resp = client.put(
        f"/api/sku-mappings/{mapping.id}",
        json={"product_sku": "SYS-001"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["product_id"] == product_id


def test_update_sku_mapping_unlink(client, db):
    token, shop_id, product_id = _setup(client, db)
    mapping = SkuMapping(shop_id=shop_id, shop_sku="WB-001", product_id=product_id, wb_product_name="WB商品", wb_barcode="123")
    db.add(mapping)
    db.commit()
    resp = client.put(
        f"/api/sku-mappings/{mapping.id}",
        json={"product_sku": ""},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["product_id"] is None


def test_link_nonexistent_sku_returns_404(client, db):
    token, shop_id, _ = _setup(client, db)
    mapping = SkuMapping(shop_id=shop_id, shop_sku="WB-001", wb_product_name="WB商品", wb_barcode="123")
    db.add(mapping)
    db.commit()
    resp = client.put(
        f"/api/sku-mappings/{mapping.id}",
        json={"product_sku": "NONEXISTENT"},
        headers=_auth(token),
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_sku_mappings.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 sku_mapping schema**

```python
# backend/app/schemas/sku_mapping.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class SkuMappingOut(BaseModel):
    id: int
    shop_id: int
    shop_sku: str
    product_id: Optional[int] = None
    wb_product_name: str
    wb_barcode: str
    created_at: datetime

    class Config:
        from_attributes = True


class SkuMappingUpdate(BaseModel):
    product_sku: str  # empty string to unlink
```

- [ ] **Step 4: 创建 sku_mappings 路由**

```python
# backend/app/routers/sku_mappings.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import SkuMapping, Product
from app.schemas.sku_mapping import SkuMappingOut, SkuMappingUpdate
from app.utils.deps import get_current_user, require_role

router = APIRouter(tags=["sku-mappings"])


@router.get("/api/shops/{shop_id}/sku-mappings", response_model=list[SkuMappingOut])
def list_shop_sku_mappings(shop_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(SkuMapping).filter(SkuMapping.shop_id == shop_id).all()


@router.put("/api/sku-mappings/{mapping_id}", response_model=SkuMappingOut)
def update_sku_mapping(mapping_id: int, data: SkuMappingUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin", "operator"))):
    mapping = db.query(SkuMapping).filter(SkuMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="SKU mapping not found")

    if data.product_sku == "":
        mapping.product_id = None
    else:
        product = db.query(Product).filter(Product.sku == data.product_sku).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with SKU '{data.product_sku}' not found")
        mapping.product_id = product.id

    db.commit()
    db.refresh(mapping)
    return mapping
```

- [ ] **Step 5: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops, products, sku_mappings
app.include_router(sku_mappings.router)
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_sku_mappings.py -v`
Expected: 4 passed

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/sku_mapping.py backend/app/routers/sku_mappings.py backend/tests/test_sku_mappings.py backend/app/main.py
git commit -m "feat: add SKU mapping API — link shop SKUs to system products"
```

---

### Task 9: 订单管理 API

**Files:**
- Create: `backend/app/schemas/order.py`
- Create: `backend/app/routers/orders.py`
- Create: `backend/tests/test_orders.py`

- [ ] **Step 1: 编写订单管理测试**

```python
# backend/tests/test_orders.py
from app.models.user import User
from app.models.shop import Shop
from app.models.order import Order, OrderItem, OrderStatusLog
from app.utils.security import hash_password, encrypt_token


def _setup(client, db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("tok"), is_active=True)
    db.add_all([user, shop])
    db.commit()

    order = Order(wb_order_id="WB-001", shop_id=shop.id, order_type="FBS", status="pending", total_price=2350.0)
    db.add(order)
    db.commit()

    item = OrderItem(order_id=order.id, product_name="鞋子", sku="WB-SKU-1", quantity=1, price=2350.0, commission=235.0, logistics_cost=150.0)
    log = OrderStatusLog(order_id=order.id, status="pending", wb_status="waiting")
    db.add_all([item, log])
    db.commit()

    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"], shop.id, order.id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_list_orders(client, db):
    token, shop_id, _ = _setup(client, db)
    resp = client.get("/api/orders", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_list_orders_filter_by_type(client, db):
    token, shop_id, _ = _setup(client, db)
    resp = client.get("/api/orders?order_type=FBS", headers=_auth(token))
    assert len(resp.json()["items"]) == 1
    resp = client.get("/api/orders?order_type=FBW", headers=_auth(token))
    assert len(resp.json()["items"]) == 0


def test_list_orders_filter_by_shop(client, db):
    token, shop_id, _ = _setup(client, db)
    resp = client.get(f"/api/orders?shop_id={shop_id}", headers=_auth(token))
    assert len(resp.json()["items"]) == 1
    resp = client.get("/api/orders?shop_id=9999", headers=_auth(token))
    assert len(resp.json()["items"]) == 0


def test_get_order_detail(client, db):
    token, _, order_id = _setup(client, db)
    resp = client.get(f"/api/orders/{order_id}", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["wb_order_id"] == "WB-001"
    assert len(data["items"]) == 1
    assert len(data["status_logs"]) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_orders.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 order schema**

```python
# backend/app/schemas/order.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class OrderItemOut(BaseModel):
    id: int
    wb_product_id: str
    product_name: str
    sku: str
    barcode: str
    quantity: int
    price: float
    commission: float
    logistics_cost: float

    class Config:
        from_attributes = True


class OrderStatusLogOut(BaseModel):
    id: int
    status: str
    wb_status: str
    changed_at: datetime
    note: str

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    wb_order_id: str
    shop_id: int
    order_type: str
    status: str
    total_price: float
    currency: str
    customer_name: str
    warehouse_name: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = []
    status_logs: list[OrderStatusLogOut] = []

    class Config:
        from_attributes = True


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int
```

- [ ] **Step 4: 创建 orders 路由**

```python
# backend/app/routers/orders.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.schemas.order import OrderOut, OrderListOut
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=OrderListOut)
def list_orders(
    shop_id: Optional[int] = Query(None),
    order_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Order)
    if shop_id:
        query = query.filter(Order.shop_id == shop_id)
    if order_type:
        query = query.filter(Order.order_type == order_type)
    if status:
        query = query.filter(Order.status == status)

    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return OrderListOut(items=orders, total=total)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
```

- [ ] **Step 5: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops, products, sku_mappings, orders
app.include_router(orders.router)
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_orders.py -v`
Expected: 4 passed

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/order.py backend/app/routers/orders.py backend/tests/test_orders.py backend/app/main.py
git commit -m "feat: add order management API — list with filters, detail with items and status logs"
```

---

### Task 10: 库存管理 API

**Files:**
- Create: `backend/app/schemas/inventory.py`
- Create: `backend/app/routers/inventory.py`
- Create: `backend/tests/test_inventory.py`

- [ ] **Step 1: 编写库存管理测试**

```python
# backend/tests/test_inventory.py
from app.models.user import User
from app.models.shop import Shop
from app.models.inventory import Inventory
from app.utils.security import hash_password, encrypt_token


def _setup(client, db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("tok"), is_active=True)
    db.add_all([user, shop])
    db.commit()

    inv = Inventory(shop_id=shop.id, product_name="鞋子", sku="WB-SKU-1", stock_fbs=50, stock_fbw=30, low_stock_threshold=10)
    db.add(inv)
    db.commit()

    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"], shop.id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_list_inventory(client, db):
    token, _ = _setup(client, db)
    resp = client.get("/api/inventory", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_inventory_filter_by_shop(client, db):
    token, shop_id = _setup(client, db)
    resp = client.get(f"/api/inventory?shop_id={shop_id}", headers=_auth(token))
    assert len(resp.json()) == 1
    resp = client.get("/api/inventory?shop_id=9999", headers=_auth(token))
    assert len(resp.json()) == 0


def test_low_stock_alerts(client, db):
    token, shop_id = _setup(client, db)
    low = Inventory(shop_id=shop_id, product_name="低库存品", sku="WB-LOW", stock_fbs=3, stock_fbw=2, low_stock_threshold=10)
    db.add(low)
    db.commit()
    resp = client.get("/api/inventory/low-stock", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["sku"] == "WB-LOW"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_inventory.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 inventory schema**

```python
# backend/app/schemas/inventory.py
from datetime import datetime
from pydantic import BaseModel


class InventoryOut(BaseModel):
    id: int
    shop_id: int
    wb_product_id: str
    product_name: str
    sku: str
    barcode: str
    stock_fbs: int
    stock_fbw: int
    low_stock_threshold: int
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 创建 inventory 路由**

```python
# backend/app/routers/inventory.py
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryOut
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryOut])
def list_inventory(
    shop_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Inventory)
    if shop_id:
        query = query.filter(Inventory.shop_id == shop_id)
    return query.all()


@router.get("/low-stock", response_model=list[InventoryOut])
def low_stock_alerts(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Inventory).filter(
        (Inventory.stock_fbs + Inventory.stock_fbw) < Inventory.low_stock_threshold
    ).all()
```

- [ ] **Step 5: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory
app.include_router(inventory.router)
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_inventory.py -v`
Expected: 3 passed

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/inventory.py backend/app/routers/inventory.py backend/tests/test_inventory.py backend/app/main.py
git commit -m "feat: add inventory API — list with shop filter, low stock alerts"
```

---

### Task 11: 财务统计 API

**Files:**
- Create: `backend/app/routers/finance.py`
- Create: `backend/tests/test_finance.py`

- [ ] **Step 1: 编写财务统计测试**

```python
# backend/tests/test_finance.py
from datetime import datetime
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product, SkuMapping
from app.models.order import Order, OrderItem
from app.utils.security import hash_password, encrypt_token


def _setup(client, db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("tok"), is_active=True)
    product = Product(sku="SYS-001", name="鞋子", purchase_price=100.0)
    db.add_all([user, shop, product])
    db.commit()

    mapping = SkuMapping(shop_id=shop.id, shop_sku="WB-SKU-1", product_id=product.id, wb_product_name="鞋子")
    db.add(mapping)
    db.commit()

    order = Order(wb_order_id="WB-001", shop_id=shop.id, order_type="FBS", status="completed", total_price=2350.0)
    db.add(order)
    db.commit()

    item = OrderItem(order_id=order.id, product_name="鞋子", sku="WB-SKU-1", quantity=2, price=1175.0, commission=235.0, logistics_cost=150.0)
    db.add(item)
    db.commit()

    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"], shop.id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_finance_summary(client, db):
    token, _ = _setup(client, db)
    resp = client.get("/api/finance/summary", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sales"] == 2350.0  # 1175 * 2
    assert data["total_commission"] == 235.0
    assert data["total_logistics"] == 150.0
    assert data["total_purchase_cost"] == 200.0  # 100 * 2
    assert data["total_profit"] == 1965.0  # 2350 - 200 - 235 - 150


def test_finance_summary_filter_by_shop(client, db):
    token, shop_id = _setup(client, db)
    resp = client.get(f"/api/finance/summary?shop_id={shop_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total_sales"] == 2350.0
    resp = client.get("/api/finance/summary?shop_id=9999", headers=_auth(token))
    assert resp.json()["total_sales"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_finance.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 finance 路由**

```python
# backend/app/routers/finance.py
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.product import SkuMapping, Product
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/summary")
def finance_summary(
    shop_id: Optional[int] = Query(None),
    order_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(OrderItem).join(Order)
    if shop_id:
        query = query.filter(Order.shop_id == shop_id)
    if order_type:
        query = query.filter(Order.order_type == order_type)

    items = query.all()

    total_sales = sum(i.price * i.quantity for i in items)
    total_commission = sum(i.commission for i in items)
    total_logistics = sum(i.logistics_cost for i in items)

    # Calculate purchase cost via SKU mapping
    total_purchase_cost = 0.0
    for item in items:
        order = db.query(Order).filter(Order.id == item.order_id).first()
        mapping = db.query(SkuMapping).filter(
            SkuMapping.shop_id == order.shop_id,
            SkuMapping.shop_sku == item.sku,
        ).first()
        if mapping and mapping.product_id:
            product = db.query(Product).filter(Product.id == mapping.product_id).first()
            if product:
                total_purchase_cost += product.purchase_price * item.quantity

    total_profit = total_sales - total_purchase_cost - total_commission - total_logistics

    return {
        "total_sales": total_sales,
        "total_commission": total_commission,
        "total_logistics": total_logistics,
        "total_purchase_cost": total_purchase_cost,
        "total_profit": total_profit,
        "order_count": len(set(i.order_id for i in items)),
    }
```

- [ ] **Step 4: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance
app.include_router(finance.router)
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_finance.py -v`
Expected: 2 passed

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/finance.py backend/tests/test_finance.py backend/app/main.py
git commit -m "feat: add finance summary API — sales, commission, logistics, purchase cost, profit"
```

---

### Task 12: 数据看板 API

**Files:**
- Create: `backend/app/routers/dashboard.py`
- Create: `backend/tests/test_dashboard.py`

- [ ] **Step 1: 编写看板 API 测试**

```python
# backend/tests/test_dashboard.py
from datetime import datetime
from app.models.user import User
from app.models.shop import Shop
from app.models.order import Order, OrderItem
from app.models.inventory import Inventory
from app.utils.security import hash_password, encrypt_token


def _setup(client, db):
    user = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("tok"), is_active=True)
    db.add_all([user, shop])
    db.commit()

    order = Order(wb_order_id="WB-001", shop_id=shop.id, order_type="FBS", status="pending", total_price=2350.0)
    db.add(order)
    db.commit()

    item = OrderItem(order_id=order.id, product_name="鞋子", sku="WB-SKU-1", quantity=1, price=2350.0, commission=235.0, logistics_cost=150.0)
    low_inv = Inventory(shop_id=shop.id, product_name="低库存品", sku="WB-LOW", stock_fbs=2, stock_fbw=1, low_stock_threshold=10)
    db.add_all([item, low_inv])
    db.commit()

    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_stats(client, db):
    token = _setup(client, db)
    resp = client.get("/api/dashboard/stats", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["today_orders"] >= 0
    assert data["today_sales"] >= 0
    assert "pending_shipment" in data
    assert "low_stock_count" in data
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_dashboard.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 dashboard 路由**

```python
# backend/app/routers/dashboard.py
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.inventory import Inventory
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    today_orders = db.query(Order).filter(Order.created_at >= today_start).count()
    today_sales_result = (
        db.query(func.coalesce(func.sum(OrderItem.price * OrderItem.quantity), 0))
        .join(Order)
        .filter(Order.created_at >= today_start)
        .scalar()
    )

    pending_shipment = db.query(Order).filter(Order.status == "pending").count()

    low_stock_count = db.query(Inventory).filter(
        (Inventory.stock_fbs + Inventory.stock_fbw) < Inventory.low_stock_threshold
    ).count()

    recent_orders = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "today_orders": today_orders,
        "today_sales": float(today_sales_result),
        "pending_shipment": pending_shipment,
        "low_stock_count": low_stock_count,
        "recent_orders": [
            {
                "id": o.id,
                "wb_order_id": o.wb_order_id,
                "shop_id": o.shop_id,
                "order_type": o.order_type,
                "status": o.status,
                "total_price": o.total_price,
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ],
    }
```

- [ ] **Step 4: 在 main.py 注册路由**

```python
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance, dashboard
app.include_router(dashboard.router)
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_dashboard.py -v`
Expected: 1 passed

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/dashboard.py backend/tests/test_dashboard.py backend/app/main.py
git commit -m "feat: add dashboard stats API — today orders, sales, pending shipment, low stock"
```

---

### Task 13: WB API 对接与数据同步

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/wb_api.py`
- Create: `backend/app/services/sync.py`
- Create: `backend/app/services/scheduler.py`
- Create: `backend/tests/test_sync.py`

- [ ] **Step 1: 编写同步逻辑测试**

```python
# backend/tests/test_sync.py
from unittest.mock import patch, AsyncMock
from datetime import datetime
from app.models.shop import Shop
from app.models.order import Order
from app.models.inventory import Inventory
from app.models.product import SkuMapping
from app.utils.security import encrypt_token
from app.services.sync import sync_shop_orders, sync_shop_inventory


MOCK_WB_ORDERS = [
    {
        "id": 123456,
        "rid": "WB-RID-001",
        "orderType": "fbs",
        "status": 0,
        "totalPrice": 2350,
        "currency": "RUB",
        "address": "Moscow, ul. Lenina 1",
        "warehouseName": "Коледино",
        "createdAt": "2026-03-31T10:00:00Z",
        "skus": ["WB-SKU-001"],
        "products": [
            {"name": "Кроссовки", "sku": "WB-SKU-001", "barcode": "123456", "quantity": 1, "price": 2350, "commission": 235, "logisticsCost": 150}
        ],
    }
]

MOCK_WB_STOCKS = [
    {"sku": "WB-SKU-001", "name": "Кроссовки", "barcode": "123456", "stock": 50, "warehouseId": 1, "warehouseName": "FBS"},
    {"sku": "WB-SKU-001", "name": "Кроссовки", "barcode": "123456", "stock": 30, "warehouseId": 2, "warehouseName": "FBW"},
]


def test_sync_shop_orders(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()

    with patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS):
        sync_shop_orders(db, shop)

    orders = db.query(Order).all()
    assert len(orders) == 1
    assert orders[0].wb_order_id == "123456"
    assert orders[0].order_type == "FBS"

    # Second sync should not duplicate
    with patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS):
        sync_shop_orders(db, shop)
    assert db.query(Order).count() == 1


def test_sync_shop_inventory(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()

    with patch("app.services.sync.fetch_stocks", return_value=MOCK_WB_STOCKS):
        sync_shop_inventory(db, shop)

    inv = db.query(Inventory).filter(Inventory.sku == "WB-SKU-001").first()
    assert inv is not None
    assert inv.stock_fbs == 50
    assert inv.stock_fbw == 30


def test_sync_creates_sku_mappings(db):
    shop = Shop(name="店铺A", type="local", api_token=encrypt_token("test_token"), is_active=True)
    db.add(shop)
    db.commit()

    with patch("app.services.sync.fetch_orders", return_value=MOCK_WB_ORDERS):
        sync_shop_orders(db, shop)

    mapping = db.query(SkuMapping).filter(SkuMapping.shop_sku == "WB-SKU-001").first()
    assert mapping is not None
    assert mapping.shop_id == shop.id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_sync.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 wb_api.py — WB API 客户端**

```python
# backend/app/services/wb_api.py
import httpx
from typing import Optional
from datetime import datetime

WB_API_BASE = "https://marketplace-api.wildberries.ru"


def _headers(api_token: str) -> dict:
    return {"Authorization": api_token, "Content-Type": "application/json"}


def fetch_orders(api_token: str, date_from: Optional[datetime] = None) -> list[dict]:
    """Fetch orders from WB API. Returns list of order dicts."""
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
    """Fetch warehouse stocks from WB API."""
    url = f"{WB_API_BASE}/api/v3/stocks/{0}"  # warehouseId=0 for all
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=_headers(api_token), json={"skus": []})
            resp.raise_for_status()
            return resp.json().get("stocks", [])
    except Exception as e:
        print(f"[WB API] Error fetching stocks: {e}")
        return []
```

- [ ] **Step 4: 创建 sync.py — 同步逻辑**

```python
# backend/app/services/sync.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.shop import Shop
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory
from app.models.product import SkuMapping
from app.utils.security import decrypt_token
from app.services.wb_api import fetch_orders, fetch_stocks

WB_STATUS_MAP = {
    0: "pending",
    1: "pending",
    2: "shipped",
    3: "in_transit",
    5: "completed",
    6: "cancelled",
    7: "returned",
}


def sync_shop_orders(db: Session, shop: Shop):
    """Sync orders for a single shop from WB API."""
    api_token = decrypt_token(shop.api_token)
    raw_orders = fetch_orders(api_token, date_from=shop.last_sync_at)

    for raw in raw_orders:
        wb_order_id = str(raw.get("id", ""))
        existing = db.query(Order).filter(Order.wb_order_id == wb_order_id).first()
        if existing:
            # Update status if changed
            new_status = WB_STATUS_MAP.get(raw.get("status", 0), "pending")
            if existing.status != new_status:
                existing.status = new_status
                existing.updated_at = datetime.now(timezone.utc)
                log = OrderStatusLog(
                    order_id=existing.id,
                    status=new_status,
                    wb_status=str(raw.get("status", "")),
                )
                db.add(log)
            continue

        order_type = raw.get("orderType", "fbs").upper()
        status = WB_STATUS_MAP.get(raw.get("status", 0), "pending")

        order = Order(
            wb_order_id=wb_order_id,
            shop_id=shop.id,
            order_type=order_type,
            status=status,
            total_price=raw.get("totalPrice", 0),
            currency=raw.get("currency", "RUB"),
            delivery_address=raw.get("address", ""),
            warehouse_name=raw.get("warehouseName", ""),
        )
        db.add(order)
        db.flush()

        log = OrderStatusLog(order_id=order.id, status=status, wb_status=str(raw.get("status", "")))
        db.add(log)

        for p in raw.get("products", []):
            item = OrderItem(
                order_id=order.id,
                product_name=p.get("name", ""),
                sku=p.get("sku", ""),
                barcode=p.get("barcode", ""),
                quantity=p.get("quantity", 1),
                price=p.get("price", 0),
                commission=p.get("commission", 0),
                logistics_cost=p.get("logisticsCost", 0),
            )
            db.add(item)

            # Auto-create SKU mapping if not exists
            sku = p.get("sku", "")
            if sku:
                existing_mapping = db.query(SkuMapping).filter(
                    SkuMapping.shop_id == shop.id, SkuMapping.shop_sku == sku
                ).first()
                if not existing_mapping:
                    mapping = SkuMapping(
                        shop_id=shop.id,
                        shop_sku=sku,
                        wb_product_name=p.get("name", ""),
                        wb_barcode=p.get("barcode", ""),
                    )
                    db.add(mapping)

    shop.last_sync_at = datetime.now(timezone.utc)
    db.commit()


def sync_shop_inventory(db: Session, shop: Shop):
    """Sync inventory for a single shop from WB API."""
    api_token = decrypt_token(shop.api_token)
    stocks = fetch_stocks(api_token)

    # Group by SKU
    sku_stocks: dict[str, dict] = {}
    for s in stocks:
        sku = s.get("sku", "")
        if sku not in sku_stocks:
            sku_stocks[sku] = {"name": s.get("name", ""), "barcode": s.get("barcode", ""), "fbs": 0, "fbw": 0}
        wh_name = s.get("warehouseName", "")
        if "FBW" in wh_name.upper() or s.get("warehouseId", 0) >= 100:
            sku_stocks[sku]["fbw"] += s.get("stock", 0)
        else:
            sku_stocks[sku]["fbs"] += s.get("stock", 0)

    for sku, data in sku_stocks.items():
        inv = db.query(Inventory).filter(
            Inventory.shop_id == shop.id, Inventory.sku == sku
        ).first()
        if inv:
            inv.stock_fbs = data["fbs"]
            inv.stock_fbw = data["fbw"]
            inv.updated_at = datetime.now(timezone.utc)
        else:
            inv = Inventory(
                shop_id=shop.id,
                product_name=data["name"],
                sku=sku,
                barcode=data["barcode"],
                stock_fbs=data["fbs"],
                stock_fbw=data["fbw"],
            )
            db.add(inv)

    db.commit()
```

- [ ] **Step 5: 创建 scheduler.py — 定时任务**

```python
# backend/app/services/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models.shop import Shop
from app.services.sync import sync_shop_orders, sync_shop_inventory
from app.config import SYNC_INTERVAL_MINUTES

scheduler = BackgroundScheduler()


def sync_all_shops():
    """Sync orders and inventory for all active shops."""
    db = SessionLocal()
    try:
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        for shop in shops:
            try:
                sync_shop_orders(db, shop)
                sync_shop_inventory(db, shop)
                print(f"[Scheduler] Synced shop: {shop.name}")
            except Exception as e:
                print(f"[Scheduler] Error syncing shop {shop.name}: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(sync_all_shops, "interval", minutes=SYNC_INTERVAL_MINUTES, id="sync_all")
    scheduler.start()
    print(f"[Scheduler] Started — syncing every {SYNC_INTERVAL_MINUTES} minutes")


def stop_scheduler():
    scheduler.shutdown(wait=False)
```

- [ ] **Step 6: 创建空 services/__init__.py**

创建空文件 `backend/app/services/__init__.py`。

- [ ] **Step 7: 添加手动同步 API 到 shops 路由**

在 `backend/app/routers/shops.py` 底部添加：

```python
from app.services.sync import sync_shop_orders, sync_shop_inventory

@router.post("/{shop_id}/sync")
def trigger_sync(shop_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "operator"))):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    try:
        sync_shop_orders(db, shop)
        sync_shop_inventory(db, shop)
        return {"detail": f"Sync completed for {shop.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
```

- [ ] **Step 8: 在 main.py 启动调度器**

在 `main.py` 添加：

```python
from contextlib import asynccontextmanager
from app.services.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    yield
    stop_scheduler()

# Update FastAPI initialization:
app = FastAPI(title="WB-ERP", description="Wildberries 订单管理系统", lifespan=lifespan)
```

- [ ] **Step 9: 运行测试**

Run: `cd backend && python -m pytest tests/test_sync.py -v`
Expected: 3 passed

- [ ] **Step 10: 运行全部测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 11: 提交**

```bash
git add backend/app/services/ backend/app/routers/shops.py backend/app/main.py backend/tests/test_sync.py
git commit -m "feat: add WB API sync — order/inventory sync, scheduler, manual trigger"
```

---

### Task 14: 初始管理员创建脚本

**Files:**
- Create: `backend/create_admin.py`

- [ ] **Step 1: 创建脚本**

```python
# backend/create_admin.py
"""Create initial admin user."""
from app.database import SessionLocal, Base, engine
from app.models.user import User
from app.utils.security import hash_password
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)

db = SessionLocal()
if not db.query(User).filter(User.username == "admin").first():
    admin = User(username="admin", password_hash=hash_password("admin123"), role="admin", is_active=True)
    db.add(admin)
    db.commit()
    print("Admin user created: admin / admin123")
else:
    print("Admin user already exists")
db.close()
```

- [ ] **Step 2: 提交**

```bash
git add backend/create_admin.py
git commit -m "feat: add initial admin creation script"
```

---

## Phase 2: 前端

### Task 15: 前端项目初始化

**Files:**
- Create: `frontend/` (via Vite scaffolding)
- Modify: `frontend/vite.config.js`
- Create: `frontend/src/api/index.js`

- [ ] **Step 1: 创建 Vue 项目**

Run: `cd /c/Users/caiyi/Desktop/wb-erp && npm create vite@latest frontend -- --template vue`

- [ ] **Step 2: 安装依赖**

Run: `cd frontend && npm install && npm install element-plus @element-plus/icons-vue vue-router@4 pinia axios echarts vue-echarts`

- [ ] **Step 3: 配置 vite.config.js 代理**

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
    }
  }
})
```

- [ ] **Step 4: 创建 API 封装**

```javascript
// frontend/src/api/index.js
import axios from 'axios'

const api = axios.create({ baseURL: '' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
```

- [ ] **Step 5: 提交**

```bash
git add frontend/
git commit -m "feat: initialize Vue 3 frontend with Element Plus, Pinia, ECharts"
```

---

### Task 16: 路由与布局组件

**Files:**
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/views/Layout.vue`
- Create: `frontend/src/views/Login.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: 创建路由**

```javascript
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'orders', name: 'Orders', component: () => import('../views/Orders.vue') },
      { path: 'orders/:id', name: 'OrderDetail', component: () => import('../views/OrderDetail.vue') },
      { path: 'products', name: 'Products', component: () => import('../views/Products.vue') },
      { path: 'finance', name: 'Finance', component: () => import('../views/Finance.vue') },
      { path: 'inventory', name: 'Inventory', component: () => import('../views/Inventory.vue') },
      { path: 'shops', name: 'Shops', component: () => import('../views/Shops.vue') },
      { path: 'shops/:id/sku-mappings', name: 'SkuMappings', component: () => import('../views/SkuMappings.vue') },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue') },
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
```

- [ ] **Step 2: 创建 auth store**

```javascript
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token'))

  async function login(username, password) {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    const { data } = await api.post('/api/auth/login', formData)
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchUser()
  }

  async function fetchUser() {
    const { data } = await api.get('/api/auth/me')
    user.value = data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { user, token, login, fetchUser, logout }
})
```

- [ ] **Step 3: 创建 Layout.vue**

```vue
<!-- frontend/src/views/Layout.vue -->
<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background: #16213e">
      <div style="padding: 16px; color: white; font-size: 1.2em; font-weight: bold; text-align: center; border-bottom: 1px solid #2a3a5e;">
        WB-ERP
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#16213e"
        text-color="#ccc"
        active-text-color="#4fc3f7"
        router
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据看板</span>
        </el-menu-item>
        <el-sub-menu index="orders-sub">
          <template #title>
            <el-icon><Box /></el-icon>
            <span>订单管理</span>
          </template>
          <el-menu-item index="/orders?order_type=FBS">FBS 订单</el-menu-item>
          <el-menu-item index="/orders?order_type=FBW">FBW 订单</el-menu-item>
          <el-menu-item index="/orders">全部订单</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <span>商品管理</span>
        </el-menu-item>
        <el-menu-item index="/finance">
          <el-icon><Money /></el-icon>
          <span>财务统计</span>
        </el-menu-item>
        <el-menu-item index="/inventory">
          <el-icon><List /></el-icon>
          <span>库存管理</span>
        </el-menu-item>
        <el-menu-item index="/shops">
          <el-icon><Shop /></el-icon>
          <span>店铺管理</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.user?.role === 'admin'" index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="background: #1a1a2e; color: white; display: flex; align-items: center; justify-content: flex-end; gap: 16px">
        <span>{{ authStore.user?.username }}</span>
        <el-tag>{{ authStore.user?.role }}</el-tag>
        <el-button text style="color: #ccc" @click="handleLogout">退出</el-button>
      </el-header>
      <el-main style="background: #f0f2f5">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { DataAnalysis, Box, Goods, Money, List, Shop, User } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const router = useRouter()

onMounted(() => {
  if (authStore.token) authStore.fetchUser()
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
```

- [ ] **Step 4: 创建 Login.vue**

```vue
<!-- frontend/src/views/Login.vue -->
<template>
  <div style="display: flex; align-items: center; justify-content: center; height: 100vh; background: #1a1a2e">
    <el-card style="width: 400px">
      <template #header>
        <h2 style="text-align: center; margin: 0">WB-ERP 登录</h2>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()

async function handleLogin() {
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    router.push('/')
  } catch {
    ElMessage.error('用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 5: 更新 main.js**

```javascript
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
```

- [ ] **Step 6: 更新 App.vue**

```vue
<!-- frontend/src/App.vue -->
<template>
  <router-view />
</template>
```

- [ ] **Step 7: 创建占位页面文件**

为每个未实现的页面创建最简占位 Vue 文件（Dashboard.vue, Orders.vue, OrderDetail.vue, Products.vue, Finance.vue, Inventory.vue, Shops.vue, SkuMappings.vue, Users.vue）：

```vue
<template>
  <div>页面建设中...</div>
</template>
```

- [ ] **Step 8: 验证前端启动**

Run: `cd frontend && npm run dev`
Expected: 浏览器可打开 http://localhost:5173/login，看到登录页

- [ ] **Step 9: 提交**

```bash
git add frontend/
git commit -m "feat: add frontend routing, layout, login page with Element Plus"
```

---

### Task 17: 数据看板页面

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: 实现 Dashboard.vue**

```vue
<!-- frontend/src/views/Dashboard.vue -->
<template>
  <div>
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">今日订单</div>
          <div style="font-size: 28px; font-weight: bold">{{ stats.today_orders }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">今日销售额</div>
          <div style="font-size: 28px; font-weight: bold">₽ {{ stats.today_sales?.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">待发货</div>
          <div style="font-size: 28px; font-weight: bold; color: #f57c00">{{ stats.pending_shipment }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 14px">低库存预警</div>
          <div style="font-size: 28px; font-weight: bold; color: #c62828">{{ stats.low_stock_count }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 20px">
      <template #header>最近订单</template>
      <el-table :data="stats.recent_orders" stripe>
        <el-table-column prop="wb_order_id" label="订单号" />
        <el-table-column prop="order_type" label="类型">
          <template #default="{ row }">
            <el-tag :type="row.order_type === 'FBS' ? 'success' : 'primary'" size="small">{{ row.order_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_price" label="金额">
          <template #default="{ row }">₽ {{ row.total_price?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" />
        <el-table-column prop="created_at" label="时间" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const stats = ref({ today_orders: 0, today_sales: 0, pending_shipment: 0, low_stock_count: 0, recent_orders: [] })

onMounted(async () => {
  const { data } = await api.get('/api/dashboard/stats')
  stats.value = data
})
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "feat: add dashboard page — stats cards and recent orders table"
```

---

### Task 18: 订单列表与详情页面

**Files:**
- Modify: `frontend/src/views/Orders.vue`
- Modify: `frontend/src/views/OrderDetail.vue`

- [ ] **Step 1: 实现 Orders.vue**

```vue
<!-- frontend/src/views/Orders.vue -->
<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>订单列表</span>
        <div style="display: flex; gap: 12px">
          <el-select v-model="filters.order_type" placeholder="订单类型" clearable @change="fetchOrders">
            <el-option label="FBS" value="FBS" />
            <el-option label="FBW" value="FBW" />
          </el-select>
          <el-select v-model="filters.status" placeholder="状态" clearable @change="fetchOrders">
            <el-option label="待发货" value="pending" />
            <el-option label="已发货" value="shipped" />
            <el-option label="配送中" value="in_transit" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="已退货" value="returned" />
          </el-select>
        </div>
      </div>
    </template>
    <el-table :data="orders" stripe @row-click="row => $router.push(`/orders/${row.id}`)">
      <el-table-column prop="wb_order_id" label="订单号" />
      <el-table-column prop="order_type" label="类型">
        <template #default="{ row }">
          <el-tag :type="row.order_type === 'FBS' ? 'success' : 'primary'" size="small">{{ row.order_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_price" label="金额">
        <template #default="{ row }">₽ {{ row.total_price?.toLocaleString() }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" />
      <el-table-column prop="warehouse_name" label="仓库" />
      <el-table-column prop="created_at" label="时间" />
    </el-table>
    <el-pagination
      v-model:current-page="page"
      :total="total"
      :page-size="50"
      layout="total, prev, pager, next"
      style="margin-top: 16px"
      @current-change="fetchOrders"
    />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const orders = ref([])
const total = ref(0)
const page = ref(1)
const filters = reactive({
  order_type: route.query.order_type || '',
  status: '',
})

async function fetchOrders() {
  const params = { page: page.value }
  if (filters.order_type) params.order_type = filters.order_type
  if (filters.status) params.status = filters.status
  const { data } = await api.get('/api/orders', { params })
  orders.value = data.items
  total.value = data.total
}

onMounted(fetchOrders)
</script>
```

- [ ] **Step 2: 实现 OrderDetail.vue**

```vue
<!-- frontend/src/views/OrderDetail.vue -->
<template>
  <div v-if="order">
    <el-page-header @back="$router.back()">
      <template #content>订单 {{ order.wb_order_id }}</template>
    </el-page-header>

    <el-descriptions :column="3" border style="margin-top: 20px">
      <el-descriptions-item label="订单号">{{ order.wb_order_id }}</el-descriptions-item>
      <el-descriptions-item label="类型">
        <el-tag :type="order.order_type === 'FBS' ? 'success' : 'primary'">{{ order.order_type }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="状态">{{ order.status }}</el-descriptions-item>
      <el-descriptions-item label="金额">₽ {{ order.total_price?.toLocaleString() }}</el-descriptions-item>
      <el-descriptions-item label="仓库">{{ order.warehouse_name }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ order.created_at }}</el-descriptions-item>
    </el-descriptions>

    <el-card style="margin-top: 20px">
      <template #header>商品明细</template>
      <el-table :data="order.items">
        <el-table-column prop="product_name" label="商品名" />
        <el-table-column prop="sku" label="SKU" />
        <el-table-column prop="quantity" label="数量" />
        <el-table-column prop="price" label="售价">
          <template #default="{ row }">₽ {{ row.price }}</template>
        </el-table-column>
        <el-table-column prop="commission" label="佣金">
          <template #default="{ row }">₽ {{ row.commission }}</template>
        </el-table-column>
        <el-table-column prop="logistics_cost" label="物流费">
          <template #default="{ row }">₽ {{ row.logistics_cost }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>状态时间线</template>
      <el-timeline>
        <el-timeline-item
          v-for="log in order.status_logs"
          :key="log.id"
          :timestamp="log.changed_at"
        >
          {{ log.status }} <span v-if="log.note" style="color: #999">— {{ log.note }}</span>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const order = ref(null)

onMounted(async () => {
  const { data } = await api.get(`/api/orders/${route.params.id}`)
  order.value = data
})
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/Orders.vue frontend/src/views/OrderDetail.vue
git commit -m "feat: add orders list page with filters and order detail page with timeline"
```

---

### Task 19: 商品管理页面

**Files:**
- Modify: `frontend/src/views/Products.vue`

- [ ] **Step 1: 实现 Products.vue**

```vue
<!-- frontend/src/views/Products.vue -->
<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>商品管理</span>
        <el-button type="primary" @click="showDialog = true">添加商品</el-button>
      </div>
    </template>
    <el-table :data="products" stripe>
      <el-table-column label="图片" width="80">
        <template #default="{ row }">
          <el-image v-if="row.image" :src="row.image" style="width: 50px; height: 50px" fit="cover" />
          <span v-else style="color: #ccc">无图</span>
        </template>
      </el-table-column>
      <el-table-column prop="sku" label="SKU" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="purchase_price" label="采购价">
        <template #default="{ row }">¥ {{ row.purchase_price }}</template>
      </el-table-column>
      <el-table-column prop="weight" label="重量(g)" />
      <el-table-column label="尺寸(cm)">
        <template #default="{ row }">{{ row.length }} × {{ row.width }} × {{ row.height }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="editProduct(row)">编辑</el-button>
          <el-upload
            :action="`/api/products/${row.id}/image`"
            :headers="{ Authorization: `Bearer ${token}` }"
            :show-file-list="false"
            @success="fetchProducts"
          >
            <el-button size="small">上传图片</el-button>
          </el-upload>
          <el-popconfirm title="确定删除?" @confirm="deleteProduct(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="showDialog" :title="form.id ? '编辑商品' : '添加商品'" width="500px">
    <el-form :model="form" label-width="80px">
      <el-form-item label="SKU"><el-input v-model="form.sku" /></el-form-item>
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="采购价"><el-input-number v-model="form.purchase_price" :min="0" :precision="2" /></el-form-item>
      <el-form-item label="重量(g)"><el-input-number v-model="form.weight" :min="0" /></el-form-item>
      <el-form-item label="长(cm)"><el-input-number v-model="form.length" :min="0" /></el-form-item>
      <el-form-item label="宽(cm)"><el-input-number v-model="form.width" :min="0" /></el-form-item>
      <el-form-item label="高(cm)"><el-input-number v-model="form.height" :min="0" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showDialog = false">取消</el-button>
      <el-button type="primary" @click="saveProduct">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const products = ref([])
const showDialog = ref(false)
const token = localStorage.getItem('token')
const form = reactive({ id: null, sku: '', name: '', purchase_price: 0, weight: 0, length: 0, width: 0, height: 0 })

async function fetchProducts() {
  const { data } = await api.get('/api/products')
  products.value = data
}

function editProduct(row) {
  Object.assign(form, row)
  showDialog.value = true
}

async function saveProduct() {
  if (form.id) {
    await api.put(`/api/products/${form.id}`, form)
  } else {
    await api.post('/api/products', form)
  }
  showDialog.value = false
  Object.assign(form, { id: null, sku: '', name: '', purchase_price: 0, weight: 0, length: 0, width: 0, height: 0 })
  fetchProducts()
  ElMessage.success('保存成功')
}

async function deleteProduct(id) {
  await api.delete(`/api/products/${id}`)
  fetchProducts()
  ElMessage.success('删除成功')
}

onMounted(fetchProducts)
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/Products.vue
git commit -m "feat: add products page — CRUD with image upload"
```

---

### Task 20: 店铺管理与 SKU 关联页面

**Files:**
- Modify: `frontend/src/views/Shops.vue`
- Modify: `frontend/src/views/SkuMappings.vue`

- [ ] **Step 1: 实现 Shops.vue**

```vue
<!-- frontend/src/views/Shops.vue -->
<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>店铺管理</span>
        <el-button type="primary" @click="showDialog = true">添加店铺</el-button>
      </div>
    </template>
    <el-table :data="shops" stripe>
      <el-table-column prop="name" label="店铺名称" />
      <el-table-column prop="type" label="类型">
        <template #default="{ row }">
          <el-tag :type="row.type === 'local' ? 'success' : 'warning'">{{ row.type === 'local' ? '本土' : '跨境' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_sync_at" label="最后同步" />
      <el-table-column label="操作" width="320">
        <template #default="{ row }">
          <el-button size="small" @click="editShop(row)">编辑</el-button>
          <el-button size="small" type="success" @click="$router.push(`/shops/${row.id}/sku-mappings`)">SKU关联</el-button>
          <el-button size="small" type="warning" :loading="syncing === row.id" @click="syncShop(row.id)">同步</el-button>
          <el-popconfirm title="确定删除?" @confirm="deleteShop(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="showDialog" :title="form.id ? '编辑店铺' : '添加店铺'" width="500px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="店铺名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.type">
          <el-option label="本土" value="local" />
          <el-option label="跨境" value="cross_border" />
        </el-select>
      </el-form-item>
      <el-form-item label="API Token"><el-input v-model="form.api_token" type="password" show-password /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showDialog = false">取消</el-button>
      <el-button type="primary" @click="saveShop">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const shops = ref([])
const showDialog = ref(false)
const syncing = ref(null)
const form = reactive({ id: null, name: '', type: 'local', api_token: '' })

async function fetchShops() {
  const { data } = await api.get('/api/shops')
  shops.value = data
}

function editShop(row) {
  Object.assign(form, { ...row, api_token: '' })
  showDialog.value = true
}

async function saveShop() {
  if (form.id) {
    const payload = { name: form.name, type: form.type }
    if (form.api_token) payload.api_token = form.api_token
    await api.put(`/api/shops/${form.id}`, payload)
  } else {
    await api.post('/api/shops', form)
  }
  showDialog.value = false
  Object.assign(form, { id: null, name: '', type: 'local', api_token: '' })
  fetchShops()
  ElMessage.success('保存成功')
}

async function deleteShop(id) {
  await api.delete(`/api/shops/${id}`)
  fetchShops()
  ElMessage.success('删除成功')
}

async function syncShop(id) {
  syncing.value = id
  try {
    await api.post(`/api/shops/${id}/sync`)
    ElMessage.success('同步完成')
    fetchShops()
  } catch {
    ElMessage.error('同步失败')
  } finally {
    syncing.value = null
  }
}

onMounted(fetchShops)
</script>
```

- [ ] **Step 2: 实现 SkuMappings.vue**

```vue
<!-- frontend/src/views/SkuMappings.vue -->
<template>
  <div>
    <el-page-header @back="$router.back()">
      <template #content>SKU 关联管理</template>
    </el-page-header>

    <el-card style="margin-top: 20px">
      <el-table :data="mappings" stripe>
        <el-table-column prop="wb_product_name" label="WB商品名称" />
        <el-table-column prop="shop_sku" label="店铺SKU" />
        <el-table-column prop="wb_barcode" label="条码" />
        <el-table-column label="关联系统SKU" width="250">
          <template #default="{ row }">
            <el-input
              v-model="row._input_sku"
              placeholder="输入系统SKU"
              @blur="linkSku(row)"
              @keyup.enter="linkSku(row)"
            >
              <template #suffix>
                <el-icon v-if="row.product_id" style="color: #67c23a"><Check /></el-icon>
              </template>
            </el-input>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.product_id ? 'success' : 'warning'" size="small">
              {{ row.product_id ? '已关联' : '未关联' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import api from '../api'

const route = useRoute()
const shopId = route.params.id
const mappings = ref([])

async function fetchMappings() {
  const { data } = await api.get(`/api/shops/${shopId}/sku-mappings`)
  mappings.value = data.map(m => ({ ...m, _input_sku: m._input_sku || '' }))

  // Resolve existing product SKUs
  const products = (await api.get('/api/products')).data
  const skuMap = {}
  products.forEach(p => { skuMap[p.id] = p.sku })
  mappings.value.forEach(m => {
    if (m.product_id && skuMap[m.product_id]) {
      m._input_sku = skuMap[m.product_id]
    }
  })
}

async function linkSku(row) {
  try {
    await api.put(`/api/sku-mappings/${row.id}`, { product_sku: row._input_sku || '' })
    ElMessage.success(row._input_sku ? '关联成功' : '已取消关联')
    fetchMappings()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '关联失败')
  }
}

onMounted(fetchMappings)
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/Shops.vue frontend/src/views/SkuMappings.vue
git commit -m "feat: add shops page with sync trigger and SKU mapping page"
```

---

### Task 21: 财务统计、库存管理、用户管理页面

**Files:**
- Modify: `frontend/src/views/Finance.vue`
- Modify: `frontend/src/views/Inventory.vue`
- Modify: `frontend/src/views/Users.vue`

- [ ] **Step 1: 实现 Finance.vue**

```vue
<!-- frontend/src/views/Finance.vue -->
<template>
  <div>
    <el-card style="margin-bottom: 20px">
      <div style="display: flex; gap: 12px; margin-bottom: 16px">
        <el-select v-model="filters.shop_id" placeholder="全部店铺" clearable @change="fetchFinance">
          <el-option v-for="s in shops" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filters.order_type" placeholder="订单类型" clearable @change="fetchFinance">
          <el-option label="FBS" value="FBS" />
          <el-option label="FBW" value="FBW" />
        </el-select>
      </div>
      <el-row :gutter="16">
        <el-col :span="5">
          <el-statistic title="销售额" :value="summary.total_sales" prefix="₽" />
        </el-col>
        <el-col :span="5">
          <el-statistic title="采购成本" :value="summary.total_purchase_cost" prefix="₽" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="佣金" :value="summary.total_commission" prefix="₽" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="物流费" :value="summary.total_logistics" prefix="₽" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="利润" :value="summary.total_profit" prefix="₽" :value-style="{ color: summary.total_profit >= 0 ? '#67c23a' : '#f56c6c' }" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const shops = ref([])
const filters = reactive({ shop_id: '', order_type: '' })
const summary = ref({ total_sales: 0, total_commission: 0, total_logistics: 0, total_purchase_cost: 0, total_profit: 0 })

async function fetchFinance() {
  const params = {}
  if (filters.shop_id) params.shop_id = filters.shop_id
  if (filters.order_type) params.order_type = filters.order_type
  const { data } = await api.get('/api/finance/summary', { params })
  summary.value = data
}

onMounted(async () => {
  shops.value = (await api.get('/api/shops')).data
  fetchFinance()
})
</script>
```

- [ ] **Step 2: 实现 Inventory.vue**

```vue
<!-- frontend/src/views/Inventory.vue -->
<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>库存管理</span>
        <el-switch v-model="showLowOnly" active-text="仅低库存" @change="fetchInventory" />
      </div>
    </template>
    <el-table :data="inventory" stripe>
      <el-table-column prop="product_name" label="商品名" />
      <el-table-column prop="sku" label="SKU" />
      <el-table-column prop="stock_fbs" label="FBS库存" />
      <el-table-column prop="stock_fbw" label="FBW库存" />
      <el-table-column label="总库存">
        <template #default="{ row }">{{ row.stock_fbs + row.stock_fbw }}</template>
      </el-table-column>
      <el-table-column prop="low_stock_threshold" label="预警阈值" />
      <el-table-column label="状态">
        <template #default="{ row }">
          <el-tag v-if="(row.stock_fbs + row.stock_fbw) < row.low_stock_threshold" type="danger" size="small">低库存</el-tag>
          <el-tag v-else type="success" size="small">正常</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const inventory = ref([])
const showLowOnly = ref(false)

async function fetchInventory() {
  const url = showLowOnly.value ? '/api/inventory/low-stock' : '/api/inventory'
  const { data } = await api.get(url)
  inventory.value = data
}

onMounted(fetchInventory)
</script>
```

- [ ] **Step 3: 实现 Users.vue**

```vue
<!-- frontend/src/views/Users.vue -->
<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>用户管理</span>
        <el-button type="primary" @click="showDialog = true">添加用户</el-button>
      </div>
    </template>
    <el-table :data="users" stripe>
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="role" label="角色">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'operator' ? 'warning' : 'info'">{{ row.role }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" @click="editUser(row)">编辑</el-button>
          <el-popconfirm title="确定删除?" @confirm="deleteUser(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="showDialog" :title="form.id ? '编辑用户' : '添加用户'" width="400px">
    <el-form :model="form" label-width="80px">
      <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="form.password" type="password" :placeholder="form.id ? '留空不修改' : ''" /></el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option label="管理员" value="admin" />
          <el-option label="操作员" value="operator" />
          <el-option label="查看者" value="viewer" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showDialog = false">取消</el-button>
      <el-button type="primary" @click="saveUser">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const users = ref([])
const showDialog = ref(false)
const form = reactive({ id: null, username: '', password: '', role: 'viewer' })

async function fetchUsers() {
  const { data } = await api.get('/api/users')
  users.value = data
}

function editUser(row) {
  Object.assign(form, { ...row, password: '' })
  showDialog.value = true
}

async function saveUser() {
  if (form.id) {
    const payload = { role: form.role }
    if (form.username) payload.username = form.username
    if (form.password) payload.password = form.password
    await api.put(`/api/users/${form.id}`, payload)
  } else {
    await api.post('/api/users', form)
  }
  showDialog.value = false
  Object.assign(form, { id: null, username: '', password: '', role: 'viewer' })
  fetchUsers()
  ElMessage.success('保存成功')
}

async function deleteUser(id) {
  await api.delete(`/api/users/${id}`)
  fetchUsers()
  ElMessage.success('删除成功')
}

onMounted(fetchUsers)
</script>
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/Finance.vue frontend/src/views/Inventory.vue frontend/src/views/Users.vue
git commit -m "feat: add finance, inventory, and user management pages"
```

---

### Task 22: 端到端验证

**Files:** 无新文件

- [ ] **Step 1: 运行全部后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: 创建管理员并启动后端**

Run: `cd backend && python create_admin.py && uvicorn app.main:app --reload`
Expected: Admin created, server running at http://localhost:8000

- [ ] **Step 3: 启动前端**

Run: `cd frontend && npm run dev`
Expected: Frontend at http://localhost:5173

- [ ] **Step 4: 手动验证**

1. 打开 http://localhost:5173/login，用 admin/admin123 登录
2. 看到数据看板页
3. 进入店铺管理，添加店铺
4. 进入商品管理，添加商品
5. 进入 SKU 关联页面，关联 SKU
6. 检查订单、库存、财务页面

- [ ] **Step 5: 提交最终状态**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
