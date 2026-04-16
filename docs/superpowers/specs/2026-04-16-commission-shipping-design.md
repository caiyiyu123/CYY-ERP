# 佣金运费模块设计

## 概述

新增"佣金运费"模块，包含两个功能板块：
1. **平台佣金** — 用户上传 Excel 佣金表格，解析入库，支持搜索查看，后续接入利润计算
2. **头程运费** — 用户创建运费模板，填写密度区间和对应运费价格，后续接入成本计算

## 页面结构

- 导航栏新增"佣金运费"菜单项
- 权限模块名：`commission_shipping`
- 页面内两个 Tab：**平台佣金** | **头程运费**

---

## 一、平台佣金

### 支持的平台

| 平台 | platform 值 | 表格特点 |
|------|------------|---------|
| WB本土 | `wb_local` | 类别 + 商品 + 佣金% + 多个仓库费率列 |
| WB跨境 | `wb_cross_border` | 类目 + 商品 + 佣金率（3列） |
| OZON本土 | `ozon_local` | 类别 + 货物类型 + FBO/FBS各价格区间佣金率（十几列） |

### 页面布局

- 顶部：三个子 Tab 切换平台（WB本土 / WB跨境 / OZON本土）
- 每个子 Tab：右上角"上传佣金表格"按钮 + 搜索框（按类目/商品名搜索）
- 下方：el-table 展示解析后的佣金数据
- 重新上传会覆盖该平台的旧数据

### 数据模型

#### CommissionTable（佣金表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| platform | String(30) | 平台标识：wb_local / wb_cross_border / ozon_local |
| filename | String(200) | 上传的原始文件名 |
| uploaded_at | DateTime | 上传时间 |

#### CommissionRate（佣金率明细）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| table_id | Integer FK → CommissionTable | 所属佣金表 |
| category | String(200) | 类目名称 |
| product_name | String(200) | 商品名称 |
| rate | Float | 基础佣金率（百分比数值，如 23.5 表示 23.5%） |
| extra_rates | JSON | 附加费率列（WB本土的仓库列、OZON的FBO/FBS各区间列），存为 JSON 对象 |

### 上传解析逻辑

1. 用户选择 Excel 文件（.xlsx / .xls）上传
2. 后端使用 openpyxl 解析文件内容
3. 根据 platform 类型确定解析策略：
   - **wb_local**：第1列=类别，第2列=商品，第3列=佣金率，第4列起=附加费率（列名作为 extra_rates 的 key）
   - **wb_cross_border**：第1列=类目，第2列=商品，第3列=佣金率，无附加列
   - **ozon_local**：第1列=类别，第2列=货物类型，第3列起=各区间佣金率（列名作为 extra_rates 的 key）。OZON 无单一基础佣金率，rate 字段存第一个费率列的值
4. 删除该 platform 的旧 CommissionTable 及关联 CommissionRate
5. 创建新 CommissionTable，批量插入 CommissionRate
6. 返回成功信息

### 前端表格渲染

- WB跨境：固定3列（类目、商品、佣金率）
- WB本土/OZON本土：前几列固定（类目、商品），后续列从 extra_rates 的 key 动态生成 el-table-column
- 搜索：前端过滤 category 和 product_name 字段

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/commission/upload?platform=xxx | 上传佣金表格 |
| GET | /api/commission/rates?platform=xxx&search=xxx | 查询佣金率列表 |
| GET | /api/commission/info?platform=xxx | 获取当前佣金表信息（文件名、上传时间） |

---

## 二、头程运费

### 页面布局

- 顶部：左侧标题，右侧"新增运费模板"按钮
- 下方：el-table 列表展示所有运费模板（名称、日期、区间数、操作）
- 操作：编辑、删除

### 新增/编辑对话框

- 头程名称：文本输入
- 日期：日期选择器
- 密度-运费表格（动态行）：
  - 每行：密度区间起始值（Float）、密度区间结束值（Float）、运费 USD（Float）
  - 底部"添加行"按钮
  - 每行右侧"删除行"按钮
- 密度定义：重量(g) ÷ 体积(cm³) × 1000

### 数据模型

#### ShippingTemplate（运费模板）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| name | String(200) | 头程名称（如"空运-莫斯科"） |
| date | Date | 日期 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### ShippingRate（运费明细）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 主键 |
| template_id | Integer FK → ShippingTemplate | 所属模板 |
| density_min | Float | 密度区间下限 |
| density_max | Float | 密度区间上限 |
| price_usd | Float | 运费（美金） |

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/shipping/templates | 获取所有运费模板列表 |
| POST | /api/shipping/templates | 创建运费模板（含密度区间） |
| PUT | /api/shipping/templates/{id} | 更新运费模板 |
| DELETE | /api/shipping/templates/{id} | 删除运费模板 |

### 请求/响应格式

创建/更新请求体：
```json
{
  "name": "空运-莫斯科",
  "date": "2026-04-10",
  "rates": [
    {"density_min": 0, "density_max": 100, "price_usd": 3.5},
    {"density_min": 100, "density_max": 200, "price_usd": 3.0},
    {"density_min": 200, "density_max": 300, "price_usd": 2.5}
  ]
}
```

---

## 技术实现

### 后端新增

| 文件 | 操作 |
|------|------|
| `backend/app/models/commission.py` | **新建** — CommissionTable、CommissionRate、ShippingTemplate、ShippingRate 模型 |
| `backend/app/routers/commission_shipping.py` | **新建** — 佣金上传/查询 + 运费模板 CRUD 路由 |
| `backend/app/main.py` | **修改** — 注册新路由、导入新模型 |
| `backend/requirements.txt` | **修改** — 添加 openpyxl 依赖 |

### 前端新增

| 文件 | 操作 |
|------|------|
| `frontend/src/views/CommissionShipping.vue` | **新建** — 佣金运费页面 |
| `frontend/src/router/index.js` | **修改** — 添加路由 |
| `frontend/src/views/Layout.vue` | **修改** — 添加导航菜单项 |

### 权限

- 模块名：`commission_shipping`
- 需在 User 模型的 ALL_MODULES 中添加
- Layout.vue 菜单项使用 `hasPerm('commission_shipping')` 控制显示

---

## 暂不实现（后续迭代）

- 佣金率自动匹配商品类目参与订单利润计算
- 头程运费模板关联到商品或店铺
- 佣金率变更历史记录
