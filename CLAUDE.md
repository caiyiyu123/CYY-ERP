# CYY-ERP 项目文档

## 1. 项目概述

**CYY-ERP**（内部代号 `TS-ERP`）是一套面向 **Wildberries（俄罗斯电商平台）** 的跨境电商 ERP 系统，用于管理多个 WB 店铺的订单、商品、库存、广告投放、财务对账等业务。

**业务背景**：
- 用户同时经营多个 WB 店铺，既有"跨境店"也有"本土店"（俄罗斯本地仓）
- 需要统一管理多店铺的订单状态、销售数据、利润核算
- 需要和国内自有 SKU / 采购价 / 物流成本对齐，计算真实利润
- 需要定期从 WB 开放平台 API 拉取数据并本地汇总分析

**解决的核心问题**：
- WB 后台分散，多店切换繁琐 → 一个系统汇总
- WB 财务报表字段晦涩（俄语 + WB 自有术语）→ 翻译 + 分类呈现
- WB 订单 / 销售 / 财报数据需按 `srid` 关联 → 自动合并
- 跨境店铺的 SKU 和国内采购 SKU 不一致 → SKU 映射表
- 日常经营决策需要数据看板、采购计划、库存预警

---

## 2. 技术栈

### 后端
| 组件 | 版本 / 选型 |
|------|------|
| 框架 | FastAPI >= 0.115 |
| ASGI | uvicorn / gunicorn（生产） |
| ORM | SQLAlchemy 2.x (Mapped / mapped_column) |
| Schema | Pydantic v2 |
| 数据库 | PostgreSQL（生产 / Railway）、SQLite（本地开发） |
| 认证 | python-jose（JWT） + bcrypt |
| 敏感字段加密 | cryptography（Fernet） |
| 定时任务 | APScheduler 3.10.4 |
| HTTP 客户端 | httpx |
| Excel 处理 | openpyxl |
| 测试 | pytest + pytest-asyncio |

### 前端
| 组件 | 版本 / 选型 |
|------|------|
| 框架 | Vue 3.5 (Composition API, `<script setup>`) |
| 构建 | Vite 8 |
| UI 库 | Element Plus 2.13 + @element-plus/icons-vue |
| 路由 | vue-router 4 |
| 状态 | Pinia 3 |
| 图表 | ECharts 6 + vue-echarts |
| HTTP | axios |

### 部署
- **后端**：Railway（NIXPACKS builder + gunicorn），PostgreSQL 插件
- **前端**：Vercel（Vite 静态构建）或 Docker + nginx（`Dockerfile` + `nginx.conf.template`）

---

## 3. 项目目录结构

