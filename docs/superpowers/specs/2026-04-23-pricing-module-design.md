# 定价表模块设计文档

**日期**：2026-04-23
**模块**：pricing（定价表）
**目标**：为 CYY-ERP 新增一个定价决策模块，辅助商家核算不同平台/物流方案下的商品利润和定价策略。

---

## 1. 背景与动机

现有 ERP 已经有商品管理、采购成本、佣金率、头程运费等基础数据，但缺少一个**把这些数据串起来做定价决策**的工具。商家在定价时需要：

- 在多个平台（WB 跨境 / WB 本土 / OZON 本土）之间对比利润
- 根据采购成本、头程运费、平台佣金、提现手续费等自动算出利润与利润率
- 支持"同一商品多种方案对比"（旺季/淡季定价等）

本模块提供一个可保存、可复算的定价工具。

---

## 2. 本期范围

### 做

- 新模块骨架：路由、权限、数据模型、API、前端页面
- **仅实现 WB 跨境 FBS 一行定价**（UI + 全部 12 个字段的计算公式）
- 参数 tab：5 个全局参数可编辑
- SKU 软关联 Product（创建时快照复制字段，后续独立编辑）
- SKU 可空（支持纯测试定价）
- 三个平台类目字段（WB 本土 / WB 跨境 / OZON 本土）在 UI 中**全部显示**，一次填齐方便未来扩展

### 不做（留到未来）

- WB 跨境 FBW / WB 本土 / OZON 本土 FBS / OZON 本土 FBO 四行
- 利润快照（随参数变化后，老条目显示"当时"的利润）
- 批量导入 / 导出 Excel
- 批量编辑 / 复制条目

---

## 3. 架构总览

- **路由**：`/pricing`
- **权限 key**：`pricing`（加入 `User.ALL_MODULES`，admin 默认可见）
- **后端目录结构**：
  - `backend/app/models/pricing.py` — 两张新表
  - `backend/app/routers/pricing.py` — CRUD + 参数读写
  - （不需要 `services/pricing_calc.py`，计算全部放前端）
- **前端目录结构**：
  - `frontend/src/views/Pricing.vue` — 主页面，含 2 个 tab
  - `frontend/src/components/pricing/PricingListTab.vue` — "定价表" tab（卡片列表 + 搜索 + 新增）
  - `frontend/src/components/pricing/PricingCard.vue` — 单个定价卡片
  - `frontend/src/components/pricing/ParamsTab.vue` — "参数" tab
  - `frontend/src/composables/usePricingCalc.js` — 纯计算 composable

### 复用现有基础设施

| 依赖 | 来源 |
|---|---|
| SKU 查询 | `products` 表 + `GET /api/products`（已有） |
| 类目/佣金率 | `commission_rates` 表 + `GET /api/commission/rates?platform=xxx`（已有） |
| 默认头程模板 | `shipping_templates` + `GET /api/shipping/default-template`（已有） |
| 图片上传 | `backend/app/uploads/` + 现有上传接口 |
| 全局参数持久化 | `system_settings` 表（key/value 方式，沿用 `default_shipping_template` 的做法） |

---

## 4. 数据模型

两张新表，位于 `backend/app/models/pricing.py`。

### 4.1 `pricing_items`

一条定价方案（一个商品 × 一种场景）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK int | |
| `name` | String(100) | 方案名，用户起，列表展示用 |
| `sku` | String(200), indexed, default="" | 可空 |
| `product_id` | int, FK(products.id), nullable | **软关联**：创建时快照复制，不维持引用 |
| `image_url` | String(500), default="" | 商品图片 URL |
| `purchase_cost` | Float | RMB |
| `weight_kg` | Float | |
| `length_cm`, `width_cm`, `height_cm` | Float | 体积/密度前端算，不存 |
| `wb_local_rate_id` | int, FK(commission_rates.id), nullable, `ON DELETE SET NULL` | |
| `wb_cross_rate_id` | int, FK(commission_rates.id), nullable, `ON DELETE SET NULL` | |
| `ozon_local_rate_id` | int, FK(commission_rates.id), nullable, `ON DELETE SET NULL` | |
| `created_at`, `updated_at` | DateTime | |

关系：`PricingItem.platforms` 一对多 `PricingPlatform`（cascade delete）。

### 4.2 `pricing_platforms`

一条定价方案在某个平台的定价输入。本期只写 `platform="wb_cross_fbs"` 的行。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK int | |
| `item_id` | int, FK(pricing_items.id), `ON DELETE CASCADE` | |
| `platform` | String(30) | `"wb_cross_fbs"`（本期）；未来：`"wb_cross_fbw"` / `"wb_local"` / `"ozon_local_fbs"` / `"ozon_local_fbo"` |
| `price_rub` | Float, default=0 | 定价（买家端） |
| `price_rmb` | Float, default=0 | 定价（卖家端） |
| `discount_pct` | Float, default=0 | 平台折扣 %（0–100） |
| `extra` | JSON, default={} | 平台特有字段预留，本期不用 |

