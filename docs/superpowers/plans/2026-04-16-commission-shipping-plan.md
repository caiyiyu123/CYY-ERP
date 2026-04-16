# 佣金运费模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增"佣金运费"模块，支持上传解析平台佣金 Excel 表格和创建管理头程运费模板

**Architecture:** 后端新增 SQLAlchemy 模型存储佣金率和运费模板数据，使用 openpyxl 解析上传的 Excel 文件。前端新增 Vue 页面，使用 el-tabs 切换"平台佣金"和"头程运费"两个功能板块，佣金表格支持动态列渲染

**Tech Stack:** FastAPI, SQLAlchemy, openpyxl, Vue 3, Element Plus

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/models/commission.py` | 新建 | CommissionTable、CommissionRate、ShippingTemplate、ShippingRate 模型 |
| `backend/app/models/__init__.py` | 修改 | 导入新模型 |
| `backend/app/routers/commission_shipping.py` | 新建 | 佣金上传/查询 + 运费模板 CRUD 路由 |
| `backend/app/main.py` | 修改 | 注册新路由 |
| `backend/app/models/user.py` | 修改 | ALL_MODULES 添加 commission_shipping |
| `backend/requirements.txt` | 修改 | 添加 openpyxl |
| `frontend/src/views/CommissionShipping.vue` | 新建 | 佣金运费页面（含两个 Tab） |
| `frontend/src/router/index.js` | 修改 | 添加路由 |
| `frontend/src/views/Layout.vue` | 修改 | 添加导航菜单项 |

---

### Task 1: 创建后端数据模型

**Files:**
- Create: `backend/app/models/commission.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 commission.py 模型文件**

创建 `backend/app/models/commission.py`，内容：

```python
from datetime import datetime, timezone, date
from sqlalchemy import String, Float, Integer, DateTime, Date, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class CommissionTable(Base):
    __tablename__ = "commission_tables"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    rates: Mapped[list["CommissionRate"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )


class CommissionRate(Base):
    __tablename__ = "commission_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commission_tables.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(200), default="")
    product_name: Mapped[str] = mapped_column(String(200), default="")
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    extra_rates: Mapped[dict] = mapped_column(JSON, default=dict)
    table: Mapped["CommissionTable"] = relationship(back_populates="rates")


class ShippingTemplate(Base):
    __tablename__ = "shipping_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    rates: Mapped[list["ShippingRate"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class ShippingRate(Base):
    __tablename__ = "shipping_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shipping_templates.id", ondelete="CASCADE")
    )
    density_min: Mapped[float] = mapped_column(Float, default=0.0)
    density_max: Mapped[float] = mapped_column(Float, default=0.0)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    template: Mapped["ShippingTemplate"] = relationship(back_populates="rates")
```

- [ ] **Step 2: 更新 models/\_\_init\_\_.py**

在 `backend/app/models/__init__.py` 中添加导入：

```python
from app.models.commission import CommissionTable, CommissionRate, ShippingTemplate, ShippingRate
```

并在 `__all__` 列表末尾添加：`"CommissionTable", "CommissionRate", "ShippingTemplate", "ShippingRate"`

完整文件：

```python
from app.models.user import User
from app.models.shop import Shop
from app.models.product import Product, SkuMapping
from app.models.order import Order, OrderItem, OrderStatusLog
from app.models.inventory import Inventory
from app.models.ad import AdCampaign, AdDailyStat
from app.models.setting import SystemSetting
from app.models.commission import CommissionTable, CommissionRate, ShippingTemplate, ShippingRate

__all__ = [
    "User", "Shop", "Product", "SkuMapping",
    "Order", "OrderItem", "OrderStatusLog",
    "Inventory", "AdCampaign", "AdDailyStat", "SystemSetting",
    "CommissionTable", "CommissionRate", "ShippingTemplate", "ShippingRate",
]
```

- [ ] **Step 3: 验证模型语法**

