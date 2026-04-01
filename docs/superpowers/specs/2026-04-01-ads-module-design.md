# 推广数据模块设计

## 概述

为韬盛ERP新增WB推广数据模块，对接Wildberries广告推广API（`advert-api.wildberries.ru`），同步广告活动数据并计算ROAS（广告回报率），支持按活动维度和商品维度分析推广效果。

## 需求总结

- 同步WB推广数据到ERP，展示花费、展示、点击、转化等效果
- 结合广告API自带的订单数据计算ROAS（ROAS = 订单金额 / 推广花费）
- 支持按广告活动维度和按商品维度两种分析视角
- 支持预设快捷时间（今日/昨日/近7天/近30天）+ 自定义日期范围
- 导航放在"商品管理"下作为子菜单

## 数据模型

### ad_campaigns — 广告活动表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 主键 |
| shop_id | Integer, FK → shops.id | 所属店铺 |
| wb_advert_id | Integer, unique, indexed | WB广告活动ID |
| name | String(500) | 活动名称 |
| type | Integer | 活动类型（5=自动, 6=搜索, 7=商品卡片, 8=推荐, 9=搜索+推荐） |
| status | Integer | WB状态（4=准备中, 7=进行中, 8=审核中, 9=暂停, 11=已结束） |
| daily_budget | Float, default=0 | 日预算 |
| create_time | DateTime | WB端创建时间 |
| updated_at | DateTime | 最后同步时间 |

### ad_daily_stats — 广告每日统计表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 主键 |
| campaign_id | Integer, FK → ad_campaigns.id | 所属广告活动 |
| nm_id | Integer | 商品nmId |
| date | Date | 统计日期 |
| views | Integer, default=0 | 展示量 |
| clicks | Integer, default=0 | 点击量 |
| ctr | Float, default=0 | 点击率(%) |
| cpc | Float, default=0 | 单次点击费用 |
| spend | Float, default=0 | 花费金额 |
| orders | Integer, default=0 | 订单数 |
| order_amount | Float, default=0 | 订单金额 |
| atbs | Integer, default=0 | 加购数 |
| cr | Float, default=0 | 转化率(%) |

唯一约束：`(campaign_id, nm_id, date)`，防止重复写入。

ROAS不存储，查询时计算：`ROAS = SUM(order_amount) / SUM(spend)`。

## WB广告API对接

Base URL: `https://advert-api.wildberries.ru`

认证方式：请求头 `Authorization: <api_token>`，与现有订单API共用同一个token。

### 获取广告活动列表

1. `GET /adv/v1/promotion/count` — 获取各状态的活动ID列表
2. `POST /adv/v1/promotion/adverts` — 批量获取活动详情（名称、类型、状态、预算、创建时间）

### 获取统计数据

`POST /adv/v2/fullstats` — 按活动ID + 日期范围获取每日统计，数据按nmId细分。

请求参数：活动ID列表 + beginDate + endDate（YYYY-MM-DD格式），最大查询周期31天。

返回字段映射：
- `views` → views
- `clicks` → clicks
- `ctr` → ctr
- `cpc` → cpc
- `sum` → spend（花费）
- `orders` → orders
- `sum_price` → order_amount（订单金额）
- `atbs` → atbs（加购数）
- `cr` → cr（转化率）

## 同步逻辑

### sync_shop_ads(db, shop)

新增函数，在 `sync.py` 中实现：

1. 调用 `GET /adv/v1/promotion/count` 获取所有活动ID（所有状态）
2. 调用 `POST /adv/v1/promotion/adverts` 批量获取活动详情，创建/更新 `ad_campaigns` 记录
3. 对进行中(7) + 暂停(9) + 已结束(11)的活动，调用 `POST /adv/v2/fullstats` 拉取每日统计
4. 按 `(campaign_id, nm_id, date)` 去重写入 `ad_daily_stats`

### 同步策略

- 首次同步：拉取最近30天数据
- 增量同步：拉取最近7天数据（覆盖WB可能的数据修正）
- 复用现有APScheduler，在 `sync_all_shops()` 中增加 `sync_shop_ads()` 调用，与订单同步共享30分钟周期
- 手动同步（`POST /api/shops/{shop_id}/sync`）同时触发推广数据同步

## 后端API路由

新增 `routers/ads.py`，前缀 `/api/ads`。

### GET /api/ads/overview

推广总览数据。

查询参数：`shop_id`(可选), `date_from`(必填), `date_to`(必填)