**唯一约束**：`(item_id, platform)`。

### 4.3 设计取舍

**为什么用子表而不是宽列**：未来扩展 5 行时，只需加新的 `platform` 枚举值，不改 schema。

**为什么不存中间计算字段**（体积、密度、前台售价、利润、佣金、头程费用、利润率）：汇率/参数会变，存了反而要同步。显示时按**当前参数实时重算**。副作用：打开老条目显示的利润是"按当前参数"算出来的，不是创建时的快照——本期接受这个取舍。

**为什么软关联 Product**：用户需要能在定价表里独立编辑商品信息（规格试算），软关联避免回写 Product 表。代价：Product 表后续改了采购价，老定价条目不自动感知。

---

## 5. 参数 tab

5 个参数，存在 `system_settings` 表里，按 key 读写。

| key | 默认值 | 用途 |
|---|---|---|
| `pricing.rate_rub_cny` | 0.08 | RUB / RMB 汇率（1 RUB = ? RMB） |
| `pricing.rate_usd_cny` | 7.2 | USD / RMB 汇率 |
| `pricing.order_fee_threshold_kg` | 2.0 | 订单处理费重量阈值 |
| `pricing.order_fee_light` | 6.0 | 阈值以下的订单处理费（RMB） |
| `pricing.order_fee_heavy` | 10.0 | 阈值以上的订单处理费（RMB） |
| `pricing.withdrawal_rate` | 0.015 | 提现手续费率 |

**只存当前值**，改了就覆盖。不留历史。

---

## 6. 计算公式（WB 跨境 FBS）

用 `P.xxx` 引用参数 tab 里的参数，`I.xxx` 引用定价条目的字段。

### 6.1 基本信息区（左侧派生字段）

| 字段 | 公式 | 显示规则 |
|---|---|---|
| 体积 (m³) | `I.length × I.width × I.height / 1,000,000` | 保留 4 位小数 |
| 密度 (kg/m³) | `I.weight / 体积` | 保留 2 位小数；体积=0 时显示 `-` |

### 6.2 定价行（右侧 13 个字段）

| # | 字段 | 公式 | 备注 |
|---|---|---|---|
| 1 | 定价 (RUB) | 用户填 或 `I.price_rmb × P.rate_rub_cny` | 双向联动 |
| 2 | 定价 (RMB) | 用户填 或 `I.price_rub / P.rate_rub_cny` | 双向联动 |
| 3 | 平台折扣 (%) | 用户填 | 0–100 |
| 4 | 前台售价 (RUB) | `price_rub × (1 − discount_pct/100)` | 展示 |
| 5 | 头程单价 (USD) | 按密度匹配默认模板 | 见 6.3 边界 |
| 6 | 头程费用 (RMB) | `weight × 头程单价 × P.rate_usd_cny` | |
| 7 | 订单处理费 (RMB) | `weight < P.threshold_kg ? P.light_fee : P.heavy_fee` | 见 6.3 边界 |
| 8 | 尾程运费 (RMB) | `length × width × height / 1000 + 4` | 常量硬编码 |
| 9 | 佣金率 (%) | `commission_rates[wb_cross_rate_id].rate × 100` | 佣金表存小数（如 0.11），显示 ×100 |
| 10 | 佣金 (RMB) | `price_rmb × commission_rates[wb_cross_rate_id].rate` | 用小数形式算 |
| 11 | 提现手续费 (RMB) | `(price_rmb − 尾程运费 − 佣金) × P.withdrawal_rate` | |
| 12 | 利润 (RMB) | `price_rmb − (purchase_cost + 头程费用 + 订单处理费 + 尾程运费 + 佣金 + 提现手续费)` | |
| 13 | 利润率 (%) | `利润 / price_rmb × 100` | price_rmb=0 时显示 `-` |

### 6.3 边界条件

**B1 密度匹配头程单价区间**：
- 区间闭合规则：`density_min ≤ 密度 < density_max`
- 密度 < 所有 `min`（极轻货）→ 取第一档（兜底）
- 密度 ≥ 最大 `max`（极重货）→ 取最后一档（兜底）
- 默认模板未设置 → 头程单价显示 `-`

**B2 订单处理费 2kg 边界**：
- `weight < 2.0` → 6 元（light_fee）
- `weight >= 2.0` → 10 元（heavy_fee）
- 即 2.0 归入"以上"档