Run: `cd "C:\Users\caiyi\Desktop\CYY应用\CYY-ERP\backend" && python -c "from app.models.commission import CommissionTable, CommissionRate, ShippingTemplate, ShippingRate; print('OK')"`
Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/commission.py backend/app/models/__init__.py
git commit -m "feat: add commission and shipping data models"
```

---

### Task 2: 添加依赖和权限配置

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/models/user.py:32`

- [ ] **Step 1: 添加 openpyxl 到 requirements.txt**

在 `backend/requirements.txt` 末尾添加一行：

```
openpyxl>=3.1.0
```

- [ ] **Step 2: 安装依赖**

Run: `cd "C:\Users\caiyi\Desktop\CYY应用\CYY-ERP\backend" && pip install openpyxl>=3.1.0`
Expected: Successfully installed openpyxl-...

- [ ] **Step 3: 添加模块权限到 ALL_MODULES**

修改 `backend/app/models/user.py` 第 32 行，将：

```python
    ALL_MODULES = ["dashboard", "orders", "products", "ads", "finance", "inventory", "shops"]
```

改为：

```python
    ALL_MODULES = ["dashboard", "orders", "products", "ads", "finance", "inventory", "shops", "commission_shipping"]
```

- [ ] **Step 4: 提交**

```bash
git add backend/requirements.txt backend/app/models/user.py
git commit -m "feat: add openpyxl dependency and commission_shipping permission"
```

---

### Task 3: 创建后端路由（佣金 + 运费）

**Files:**
- Create: `backend/app/routers/commission_shipping.py`

- [ ] **Step 1: 创建路由文件**

创建 `backend/app/routers/commission_shipping.py`，完整内容：