返回：
```json
{
  "total_spend": 2847.0,
  "total_views": 156432,
  "total_clicks": 3218,
  "total_orders": 47,
  "total_order_amount": 9740.0,
  "roas": 3.42
}
```

### GET /api/ads/campaigns

广告活动列表（含汇总统计）。

查询参数：`shop_id`(可选), `status`(可选), `date_from`, `date_to`

返回：活动列表，每个活动包含基本信息 + 该日期范围内的汇总统计（spend, views, clicks, orders, order_amount, roas）。

### GET /api/ads/campaigns/{id}/stats

单个活动的每日统计明细。

查询参数：`date_from`, `date_to`

返回：该活动下各商品(nm_id)的每日统计数据列表。

### GET /api/ads/product-stats

按商品维度汇总推广数据。

查询参数：`shop_id`(可选), `date_from`, `date_to`

返回：按nm_id汇总的推广数据列表（total_spend, total_views, total_clicks, total_orders, total_order_amount, roas），关联商品名称和SKU。

## 前端页面

### 导航结构

"商品管理"从单一链接改为展开子菜单：

```
商品管理 (Goods icon) [展开]
  ├─ 商品列表        /products
  └─ 推广数据        /ads
```

### 路由

| 路由 | 组件 | 说明 |
|------|------|------|
| `/ads` | AdsOverview.vue | 推广总览 |
| `/ads/:id` | AdDetail.vue | 活动详情钻取 |

### AdsOverview.vue — 推广总览

页面从上到下分为5个区域：

1. **日期筛选栏** — 快捷按钮（今日/昨日/近7天/近30天）+ 自定义日期选择器（Element Plus DatePicker）
2. **KPI卡片行** — 5个卡片：推广花费、展示量、点击量、推广订单、ROAS（绿色高亮）
3. **推广趋势图** — 使用ECharts展示按天的花费和订单金额折线/柱状混合图
4. **广告活动列表** — 表格展示每个活动的核心数据，点击"详情"按钮进入活动详情页
5. **商品推广排行** — 按商品汇总的推广效果表格，含商品图片、SKU、花费、ROAS等

### AdDetail.vue — 活动详情

- 顶部：活动名称、类型、状态、日预算、创建时间
- 日期筛选：与总览页相同的日期选择组件
- KPI卡片：该活动的汇总数据
- 商品明细表：该活动下每个商品(nm_id)的推广数据
- 每日趋势图：该活动的每日花费和效果趋势

## 广告类型和状态映射

### 类型映射（前端显示）

| type值 | 中文标签 | Tag颜色 |
|--------|---------|---------|
| 5 | 自动 | 绿色 |
| 6 | 搜索 | 蓝色 |
| 7 | 卡片 | 橙色 |
| 8 | 推荐 | 紫色 |
| 9 | 搜索+推荐 | 青色 |

### 状态映射（前端显示）

| status值 | 中文标签 | 颜色 |
|----------|---------|------|
| 4 | 准备中 | 灰色 |
| 7 | 进行中 | 绿色 |
| 8 | 审核中 | 橙色 |
| 9 | 已暂停 | 灰色 |
| 11 | 已结束 | 深灰色 |

## 文件清单

### 后端新增

| 文件 | 说明 |
|------|------|
| `app/models/ad.py` | AdCampaign、AdDailyStat 数据模型 |
| `app/schemas/ad.py` | 请求/响应 schema |
| `app/routers/ads.py` | API路由（4个端点） |

### 后端修改

| 文件 | 修改内容 |
|------|---------|
| `app/services/wb_api.py` | 新增3个函数：fetch_ad_campaigns、fetch_ad_details、fetch_ad_stats |
| `app/services/sync.py` | 新增 sync_shop_ads() 函数 |
| `app/models/__init__.py` | 导入新模型 |
| `app/main.py` | 注册 ads router |
| `app/routers/shops.py` | 手动同步时调用 sync_shop_ads |
| `app/services/scheduler.py` | sync_all_shops 中调用 sync_shop_ads |

### 前端新增

| 文件 | 说明 |
|------|------|
| `src/views/AdsOverview.vue` | 推广总览页面 |
| `src/views/AdDetail.vue` | 活动详情页面 |

### 前端修改

| 文件 | 修改内容 |
|------|---------|
| `src/views/Layout.vue` | "商品管理"改为展开子菜单，增加"推广数据"项 |
| `src/router/index.js` | 新增 /ads 和 /ads/:id 路由 |
