<template>
  <div>
    <!-- 日期筛选 -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;">
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <el-button v-for="preset in presets" :key="preset.label"
          :type="activePreset === preset.label ? 'primary' : 'default'" size="small"
          @click="applyPreset(preset)">{{ preset.label }}</el-button>
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
          start-placeholder="开始日期" end-placeholder="结束日期" size="small"
          value-format="YYYY-MM-DD" @change="onDateChange" />
      </div>
    </div>

    <!-- KPI 卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="5" v-for="kpi in kpis" :key="kpi.label">
        <el-card shadow="hover">
          <div style="color: #999; font-size: 13px">{{ kpi.label }}</div>
          <div :style="{ fontSize: '24px', fontWeight: 'bold', marginTop: '6px', color: kpi.color || '' }">
            {{ kpi.prefix }}{{ kpi.value?.toLocaleString() }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-card style="margin-bottom: 20px">
      <template #header>推广趋势</template>
      <v-chart :option="chartOption" style="height: 280px" autoresize />
    </el-card>

    <!-- 广告活动列表 -->
    <el-card style="margin-bottom: 20px">
      <template #header>广告活动</template>
      <el-table :data="campaigns" stripe>
        <el-table-column prop="name" label="活动名称" min-width="180" />
        <el-table-column prop="type" label="类型" min-width="80">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: statusColor(row.status), fontWeight: 'bold' }">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_spend" label="花费" min-width="100">
          <template #default="{ row }">¥ {{ row.total_spend?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_views" label="展示" min-width="90">
          <template #default="{ row }">{{ row.total_views?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_clicks" label="点击" min-width="80">
          <template #default="{ row }">{{ row.total_clicks?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_orders" label="订单" min-width="70" />
        <el-table-column prop="roas" label="ROAS" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: row.roas >= 2 ? '#67c23a' : row.roas >= 1 ? '#e6a23c' : '#f56c6c', fontWeight: 'bold' }">
              {{ row.roas }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="$router.push(`/ads/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 商品推广排行 -->
    <el-card>
      <template #header>商品推广排行</template>
      <el-table :data="productStats" stripe>
        <el-table-column label="商品" min-width="200">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-image v-if="row.image_url" :src="row.image_url" style="width: 36px; height: 36px; border-radius: 4px" fit="cover">
                <template #error><span style="color: #ccc; font-size: 12px">无图</span></template>
              </el-image>
              <span>{{ row.product_name || '-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sku" label="产品SKU" min-width="120" />
        <el-table-column prop="total_spend" label="花费" min-width="100">
          <template #default="{ row }">¥ {{ row.total_spend?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_views" label="展示" min-width="90">
          <template #default="{ row }">{{ row.total_views?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_clicks" label="点击" min-width="80">
          <template #default="{ row }">{{ row.total_clicks?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="total_orders" label="订单" min-width="70" />
        <el-table-column prop="total_order_amount" label="订单金额" min-width="100">
          <template #default="{ row }">¥ {{ row.total_order_amount?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="roas" label="ROAS" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: row.roas >= 2 ? '#67c23a' : row.roas >= 1 ? '#e6a23c' : '#f56c6c', fontWeight: 'bold' }">
              {{ row.roas }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const overview = ref({})
const campaigns = ref([])
const productStats = ref([])
const dailyStats = ref([])
const dateRange = ref(null)
const activePreset = ref('近7天')

const today = new Date()
function fmt(d) { return d.toISOString().slice(0, 10) }
function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r }

const presets = [
  { label: '今日', from: fmt(today), to: fmt(today) },
  { label: '昨日', from: fmt(addDays(today, -1)), to: fmt(addDays(today, -1)) },
  { label: '近7天', from: fmt(addDays(today, -6)), to: fmt(today) },
  { label: '近30天', from: fmt(addDays(today, -29)), to: fmt(today) },
]

let currentFrom = presets[2].from
let currentTo = presets[2].to

function applyPreset(preset) {
  activePreset.value = preset.label
  currentFrom = preset.from
  currentTo = preset.to
  dateRange.value = null
  fetchAll()
}

function onDateChange(val) {
  if (val && val.length === 2) {
    activePreset.value = ''
    currentFrom = val[0]
    currentTo = val[1]
    fetchAll()
  }
}

const kpis = computed(() => [
  { label: '推广花费', value: overview.value.total_spend, prefix: '¥ ' },
  { label: '展示量', value: overview.value.total_views, prefix: '' },
  { label: '点击量', value: overview.value.total_clicks, prefix: '' },
  { label: '推广订单', value: overview.value.total_orders, prefix: '' },
  { label: 'ROAS', value: overview.value.roas, prefix: '', color: '#67c23a' },
])

const TYPE_MAP = { 5: '自动', 6: '搜索', 7: '卡片', 8: '推荐', 9: '搜索+推荐' }
const TYPE_TAG = { 5: 'success', 6: '', 7: 'warning', 8: '', 9: 'info' }
const STATUS_MAP = { 4: '准备中', 7: '进行中', 8: '审核中', 9: '已暂停', 11: '已结束' }
const STATUS_COLOR = { 4: '#909399', 7: '#67c23a', 8: '#e6a23c', 9: '#909399', 11: '#606266' }

function typeLabel(t) { return TYPE_MAP[t] || t }
function typeTagType(t) { return TYPE_TAG[t] || '' }
function statusLabel(s) { return STATUS_MAP[s] || s }
function statusColor(s) { return STATUS_COLOR[s] || '#606266' }

const chartOption = computed(() => {
  const byDate = {}
  for (const s of dailyStats.value) {
    const d = s.date
    if (!byDate[d]) byDate[d] = { spend: 0, order_amount: 0 }
    byDate[d].spend += s.spend
    byDate[d].order_amount += s.order_amount
  }
  const dates = Object.keys(byDate).sort()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['花费', '订单金额'] },
    grid: { left: 50, right: 30, bottom: 30, top: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: [
      { name: '花费', type: 'bar', data: dates.map(d => byDate[d].spend.toFixed(2)), itemStyle: { color: '#409eff' } },
      { name: '订单金额', type: 'line', data: dates.map(d => byDate[d].order_amount.toFixed(2)), itemStyle: { color: '#67c23a' } },
    ],
  }
})

async function fetchAll() {
  const params = { date_from: currentFrom, date_to: currentTo }
  const [ovRes, campRes, prodRes] = await Promise.all([
    api.get('/api/ads/overview', { params }),
    api.get('/api/ads/campaigns', { params }),
    api.get('/api/ads/product-stats', { params }),
  ])
  overview.value = ovRes.data
  campaigns.value = campRes.data
  productStats.value = prodRes.data

  const allStats = []
  for (const c of campRes.data) {
    try {
      const res = await api.get(`/api/ads/campaigns/${c.id}/stats`, { params })
      allStats.push(...res.data)
    } catch (e) { /* skip */ }
  }
  dailyStats.value = allStats
}

onMounted(fetchAll)
</script>