```python
import io
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openpyxl import load_workbook

from app.database import get_db
from app.models.commission import CommissionTable, CommissionRate, ShippingTemplate, ShippingRate
from app.utils.deps import require_module

router = APIRouter(tags=["commission-shipping"])

VALID_PLATFORMS = {"wb_local", "wb_cross_border", "ozon_local"}


def _to_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ==================== 佣金部分 ====================


@router.post("/api/commission/upload")
def upload_commission(
    platform: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    if platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xls files are supported")

    content = file.file.read()
    wb = load_workbook(filename=io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="File has no data rows")

    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
    data_rows = rows[1:]

    # 删除该平台旧数据
    old_tables = db.query(CommissionTable).filter(CommissionTable.platform == platform).all()
    for t in old_tables:
        db.delete(t)
    db.flush()

    # 创建新表记录
    ct = CommissionTable(platform=platform, filename=file.filename or "")
    db.add(ct)
    db.flush()

    # 解析数据行
    rates = []
    for row in data_rows:
        vals = list(row)
        if not vals or all(v is None for v in vals):
            continue

        if platform == "wb_local":
            category = str(vals[0] or "").strip()
            product_name = str(vals[1] or "").strip()
            rate = _to_float(vals[2]) if len(vals) > 2 else 0.0
            extra = {}
            for i in range(3, min(len(vals), len(headers))):
                extra[headers[i]] = _to_float(vals[i])
            rates.append(CommissionRate(
                table_id=ct.id, category=category, product_name=product_name,
                rate=rate, extra_rates=extra,
            ))

        elif platform == "wb_cross_border":
            category = str(vals[0] or "").strip()
            product_name = str(vals[1] or "").strip()
            rate = _to_float(vals[2]) if len(vals) > 2 else 0.0
            rates.append(CommissionRate(
                table_id=ct.id, category=category, product_name=product_name,
                rate=rate, extra_rates={},
            ))

        elif platform == "ozon_local":
            category = str(vals[0] or "").strip()
            product_name = str(vals[1] or "").strip()
            extra = {}
            for i in range(2, min(len(vals), len(headers))):
                extra[headers[i]] = _to_float(vals[i])
            first_rate = _to_float(vals[2]) if len(vals) > 2 else 0.0
            rates.append(CommissionRate(
                table_id=ct.id, category=category, product_name=product_name,
                rate=first_rate, extra_rates=extra,
            ))

    db.add_all(rates)
    db.commit()
    wb.close()
    return {"detail": f"Uploaded {len(rates)} rows for {platform}", "count": len(rates)}


@router.get("/api/commission/rates")
def list_commission_rates(
    platform: str = Query(...),
    search: str = Query(""),
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    ct = db.query(CommissionTable).filter(CommissionTable.platform == platform).first()
    if not ct:
        return {"rates": [], "headers": []}

    q = db.query(CommissionRate).filter(CommissionRate.table_id == ct.id)
    if search:
        kw = f"%{search}%"
        q = q.filter(
            (CommissionRate.category.ilike(kw)) | (CommissionRate.product_name.ilike(kw))
        )
    rates = q.all()

    # 提取动态列名
    extra_keys = []
    if rates:
        first_extra = rates[0].extra_rates or {}
        extra_keys = list(first_extra.keys())

    result = []
    for r in rates:
        item = {
            "id": r.id,
            "category": r.category,
            "product_name": r.product_name,
            "rate": r.rate,
        }
        extras = r.extra_rates or {}
        for k in extra_keys:
            item[k] = extras.get(k, 0.0)
        result.append(item)

    return {"rates": result, "headers": extra_keys}


@router.get("/api/commission/info")
def commission_info(
    platform: str = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    ct = db.query(CommissionTable).filter(CommissionTable.platform == platform).first()
    if not ct:
        return {"filename": None, "uploaded_at": None}
    return {"filename": ct.filename, "uploaded_at": ct.uploaded_at.isoformat()}


# ==================== 运费模板部分 ====================


class ShippingRateItem(BaseModel):
    density_min: float
    density_max: float
    price_usd: float


class ShippingTemplateCreate(BaseModel):
    name: str
    date: date
    rates: list[ShippingRateItem]


class ShippingTemplateUpdate(BaseModel):
    name: str
    date: date
    rates: list[ShippingRateItem]


@router.get("/api/shipping/templates")
def list_shipping_templates(
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    templates = db.query(ShippingTemplate).order_by(ShippingTemplate.updated_at.desc()).all()
    result = []
    for t in templates:
        result.append({
            "id": t.id,
            "name": t.name,
            "date": t.date.isoformat(),
            "rate_count": len(t.rates),
            "rates": [
                {"density_min": r.density_min, "density_max": r.density_max, "price_usd": r.price_usd}
                for r in sorted(t.rates, key=lambda x: x.density_min)
            ],
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        })
    return result


@router.post("/api/shipping/templates", status_code=status.HTTP_201_CREATED)
def create_shipping_template(
    data: ShippingTemplateCreate,
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    tpl = ShippingTemplate(name=data.name, date=data.date)
    db.add(tpl)
    db.flush()
    for r in data.rates:
        db.add(ShippingRate(
            template_id=tpl.id,
            density_min=r.density_min,
            density_max=r.density_max,
            price_usd=r.price_usd,
        ))
    db.commit()
    db.refresh(tpl)
    return {"id": tpl.id, "detail": "Template created"}


@router.put("/api/shipping/templates/{tpl_id}")
def update_shipping_template(
    tpl_id: int,
    data: ShippingTemplateUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    tpl = db.query(ShippingTemplate).filter(ShippingTemplate.id == tpl_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    tpl.name = data.name
    tpl.date = data.date
    # 删除旧运费明细，重建
    db.query(ShippingRate).filter(ShippingRate.template_id == tpl.id).delete()
    for r in data.rates:
        db.add(ShippingRate(
            template_id=tpl.id,
            density_min=r.density_min,
            density_max=r.density_max,
            price_usd=r.price_usd,
        ))
    db.commit()
    return {"detail": "Template updated"}


@router.delete("/api/shipping/templates/{tpl_id}")
def delete_shipping_template(
    tpl_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_module("commission_shipping")),
):
    tpl = db.query(ShippingTemplate).filter(ShippingTemplate.id == tpl_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tpl)
    db.commit()
    return {"detail": "Template deleted"}
```