**B3 双向换算触发**：
- 用户最后编辑 RUB 字段 → RMB 自动算
- 用户最后编辑 RMB 字段 → RUB 自动算
- 前端用 `@input` 事件追踪"谁是源"

---

## 7. API 设计

### 7.1 CRUD

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| GET | `/api/pricing/items` | query: `page, page_size, search` | `{ items: [...], total: int }` |
| POST | `/api/pricing/items` | body: PricingItem + platforms 数组 | 新建的 item 对象 |
| GET | `/api/pricing/items/{id}` | — | item 对象 + platforms |
| PUT | `/api/pricing/items/{id}` | body: 同 POST | 更新后的 item |
| DELETE | `/api/pricing/items/{id}` | — | `{ detail: "Deleted" }` |

所有端点用 `Depends(require_module("pricing"))` 做权限校验。

POST/PUT 请求时，如果传了 `product_id`：
- 后端**忽略** body 里的 `image_url / purchase_cost / weight_kg / length_cm / width_cm / height_cm`
- **从 Product 表快照复制**这些字段（注意 Product 的图片字段叫 `image`，复制到 PricingItem 时存到 `image_url`）
- 创建后 `product_id` 仅作为溯源字段，不再联动（后续编辑 Product 不影响已建条目）
- **编辑时重新快照**：PUT 请求里如果 `product_id` 从 A 变成 B，按新的 product_id 重新复制字段；如果 `product_id` 不变，保留用户手动编辑过的值

### 7.2 参数

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| GET | `/api/pricing/params` | — | `{ rate_rub_cny: 0.08, rate_usd_cny: 7.2, ... }` |
| PUT | `/api/pricing/params` | body: 同上形状 | `{ detail: "Updated" }` |

读取时，某参数不存在就返回默认值；写入时批量 upsert 到 `system_settings`。

### 7.3 错误码

- 400：字段校验失败（如 discount_pct 不在 0–100）
- 403：无 pricing 模块权限
- 404：item/rate/product 不存在

---

## 8. 前端结构

### 8.1 页面布局

```
Pricing.vue
├── [el-tabs]
│   ├── Tab "定价表"
│   │   └── PricingListTab.vue
│   │       ├── [搜索栏] [新增按钮]
│   │       └── [PricingCard.vue × N]  ← 卡片列表,每条一张
│   │
│   └── Tab "参数"
│       └── ParamsTab.vue
│           └── [表单: 5 个参数 + 保存按钮]
```

### 8.2 PricingCard 卡片布局

```
┌─────────────────────────────────────────────────────────┐
│ [方案名] [SKU 搜索下拉]               [编辑] [删除]        │
├───────────────────────┬─────────────────────────────────┤
│ 左:基本信息             │ 右:WB 跨境 FBS 定价行           │
│ ┌─────┐                │                                 │
│ │图片  │                │ 定价 RUB [___]  定价 RMB [___] │
│ └─────┘                │ 折扣 [__]%                      │
│ 采购成本 [___]           │ 前台售价 XXXX RUB              │
│ 重量 [___]              │ 头程单价 X USD                  │
│ 长 [__] 宽 [__] 高 [__] │ 头程费用 XXX RMB                │
│ 体积 X.XXXX m³         │ 订单处理费 X RMB                 │
│ 密度 X kg/m³            │ 尾程运费 X RMB                  │
│                         │ 佣金率 X%  佣金 XXX             │
│ 类目:                   │ 提现手续费 XXX                  │
│  WB本土 [搜索下拉]       │ ───                            │
│  WB跨境 [搜索下拉]       │ 利润 XXX RMB                    │
│  OZON本土 [搜索下拉]     │ 利润率 X%                       │
└───────────────────────┴─────────────────────────────────┘
```

### 8.3 交互流

**新建定价条目**：

1. 点"新增"按钮 → 弹出表单（或直接在列表上方插入空卡片）
2. 用户可选：
   - a. 填 SKU 搜索框 → 从 Product 匹配 → 自动填左侧基本信息（图片/采购/重量/长宽高）
   - b. 不填 SKU → 手动填所有基本信息
3. 选三个类目（每个下拉按 platform 筛选 commission_rates）
4. 填定价 RUB 或 RMB（任一，另一个自动算）
5. 填折扣
6. 实时看所有派生字段
7. 点"保存" → POST `/api/pricing/items`

**编辑**：点卡片上"编辑"按钮 → 进入编辑态 → 改字段 → 保存 → PUT。

**删除**：点"删除" → confirm → DELETE。

**参数 tab**：表单编辑 5 个参数 → 点"保存" → PUT → 回到定价 tab，所有条目的计算结果跟着变（前端响应式）。

