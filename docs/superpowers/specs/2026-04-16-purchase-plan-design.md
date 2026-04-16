# 采购计划模块设计

## 概述

新增采购计划模块，运营人员可创建采购计划，选择商品、填写数量和箱数，跟踪采购状态（待采购→已采购→已到货）。

## 数据模型

### 采购计划主表 (PurchasePlan)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 主键 |
| operator_name | String(50) | 运营姓名（从用户列表选择的 display_name） |
| purchase_date | Date | 计划采购日期（用户手动选择） |
| express_fee | Float, default=0.0 | 快递费用（整单一个金额） |
| status | String(20), default="pending" | 状态：pending(待采购) / purchased(已采购) / arrived(已到货) |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 采购计划明细表 (PurchasePlanItem)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 主键 |
| plan_id | Integer, FK→PurchasePlan | 外键 |
| product_id | Integer, FK→Product | 外键，关联商品管理中的商品 |
| quantity | Integer, default=0 | 采购数量 |
| boxes | Integer, default=0 | 箱数 |
| unit_price | Float, default=0.0 | 采购单价（默认取商品的 purchase_price，可修改） |

### 计算字段（不存库，前端实时计算）

- 商品小计 = quantity × unit_price
- 采购总金额 = Σ(所有明细的 quantity × unit_price) + express_fee

## 后端 API

路由前缀：`/api/purchase-plans`
权限模块：`purchase_plan`
依赖：`require_module("purchase_plan")`

### 接口列表

| 方法 | 路径 | 说明 | 请求体/参数 |
|------|------|------|-------------|
| GET | /api/purchase-plans | 获取采购计划列表 | Query: status(可选，筛选状态) |
| POST | /api/purchase-plans | 新增采购计划 | Body: {operator_name, purchase_date, express_fee, items: [{product_id, quantity, boxes, unit_price}]} |
| PUT | /api/purchase-plans/{id} | 编辑采购计划 | Body: 同上 |
| DELETE | /api/purchase-plans/{id} | 删除采购计划 | - |
| PUT | /api/purchase-plans/{id}/status | 修改状态 | Body: {status} |

### GET /api/purchase-plans 返回格式

```json
[
  {
    "id": 1,
    "operator_name": "张三",
    "purchase_date": "2026-04-16",
    "express_fee": 50.0,
    "status": "pending",
    "created_at": "...",
    "updated_at": "...",
    "items": [
      {
        "id": 1,
        "product_id": 10,
        "product_sku": "A-001",
        "product_name": "商品A红色",
        "product_image": "/uploads/xxx.jpg",
        "quantity": 100,
        "boxes": 5,
        "unit_price": 15.0
      }
    ]
  }
]
```

### 商品搜索

复用已有的 `GET /api/products` 接口。前端获取全部商品列表后在本地做 SKU/名称搜索过滤（商品数量有限，无需后端搜索接口）。

## 前端页面

### 文件

- 新建：`frontend/src/views/PurchasePlan.vue`

### 列表页

表格列：运营姓名、采购日期、商品数量（items.length）、采购总金额（计算）、状态（tag 展示）、操作（编辑/删除/改状态）。

状态筛选：顶部下拉框，选项为"全部 / 待采购 / 已采购 / 已到货"。

状态 Tag 样式：
- 待采购：warning（橙色）
- 已采购：primary（蓝色）
- 已到货：success（绿色）

### 新增/编辑对话框

布局从上到下：

1. **运营姓名**：el-select 下拉框，选项从 GET /api/users 获取所有用户的 display_name（包括管理员）
2. **采购日期**：el-date-picker，type="date"
3. **添加商品**：el-select 远程搜索，filterable，搜索 SKU 或名称。选中后自动添加到下方明细列表，默认填入商品的 purchase_price 作为采购单价
4. **明细列表**：el-table 展示
   - 商品图片（50x50 缩略图）
   - 商品 SKU
   - 商品名称
   - 采购单价（el-input-number，可修改）
   - 数量（el-input-number）
   - 箱数（el-input-number）
   - 小计（quantity × unit_price，自动计算显示）
   - 操作（删除按钮）
5. **快递费用**：el-input-number
6. **采购总金额**：自动计算显示，不可编辑
7. **底部按钮**：取消 + 保存

### 状态修改

列表中每行的状态列旁显示操作按钮：
- 待采购 → 点击"标记已采购"
- 已采购 → 点击"标记已到货"
- 已到货 → 无按钮（终态）

## 权限与导航

### 后端 ALL_MODULES

在 `backend/app/models/user.py` 的 `ALL_MODULES` 列表中添加 `"purchase_plan"`。

### 前端路由

在 `frontend/src/router/index.js` 中添加：
- path: `/purchase-plan`
- component: PurchasePlan.vue
- meta: `{ module: 'purchase_plan' }`

### 导航菜单

在 `frontend/src/views/Layout.vue` 中添加菜单项：
- 名称：采购计划
- 图标：ShoppingCart（来自 @element-plus/icons-vue）
- 权限：`hasPerm('purchase_plan')`
- 位置：商品管理之后、推广数据之前

### 用户管理

在 `frontend/src/views/Users.vue` 的 `allModules` 数组中添加 `purchase_plan`。

## 需要修改的文件

| 文件 | 操作 |
|------|------|
| `backend/app/models/purchase_plan.py` | **新建** - PurchasePlan 和 PurchasePlanItem 模型 |
| `backend/app/routers/purchase_plan.py` | **新建** - CRUD + 状态修改路由 |
| `backend/app/models/__init__.py` | 修改 - 导入新模型 |
| `backend/app/models/user.py` | 修改 - ALL_MODULES 添加 purchase_plan |
| `backend/app/main.py` | 修改 - 注册路由 |
| `frontend/src/views/PurchasePlan.vue` | **新建** - 采购计划页面 |
| `frontend/src/router/index.js` | 修改 - 添加路由 |
| `frontend/src/views/Layout.vue` | 修改 - 添加菜单项 |
| `frontend/src/views/Users.vue` | 修改 - allModules 添加 purchase_plan |