- [ ] **Step 2: 验证语法**

Run: `cd "C:\Users\caiyi\Desktop\CYY应用\CYY-ERP\backend" && python -c "import py_compile; py_compile.compile('app/routers/commission_shipping.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/commission_shipping.py
git commit -m "feat: add commission upload/query and shipping template CRUD endpoints"
```

---

### Task 4: 注册路由到 main.py

**Files:**
- Modify: `backend/app/main.py:10,103`

- [ ] **Step 1: 添加导入**

修改 `backend/app/main.py` 第 10 行，将：

```python
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance, dashboard, ads, shop_products, customer_service
```

改为：

```python
from app.routers import auth, users, shops, products, sku_mappings, orders, inventory, finance, dashboard, ads, shop_products, customer_service, commission_shipping
```

- [ ] **Step 2: 注册路由**

在 `backend/app/main.py` 第 103 行 `app.include_router(customer_service.router)` 后面添加：

```python
app.include_router(commission_shipping.router)
```

- [ ] **Step 3: 验证启动**

Run: `cd "C:\Users\caiyi\Desktop\CYY应用\CYY-ERP\backend" && python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add backend/app/main.py
git commit -m "feat: register commission_shipping router in main app"
```

---

### Task 5: 创建前端佣金运费页面

**Files:**
- Create: `frontend/src/views/CommissionShipping.vue`

- [ ] **Step 1: 创建 CommissionShipping.vue**

创建 `frontend/src/views/CommissionShipping.vue`，完整内容：