```
CYY-ERP/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 入口，含启动时自动迁移
│   │   ├── config.py              # 环境变量 / DATABASE_URL / SECRET_KEY / Fernet
│   │   ├── database.py            # engine / SessionLocal / Base
│   │   ├── models/                # SQLAlchemy 2.x ORM 模型
│   │   │   ├── shop.py            # 店铺 + API token + 回溯游标
│   │   │   ├── user.py            # 用户 + 权限模块 + user_shops 关联表
│   │   │   ├── product.py         # Product / ShopProduct / SkuMapping
│   │   │   ├── order.py           # Order / OrderItem / OrderStatusLog
│   │   │   ├── inventory.py       # FBS / FBW 库存
│   │   │   ├── finance.py         # FinanceOrderRecord / FinanceOtherFee / FinanceSyncLog
│   │   │   ├── ad.py              # AdCampaign / AdDailyStat
│   │   │   ├── commission.py      # 佣金 / 运费费率表
│   │   │   ├── purchase_plan.py   # 采购计划
│   │   │   ├── ai_api_key.py      # AI 接口密钥
│   │   │   └── setting.py         # 系统迁移标记 / 键值对
│   │   ├── routers/               # FastAPI 路由（按模块拆分）
│   │   │   ├── auth.py            # 登录 / JWT
│   │   │   ├── users.py           # 用户管理
│   │   │   ├── shops.py           # 店铺管理
│   │   │   ├── products.py        # 国内商品库
│   │   │   ├── shop_products.py   # 店铺 WB 商品
│   │   │   ├── sku_mappings.py    # SKU 映射
│   │   │   ├── orders.py          # 订单
│   │   │   ├── inventory.py       # 库存
│   │   │   ├── finance.py         # 财务统计 / 同步 / 对账
│   │   │   ├── dashboard.py       # 数据看板
│   │   │   ├── ads.py             # 广告
│   │   │   ├── customer_service.py # 评价 / 问题 / 聊天（代理 WB API）
│   │   │   ├── commission_shipping.py # 佣金 / 运费费率
│   │   │   ├── purchase_plan.py   # 采购计划
│   │   │   └── ai_keys.py         # AI 密钥管理
│   │   ├── services/              # 业务逻辑
│   │   │   ├── wb_api.py          # 所有 WB API 调用封装 + 限流
│   │   │   ├── sync.py            # 订单 / 库存 / 广告 / 商品同步
│   │   │   ├── finance_sync.py    # 财报拉取 + srid 合并 + 成本/利润计算
│   │   │   ├── backfill.py        # 慢速回溯历史数据（hourly）
│   │   │   ├── scheduler.py       # APScheduler 注册
│   │   │   └── translate.py       # 俄文翻译辅助
│   │   ├── schemas/               # Pydantic v2 请求/响应模型
│   │   ├── utils/
│   │   │   ├── security.py        # 密码哈希 / JWT / Fernet token 加解密
│   │   │   └── deps.py            # get_current_user / require_module / get_accessible_shop_ids
│   │   └── uploads/               # 上传文件存储目录
│   ├── tests/                     # pytest 测试
│   │   ├── conftest.py
│   │   ├── test_auth.py / test_finance.py / test_orders.py ... （约 12 个测试文件）
│   ├── Procfile                   # Heroku/Railway 启动命令
│   ├── railway.json               # Railway 部署配置
│   ├── requirements.txt
│   ├── create_admin.py            # CLI：创建初始管理员
│   └── wb_erp.db                  # 本地 SQLite（开发用，已 .gitignore）
├── frontend/
│   ├── src/
│   │   ├── main.js                # Vue 入口
│   │   ├── App.vue
│   │   ├── router/index.js        # 所有路由 + 权限 meta.module
│   │   ├── stores/                # Pinia（auth）
│   │   ├── api/                   # axios 封装
│   │   ├── brand.js               # APP_TITLE / Logo
│   │   ├── theme.css / style.css
│   │   ├── views/                 # 页面组件（17 个页面）
│   │   │   ├── Login.vue / Layout.vue / Dashboard.vue
│   │   │   ├── Orders.vue / OrderDetail.vue
│   │   │   ├── Products.vue / ShopProducts.vue / SkuMappings.vue
│   │   │   ├── PurchasePlan.vue / Inventory.vue
│   │   │   ├── Finance.vue（+ components/finance/*）
│   │   │   ├── AdsOverview.vue / AdDetail.vue
│   │   │   ├── CustomerService.vue / CommissionShipping.vue
│   │   │   ├── Shops.vue / Users.vue
│   │   └── components/
│   │       ├── ImageUploader.vue
│   │       └── finance/           # 财务页的子组件
│   │           ├── FinanceTabContent.vue（跨境店/本土店 tab 壳）
│   │           ├── FinanceSummaryCards.vue（汇总卡片）
│   │           ├── FinanceOrdersTable.vue（订单明细）
│   │           ├── FinanceOtherFeesTable.vue（其他费用）
│   │           ├── FinanceReconciliation.vue（对账）
│   │           └── FinanceSyncDialog.vue（同步对话框）
│   ├── vite.config.js             # /api + /uploads 代理到 :8000
│   ├── vercel.json                # Vercel rewrites（SPA fallback）
│   ├── Dockerfile / nginx.conf.template / start.sh
│   └── package.json
├── docs/
│   └── superpowers/               # 设计文档 / 实现计划存放处
├── CLAUDE.md                      # 本文档
└── .gitignore
```

---

