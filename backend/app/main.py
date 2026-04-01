from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_DIR
from app.database import Base, engine
import app.models  # noqa: F401
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance, dashboard, ads
from app.services.scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="韬盛ERP", description="韬盛ERP - Wildberries 订单管理系统", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(sku_mappings.router)
app.include_router(orders.router)
app.include_router(inventory.router)
app.include_router(finance.router)
app.include_router(dashboard.router)
app.include_router(ads.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