```vue
<template>
  <el-card>
    <el-tabs v-model="mainTab">
      <!-- ====== 平台佣金 Tab ====== -->
      <el-tab-pane label="平台佣金" name="commission">
        <el-tabs v-model="platformTab" type="card" style="margin-bottom: 16px">
          <el-tab-pane label="WB本土" name="wb_local" />
          <el-tab-pane label="WB跨境" name="wb_cross_border" />
          <el-tab-pane label="OZON本土" name="ozon_local" />
        </el-tabs>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
          <div style="display: flex; align-items: center; gap: 12px">
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".xlsx,.xls"
              :on-change="onFileSelected"
            >
              <el-button type="primary">上传佣金表格</el-button>
            </el-upload>
            <span v-if="commissionInfo.filename" style="color: #909399; font-size: 13px">
              当前文件：{{ commissionInfo.filename }}（{{ commissionInfo.uploaded_at }}）
            </span>
          </div>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索类目/商品名"
            clearable
            style="width: 240px"
          />
        </div>

        <el-table :data="filteredRates" stripe max-height="600" v-loading="loadingRates">
          <el-table-column prop="category" label="类目" min-width="180" />
          <el-table-column prop="product_name" label="商品名称" min-width="180" />
          <el-table-column
            v-if="platformTab !== 'ozon_local'"
            prop="rate"
            label="佣金率(%)"
            width="120"
            align="center"
          />
          <el-table-column
            v-for="h in extraHeaders"
            :key="h"
            :prop="h"
            :label="h"
            width="140"
            align="center"
          />
        </el-table>
      </el-tab-pane>

      <!-- ====== 头程运费 Tab ====== -->
      <el-tab-pane label="头程运费" name="shipping">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
          <span style="font-size: 16px; font-weight: 500">运费模板</span>
          <el-button type="primary" @click="openShippingDialog()">新增运费模板</el-button>
        </div>

        <el-table :data="shippingTemplates" stripe v-loading="loadingTemplates">
          <el-table-column prop="name" label="头程名称" min-width="160" />
          <el-table-column prop="date" label="日期" width="130" align="center" />
          <el-table-column prop="rate_count" label="区间数" width="100" align="center" />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="openShippingDialog(row)">编辑</el-button>
              <el-popconfirm title="确定删除该模板?" @confirm="deleteTemplate(row.id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <!-- 运费模板编辑对话框 -->
  <el-dialog v-model="showShippingDialog" :title="shippingForm.id ? '编辑运费模板' : '新增运费模板'" width="600px">
    <el-form :model="shippingForm" label-width="80px">
      <el-form-item label="头程名称">
        <el-input v-model="shippingForm.name" placeholder="如：空运-莫斯科" />
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker v-model="shippingForm.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="密度区间">
        <div style="width: 100%">
          <div
            v-for="(r, idx) in shippingForm.rates"
            :key="idx"
            style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px"
          >
            <el-input-number v-model="r.density_min" :min="0" :precision="1" placeholder="下限" controls-position="right" style="width: 130px" />
            <span>~</span>
            <el-input-number v-model="r.density_max" :min="0" :precision="1" placeholder="上限" controls-position="right" style="width: 130px" />
            <el-input-number v-model="r.price_usd" :min="0" :precision="2" placeholder="运费USD" controls-position="right" style="width: 140px" />
            <el-button :icon="Delete" circle size="small" @click="shippingForm.rates.splice(idx, 1)" />
          </div>
          <el-button type="primary" link @click="shippingForm.rates.push({ density_min: 0, density_max: 0, price_usd: 0 })">
            + 添加行
          </el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showShippingDialog = false">取消</el-button>
      <el-button type="primary" @click="saveTemplate">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import api from '../api'

// ==================== 佣金部分 ====================
const mainTab = ref('commission')
const platformTab = ref('wb_local')
const searchKeyword = ref('')
const commissionRates = ref([])
const extraHeaders = ref([])
const commissionInfo = reactive({ filename: null, uploaded_at: null })
const loadingRates = ref(false)

const filteredRates = computed(() => {
  if (!searchKeyword.value) return commissionRates.value
  const kw = searchKeyword.value.toLowerCase()
  return commissionRates.value.filter(
    r => r.category.toLowerCase().includes(kw) || r.product_name.toLowerCase().includes(kw)
  )
})

async function fetchCommissionRates() {
  loadingRates.value = true
  try {
    const { data } = await api.get('/api/commission/rates', { params: { platform: platformTab.value } })
    commissionRates.value = data.rates || []
    extraHeaders.value = data.headers || []
  } catch { ElMessage.error('加载佣金数据失败') }
  finally { loadingRates.value = false }
}

async function fetchCommissionInfo() {
  try {
    const { data } = await api.get('/api/commission/info', { params: { platform: platformTab.value } })
    commissionInfo.filename = data.filename
    commissionInfo.uploaded_at = data.uploaded_at ? new Date(data.uploaded_at).toLocaleString('zh-CN') : null
  } catch { /* ignore */ }
}

async function onFileSelected(file) {
  const formData = new FormData()
  formData.append('file', file.raw)
  try {
    loadingRates.value = true
    const { data } = await api.post(`/api/commission/upload?platform=${platformTab.value}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`上传成功，共 ${data.count} 条数据`)
    fetchCommissionRates()
    fetchCommissionInfo()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally { loadingRates.value = false }
}

watch(platformTab, () => {
  searchKeyword.value = ''
  fetchCommissionRates()
  fetchCommissionInfo()
})

// ==================== 运费模板部分 ====================
const shippingTemplates = ref([])
const loadingTemplates = ref(false)
const showShippingDialog = ref(false)
const shippingForm = reactive({ id: null, name: '', date: '', rates: [] })

async function fetchShippingTemplates() {
  loadingTemplates.value = true
  try {
    const { data } = await api.get('/api/shipping/templates')
    shippingTemplates.value = data
  } catch { ElMessage.error('加载运费模板失败') }
  finally { loadingTemplates.value = false }
}