## 4. 核心模块说明

### 4.1 认证与权限（`auth` / `users`）
- **登录**：`POST /api/auth/login`，JWT 24h
- **权限模型**：每个 `User` 有 `permissions`（逗号分隔模块名）和 `user_shops` 关联表
- **admin 角色**绕过所有权限检查
- 所有业务路由用 `Depends(require_module("xxx"))` 做模块级校验
- 非 admin 用户只能看自己绑定的店铺（`get_accessible_shop_ids`）
- 模块白名单：见 `User.ALL_MODULES`

### 4.2 店铺管理（`shops`）
- 每个店铺记录 WB API Token（用 **Fernet 加密**存 `api_token` 字段）
- `type` 区分 `cross_border`（跨境店）和 `local`（本土店）
- `orders_backfill_cursor` / `finance_backfill_cursor`：慢速回溯游标

### 4.3 商品与 SKU 映射（`products` / `shop_products` / `sku_mappings`）
- `Product`：国内商品主档（SKU、采购价、重量、体积、实际运费）
- `ShopProduct`：WB 店铺上架商品（nm_id、title、图片、售价、评分）
- `SkuMapping`：**关键表** — 店铺 `shop_sku` ↔ `product_id` 关联
  - 没有映射的订单 → 采购成本 = 0，利润算不准
  - WB 财报里的 `sa_name` 就是 `shop_sku`

### 4.4 订单（`orders`）
- `Order.srid`：WB 的**订单唯一标识**（= `wb_order_id` 的语义等价）
- 订单来源：WB Marketplace `/api/v3/orders` + Statistics `/api/v1/supplier/orders`
- 状态映射见 [sync.py](backend/app/services/sync.py)：`pending / in_transit / completed / cancelled / rejected / returned`

### 4.5 库存（`inventory`）
- FBS：卖家仓库存（`/api/v3/stocks/{warehouseId}`）
- FBW：WB 仓库存（`/api/v1/supplier/stocks`）
- 分别按 `shop_id + sku` 唯一

### 4.6 广告（`ads`）
- `AdCampaign`（活动）+ `AdDailyStat`（按 `campaign+nm_id+date` 唯一的日报）
- 数据来源：`/adv/v1/promotion/adverts`、`/adv/v2/fullstats` 等

### 4.7 财务（`finance`）—— 最复杂的模块
- **输入**：WB `/api/v5/supplier/reportDetailByPeriod` 返回的周报 / 按周期报表
- **核心表**：
  - `FinanceOrderRecord`：按 `shop_id + srid` 唯一的订单级财务记录（销售收入、佣金、配送费、罚款、仓储、扣款、采购成本、净利润）
  - `FinanceOtherFee`：纯费用行（无销售的仓储/罚款/扣款/物流调整）
  - `FinanceSyncLog`：同步任务日志
- **合并逻辑**（[finance_sync.py](backend/app/services/finance_sync.py)）：
  - 原始财报按 `srid` 分组
  - 有销售或退货行的 srid → 进 `FinanceOrderRecord`
  - 只有费用行的 srid 或无 srid 的行 → 进 `FinanceOtherFee`
  - `fee_type` 枚举：`storage / fine / deduction / logistics_adjust / other`
- **成本与利润**：通过 `SkuMapping → Product.purchase_price` 填充
- **前端**：`Finance.vue` 带 tab 切换（跨境 / 本土），下面汇总卡片 + 订单表 + 其他费用表 + 对账

### 4.8 数据看板（`dashboard`）
- 聚合订单、销售、库存、广告等核心指标

### 4.9 采购计划（`purchase_plan`）
- 按采购日期、操作员、快递费等生成采购单，关联 `Product`

### 4.10 佣金运费（`commission_shipping`）
- 自行维护的佣金率表 / 运费模板，用于成本核算参考

### 4.11 评价客服（`customer_service`）
- 后端代理转发 WB Feedbacks / Questions / Chat API
- 不存本地数据库，实时从 WB 拉取

### 4.12 AI 密钥（`ai_keys`）
- 用户自己的 AI API Key 管理（翻译等用途）