### 8.4 usePricingCalc composable

```js
export function usePricingCalc({ item, platformInput, params, commissionRates, shippingTemplate }) {
  // 所有入参都是 ref/reactive
  return computed(() => ({
    volume, density,
    frontPriceRub,
    headPriceUsd, headFee,
    orderFee,
    tailFee,
    commissionRatePct, commission,
    withdrawalFee,
    profit, profitRatePct,
  }))
}
```

纯函数（无副作用），接受原始字段输出派生字段。

---

## 9. 错误处理

### 9.1 前端计算缺失数据

| 场景 | 处理 |
|---|---|
| 长/宽/高任一为 0 → 体积=0 | 密度、尾程运费显示 `-` |
| 未选 WB 跨境类目 | 佣金率、佣金、提现手续费、利润 显示 `-` |
| 密度超出所有 ShippingRate 区间 | 按 B1：超小取第一档、超大取最后一档 |
| 默认头程模板未设置 | 头程单价、头程费用显示 `-`；页面顶部 banner 提示 |
| `price_rmb = 0` | 利润率显示 `-` |
| 参数 tab 某参数缺失 | 用内置默认值，banner 提示"请配置 xx 参数" |

### 9.2 后端

- 删 `PricingItem` → cascade 删 `pricing_platforms`（FK 定义保证）
- 删 `ShippingTemplate` / `SystemSetting` → 定价表实时显示 `-`，无需特殊处理
- 删 `CommissionRate` → FK `ON DELETE SET NULL`，前端检测 `rate_id=null` 显示"未选择"

---

## 10. 测试

### 10.1 后端 `backend/tests/test_pricing.py`（新建）

1. **CRUD 正常流**：create → get → list → update → delete
2. **参数读写**：初始值是默认、写入后读到新值、部分写入不影响其他参数
3. **SKU 软关联**：POST 带 `product_id` → 字段自动从 Product 快照；随后改 Product 的 purchase_price，老条目不变
4. **FK 级联**：delete `PricingItem` 后 `PricingPlatform` 行也删
5. **FK 置空**：删引用的 `CommissionRate`，对应 `rate_id` 变 null
6. **权限**：无 pricing 权限的用户请求任一端点返回 403

### 10.2 前端 `frontend/tests/usePricingCalc.test.js`（新建）

1. **基本计算**：给定一组已知输入，对比每个派生字段的预期值
2. **双向换算 B3**：改 RUB 字段 → RMB 跟着变；改 RMB → RUB 跟着变
3. **边界 B1**：密度在区间内 / 低于最小 / 高于最大 的头程单价取值
4. **边界 B2**：weight=1.9 → 6 元、weight=2.0 → 10 元、weight=2.1 → 10 元
5. **缺失数据**：类目未选、长宽高为 0、price_rmb=0 都返回合理值（体现 `-` 对应的 `null`），不抛错

---

## 11. 验收标准

实现完成后，逐条验证：

1. [ ] 左侧菜单新增"定价表"项（admin 可见；通过权限配置后其他用户可见）
2. [ ] 打开页面看到 2 个 tab："定价表"（默认） / "参数"
3. [ ] **新建**：点"新增" → 填方案名 → 选 SKU（自动填商品数据）或留空 → 选三个类目 → 填定价 → 保存
4. [ ] **不选 SKU 也能新建**：手动填商品信息也能保存成功
5. [ ] **体积/密度实时算**：改任一长宽高或重量即时更新
6. [ ] **双向换算**：填 RMB → RUB 自动；反之亦然
7. [ ] **所有派生字段联动**：改折扣/类目/定价/长宽高/重量，所有下游字段跟着变
8. [ ] **参数 tab 改汇率**：回到定价 tab，所有卡片的计算结果跟着变
9. [ ] **编辑**：每张卡片可编辑
10. [ ] **删除**：删除前 confirm，删后列表刷新
11. [ ] **搜索**：按 SKU 或方案名搜索列表
12. [ ] **未设置默认头程模板时**：页面顶部 banner 提示，头程字段显示 `-`
13. [ ] **后端 pytest 全绿 + 前端 Vitest 全绿**

---

## 12. 未来扩展（非本期）

- 其他 4 行定价：FBW / WB 本土 / OZON FBS / OZON FBO（每行字段结构不同，复用 `PricingPlatform.extra` JSON 字段承载差异）
- 利润快照：每次保存时落一份"当前计算结果"到 `pricing_snapshots`，方便历史回溯
- 批量导入：Excel 上传一堆商品，自动生成定价条目
- 批量复制：一键为同一 SKU 复制多个方案
- 多币种：OZON 引入可能涉及 CNY 外的结算币种，参数 tab 扩展