function openShippingDialog(row) {
  if (row) {
    shippingForm.id = row.id
    shippingForm.name = row.name
    shippingForm.date = row.date
    shippingForm.rates = row.rates.map(r => ({ ...r }))
  } else {
    shippingForm.id = null
    shippingForm.name = ''
    shippingForm.date = ''
    shippingForm.rates = [{ density_min: 0, density_max: 0, price_usd: 0 }]
  }
  showShippingDialog.value = true
}

async function saveTemplate() {
  if (!shippingForm.name || !shippingForm.date) {
    ElMessage.warning('请填写名称和日期')
    return
  }
  const payload = { name: shippingForm.name, date: shippingForm.date, rates: shippingForm.rates }
  try {
    if (shippingForm.id) {
      await api.put(`/api/shipping/templates/${shippingForm.id}`, payload)
    } else {
      await api.post('/api/shipping/templates', payload)
    }
    showShippingDialog.value = false
    fetchShippingTemplates()
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteTemplate(id) {
  try {
    await api.delete(`/api/shipping/templates/${id}`)
    fetchShippingTemplates()
    ElMessage.success('删除成功')
  } catch { ElMessage.error('删除失败') }
}

onMounted(() => {
  fetchCommissionRates()
  fetchCommissionInfo()
  fetchShippingTemplates()
})
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/CommissionShipping.vue
git commit -m "feat: add CommissionShipping page with commission and shipping tabs"
```

---

### Task 6: 注册前端路由和导航菜单

**Files:**
- Modify: `frontend/src/router/index.js:19`
- Modify: `frontend/src/views/Layout.vue:43-46,83`

- [ ] **Step 1: 添加路由**

在 `frontend/src/router/index.js` 的 children 数组中，在 customer-service 路由（第 19 行）后面添加：

```javascript
      { path: 'commission-shipping', name: 'CommissionShipping', meta: { module: 'commission_shipping' }, component: () => import('../views/CommissionShipping.vue') },
```

- [ ] **Step 2: 添加导航菜单项**

在 `frontend/src/views/Layout.vue` 中，在"评价客服"菜单项（第 39-42 行）后面添加：

```vue
        <el-menu-item v-if="hasPerm('commission_shipping')" index="/commission-shipping">
          <el-icon><PriceTag /></el-icon>
          <span>佣金运费</span>
        </el-menu-item>
```

- [ ] **Step 3: 导入 PriceTag 图标**

修改 `frontend/src/views/Layout.vue` 第 83 行的图标导入，将：

```javascript
import { DataAnalysis, Box, ShoppingCart, Goods, TrendCharts, Money, List, Shop, User, ChatDotRound } from '@element-plus/icons-vue'
```

改为：

```javascript
import { DataAnalysis, Box, ShoppingCart, Goods, TrendCharts, Money, List, Shop, User, ChatDotRound, PriceTag } from '@element-plus/icons-vue'
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/router/index.js frontend/src/views/Layout.vue
git commit -m "feat: add commission-shipping route and navigation menu item"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: 重启后端服务**

提示用户重启后端和前端服务以加载新模型、路由和页面。

- [ ] **Step 2: 浏览器测试**

在浏览器中验证：

1. 导航栏显示"佣金运费"菜单项
2. 点击进入页面，确认两个主 Tab（平台佣金、头程运费）正常切换
3. 平台佣金 Tab 内三个子 Tab（WB本土、WB跨境、OZON本土）正常切换
4. 上传 Excel 文件测试（.xlsx），确认数据解析后显示在表格中
5. 搜索功能正常过滤类目/商品名
6. 切换到头程运费 Tab，点击"新增运费模板"
7. 填写名称、日期、添加密度区间行，保存
8. 编辑已有模板，修改后保存
9. 删除模板（确认弹窗正常）

- [ ] **Step 3: 确认完成后可选推送**

所有功能验证通过后，询问用户是否需要推送到远程仓库。