---

## 5. 数据库结构

### 核心表关系

```
users ──< user_shops >── shops ──< orders ──< order_items
                           │          │
                           │          └── order_status_logs
                           │
                           ├──< inventories
                           │
                           ├──< sku_mappings >── products
                           │                       │
                           │                       └──< purchase_plan_items >── purchase_plans
                           │
                           ├──< shop_products
                           ├──< ad_campaigns ──< ad_daily_stats
                           ├──< finance_order_records
                           ├──< finance_other_fees
                           └──< finance_sync_logs
```

### 关键设计点
- **srid 贯穿**：`orders.srid` ↔ `finance_order_records.srid` ↔ `finance_other_fees.srid` 是跨表关联的锚点
- **shop_id 作为租户边界**：几乎所有业务表都带 `shop_id`
- **敏感字段加密**：`shops.api_token` 用 Fernet 加密，读取时 `decrypt_token()`
- **启动时自动迁移**：[backend/app/main.py](backend/app/main.py) 在启动时通过 `ALTER TABLE ADD COLUMN` 兼容老库
- **系统标记**：`system_settings` 表用键值对记录一次性迁移是否跑过（如 `weight_migrated_to_kg`）

---

## 6. 外部 API 集成（Wildberries）

**文件**：[backend/app/services/wb_api.py](backend/app/services/wb_api.py)

| Base URL | 用途 |
|---|---|
| `marketplace-api.wildberries.ru` | FBS 订单、仓库、库存、上架商品 |
| `statistics-api.wildberries.ru` | 历史订单、销售、财报 |
| `advert-api.wildberries.ru` | 广告活动、统计 |
| `feedbacks-api.wildberries.ru` | 评价 / 问题 |
| `buyer-chat-api.wildberries.ru` | 买家聊天 |

### 已接入的 endpoint
| 函数 | WB endpoint | 说明 |
|------|-------------|------|
| `fetch_new_orders` | `GET /api/v3/orders/new` | 新 FBS 订单 |
| `fetch_orders` | `GET /api/v3/orders` | 历史订单（30 天窗口分页） |
| `fetch_order_statuses` | `POST /api/v3/orders/status` | 订单状态批量查询 |
| `fetch_warehouses` | `GET /api/v3/warehouses` | 仓库列表 |
| `fetch_stocks` / `fetch_fbw_stocks` | `/api/v3/stocks/{wh}` / `/api/v1/supplier/stocks` | FBS / FBW 库存 |
| `fetch_cards` | `POST /content/v2/get/cards/list` | 商品卡片 |
| `fetch_product_prices` | Discount API | 价格与折扣 |
| `fetch_product_ratings` | Feedbacks API | 评分 / 评价数 |
| `fetch_statistics_orders` / `fetch_statistics_sales` | `/api/v1/supplier/orders` 等 | 统计订单/销售 |
| `fetch_report_detail` | 旧版财报 | 保留兼容 |
| `fetch_finance_report` | `/api/v5/supplier/reportDetailByPeriod` | **主财报**（含 429 指数退避） |
| `fetch_ad_campaign_ids` / `fetch_ad_details` / `fetch_ad_fullstats` / `fetch_ad_budget` / `fetch_ad_campaign_names` | Advert API | 广告 |
| `fetch_public_rub_prices` | 公开 wbstatic | 卢布转价 |
| `fetch_feedbacks` / `reply_feedback` | `/api/v1/feedbacks` | 评价 |
| `fetch_questions` / `reply_question` | `/api/v1/questions` | 问题 |
| `fetch_chats` / `fetch_chat_messages` / `send_chat_message` | Buyer Chat | 聊天 |

### 限流与重试
- 全局 200ms 最小间隔（`_throttle` + threading.Lock）
- 财报 429 响应：60s 初始退避，指数翻倍到 300s，最多 3 次

---

## 7. 环境变量

在 `backend/` 根目录放 `.env`（已 `.gitignore`），生产环境在 Railway 面板设置：

| 变量名 | 说明 | 必需 |
|---|---|---|
| `DATABASE_URL` | 数据库连接串，Railway 会自动注入 PostgreSQL；留空则用本地 SQLite | 生产必需 |
| `WB_ERP_SECRET_KEY` | JWT 签名密钥（>= 32 字节随机） | 生产必需 |
| `WB_ERP_FERNET_KEY` | Fernet 加密密钥（32 字节，urlsafe base64） | 生产必需 |
| `ADMIN_DEFAULT_PASSWORD` | 首次启动创建的 admin 密码（默认 `admin123`） | 可选 |
| `CORS_ORIGINS` | 逗号分隔的允许前端域名，默认 `http://localhost:5173` | 生产必需 |
| `TEST_MODE` | 跑测试时置 `1`，跳过建表（conftest 接管） | 仅测试 |
| `PORT` | Railway 注入，无需手动设置 | 自动 |

前端构建时通过 Vercel env 注入 `VITE_API_BASE_URL`（如有，需看 `src/api/*.js`，默认走同域 `/api`）。

---

## 8. 本地运行

### 后端
```bash
cd backend
python -m venv venv
venv/Scripts/activate              # Windows (bash/PowerShell 略有差异)
pip install -r requirements.txt
# 第一次跑会自动建表 + 创建 admin/admin123
python -m uvicorn app.main:app --reload --port 8000
```
- Swagger：`http://localhost:8000/docs`
- 健康检查：`/api/health`

### 前端
```bash
cd frontend
npm install
npm run dev        # 默认 http://localhost:5173，已代理 /api → :8000
```

### 测试
```bash
cd backend
set TEST_MODE=1 && pytest -q       # Windows cmd
TEST_MODE=1 pytest -q              # bash
```

### 创建管理员（如需）
```bash
cd backend && python create_admin.py
```

---

## 9. 部署（Railway）

### 后端
1. Railway 新建项目，连 Git 仓库 `backend/` 目录为根
2. 添加 **PostgreSQL** 插件，`DATABASE_URL` 会自动注入
3. 环境变量手动设置：`WB_ERP_SECRET_KEY`、`WB_ERP_FERNET_KEY`、`CORS_ORIGINS`（填前端域名）
4. NIXPACKS 会自动识别 Python，`railway.json` / `Procfile` 定义启动命令：
   ```
   gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
   ```
5. 首次部署会自动建表并创建 `admin` 用户（密码用 `ADMIN_DEFAULT_PASSWORD` 或默认 `admin123`，**务必登录后改密码**）

### 前端
- **Vercel**（推荐）：连仓库，`frontend/` 作为 Root Directory，走 `vercel.json`
- **Docker/nginx**：用 `frontend/Dockerfile` + `nginx.conf.template`，`start.sh` 会 `envsubst` 注入后端域名

### 注意事项
- `postgres://` 开头的 URL 在代码里被替换为 `postgresql://`（SQLAlchemy 要求）
- 启动时会跑一段 "Auto-migration" ALTER TABLE 逻辑（见 main.py），部署老库不会丢数据
- Railway 免费层会休眠，APScheduler 任务会断 — 需要 Pro 或外部唤醒

---

## 10. 当前已完成 / TODO

### 已完成
- 多店铺用户 + 细粒度模块权限
- WB API token 加密存储
- 订单同步（全量 + 增量）、状态映射、订单详情
- 库存同步（FBS / FBW）
- 商品同步（卡片、价格、评分）、SKU 映射维护
- 广告活动 + 日统计同步、推广详情页
- **财务模块**（重点）：财报同步、srid 合并、采购成本填充、利润核算、对账、其他费用分类
- 采购计划、佣金运费费率
- 数据看板
- 评价 / 问题 / 聊天（WB 代理，不落库）
- 定时器：每 30 分钟增量同步 + 每周一财报同步 + 每小时慢速回溯
- 启动时自动列迁移（ALTER TABLE ADD COLUMN）

### 待补充 / TODO
- 待补充

---

## 11. 约定与规范

### 代码风格
- 后端：SQLAlchemy 2.x `Mapped[...] = mapped_column(...)` 新式 ORM（不用老式 `Column`）
- 后端：Pydantic v2 风格的 schema
- 前端：Vue 3 `<script setup>`，Composition API，不用 Options API
- 前端：Element Plus 组件，颜色 / 间距用 theme.css 变量

### 命名
- 路由：`/api/<模块>/<动作>`，小写下划线
- 前端组件：PascalCase（`FinanceOrdersTable.vue`）
- 数据库表：复数 snake_case（`finance_order_records`）
- 枚举值：英文小写下划线（`pending`、`logistics_adjust`）

### Git
- 提交前须经用户同意（见 `memory/feedback_git_push.md`）
- 修改代码需要重启服务时必须提示用户

### 分支
- 待补充

---

## 12. 常见坑 / 注意事项

### WB API
- **srid = 订单 ID**：同一订单在 orders/sales/finance 三个 API 里都用 srid 串联（见 `memory/project_wb_order_id_srid.md`）
- **30 天窗口**：`/api/v3/orders` 单次返回约 30 天数据，需要循环拉
- **财报 89 天窗口**：`reportDetailByPeriod` 单窗口上限 89 天（见 `memory/project_wb_api_history_limits.md`）
- **历史起点**：主店铺 2025-01 开始才有财报，回溯从 `2025-01-01` 起（见 `memory/project_wb_shop_start_date.md`）
- **429 限流**：WB 会毫无预警返回 `too many requests`；财报接口已做指数退避，其他接口用全局 200ms 间隔
- **俄语字段**：`supplier_oper_name` 是俄文（`Продажа / Возврат / Логистика / Штраф / Хранение / Удержания / Платная приёмка / Возмещение ...`）—— 扩展枚举映射时一定考虑
- **财报字段**：金额字段分散在 `penalty / storage_fee / deduction / delivery_rub / ppvz_for_pay / rebill_logistic_cost / ppvz_reward / acceptance` 等多个列，`_fee_amount` 要全部探测

### WB 业务语义
- **拒收订单**：买家拒收时，财报里会记只有配送费/佣金的扣款行，**产品字段为空**（`brand_name / sa_name / subject_name` 全空），`net_to_seller=0`。这些行财务上真实（必须计入扣款），但订单展示上冗余
- **FBS vs FBW**：两者库存、同步路径不同
- **本土店 vs 跨境店**：货币、仓库、结算规则都不同 —— 前端财务 tab 区分展示

### 数据库
- **SQLite 单写锁**：本地开发时若起了多个 `uvicorn --reload`，会出现 `database is locked`；先确认只跑一份
- **启动迁移**：加字段后，老部署要走 main.py 的 `ALTER TABLE` 分支；新字段记得在迁移块补上
- **数值精度**：金额全部 `Float`，累加时注意浮点误差（比较用 `abs(a-b) < 1e-9`）

### 前端
- **`el-table` 默认不拉伸**：写 `:fit="false"` + 每列 `width`（见 `memory/feedback_table_no_stretch.md`、`memory/feedback_layout.md`）
- **大表一定分页**：本土店财报 7000+ 行，一次性渲染会卡死；后端带 `page/page_size`，前端加 `el-pagination`
- **路由权限 meta.module**：新页面必须加 `meta: { module: 'xxx' }`，对应 `User.ALL_MODULES`

### 开发流程
- **不随意修改用户脚本**：见 `memory/feedback_no_modify_prompts.md`
- **重启提示**：代码改完后要让用户重启时必须明确提示（见 `memory/feedback_restart_reminder.md`）

---

## 13. 常用命令速查

```bash
# 后端开发
cd backend && python -m uvicorn app.main:app --reload --port 8000

# 前端开发
cd frontend && npm run dev

# 跑测试
cd backend && set TEST_MODE=1 && pytest -q

# 查看后端进程（Windows）
tasklist | findstr python

# DB 交互（SQLite 本地）
cd backend && python -c "from app.database import SessionLocal; db=SessionLocal(); ..."
```

---

> 此文档用于 Claude Code 在新对话中快速理解项目上下文，请在开始任何任务前先阅读本文档。
