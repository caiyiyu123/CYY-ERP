<template>
  <div>
    <el-page-header @back="$router.push('/ads')" style="margin-bottom: 20px">
      <template #content>
        <span style="font-size: 18px; font-weight: bold; color: var(--ts-text-heading)">{{ campaign.name || '广告活动详情' }}</span>
        <el-tag :type="typeTagType(campaign.type)" size="small" style="margin-left: 10px">{{ typeLabel(campaign.type) }}</el-tag>
        <span :style="{ color: statusColor(campaign.status), fontWeight: 'bold', marginLeft: '10px' }">{{ statusLabel(campaign.status) }}</span>
      </template>
    </el-page-header>

    <div style="display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap;">
      <el-button v-for="preset in presets" :key="preset.label"
        :type="activePreset === preset.label ? 'primary' : 'default'" size="small"
        @click="applyPreset(preset)">{{ preset.label }}</el-button>
      <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
        start-placeholder="开始日期" end-placeholder="结束日期" size="small"
        value-format="YYYY-MM-DD" @change="onDateChange" />
    </div>

    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="4" v-for="kpi in kpis" :key="kpi.label">
        <el-card shadow="hover">
          <div class="ts-stat-label">{{ kpi.label }}</div>
          <div :style="{ fontSize: '20px', fontWeight: 'bold', marginTop: '4px', color: kpi.color || 'var(--ts-text-heading)' }">
            {{ kpi.prefix }}{{ kpi.value?.toLocaleString() }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 20px">
      <template #header>每日趋势</template>
      <v-chart :option="chartOption" style="height: 280px" autoresize />
    </el-card>

    <el-card>
      <template #header>商品明细</template>
      <el-table :data="productAgg" stripe>
        <el-table-column prop="nm_id" label="商品ID" min-width="100" />
        <el-table-column prop="spend" label="花费" min-width="90">
          <template #default="{ row }">¥ {{ row.spend?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="views" label="展示" min-width="90">
          <template #default="{ row }">{{ row.views?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="clicks" label="点击" min-width="80" />
        <el-table-column prop="ctr" label="CTR" min-width="70">
          <template #default="{ row }">{{ row.ctr }}%</template>
        </el-table-column>
        <el-table-column prop="orders" label="订单" min-width="70" />
        <el-table-column prop="order_amount" label="订单金额" min-width="100">
          <template #default="{ row }">¥ {{ row.order_amount?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="roas" label="ROAS" min-width="80">
          <template #default="{ row }">
            <span :style="{ color: row.roas >= 2 ? '#22c55e' : row.roas >= 1 ? '#f59e0b' : '#ef4444', fontWeight: 'bold' }">
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
import { useRoute } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const route = useRoute()
const campaignId = route.params.id

const campaign = ref({})
const stats = ref([])
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
  fetchData()
}

function onDateChange(val) {
  if (val && val.length === 2) {
    activePreset.value = ''
    currentFrom = val[0]
    currentTo = val[1]
    fetchData()
  }
}

const TYPE_MAP = { 5: '自动', 6: '搜索', 7: '卡片', 8: '推荐', 9: '搜索+推荐' }
const TYPE_TAG = { 5: 'success', 6: '', 7: 'warning', 8: '', 9: 'info' }
const STATUS_MAP = { 4: '准备中', 7: '进行中', 8: '审核中', 9: '已暂停', 11: '已结束' }
const STATUS_COLOR = { 4: '#64748b', 7: '#22c55e', 8: '#f59e0b', 9: '#64748b', 11: '#64748b' }

function typeLabel(t) { return TYPE_MAP[t] || t }
function typeTagType(t) { return TYPE_TAG[t] || '' }
function statusLabel(s) { return STATUS_MAP[s] || s }
function statusColor(s) { return STATUS_COLOR[s] || '#606266' }

const totals = computed(() => {
  let spend = 0, views = 0, clicks = 0, orders = 0, order_amount = 0, atbs = 0
  for (const s of stats.value) {
    spend += s.spend; views += s.views; clicks += s.clicks
    orders += s.orders; order_amount += s.order_amount; atbs += s.atbs
  }
  const roas = spend > 0 ? (order_amount / spend).toFixed(2) : 0
  const ctr = views > 0 ? (clicks / views * 100).toFixed(2) : 0
  return { spend, views, clicks, orders, order_amount, atbs, roas: Number(roas), ctr: Number(ctr) }
})

const kpis = computed(() => [
  { label: '花费', value: totals.value.spend, prefix: '¥ ' },
  { label: '展示', value: totals.value.views, prefix: '' },
  { label: '点击', value: totals.value.clicks, prefix: '' },
  { label: 'CTR', value: totals.value.ctr, prefix: '', color: '#3b82f6' },
  { label: '订单', value: totals.value.orders, prefix: '' },
  { label: 'ROAS', value: totals.value.roas, prefix: '', color: '#22c55e' },
])

const productAgg = computed(() => {
  const map = {}
  for (const s of stats.value) {
    if (!map[s.nm_id]) map[s.nm_id] = { nm_id: s.nm_id, spend: 0, views: 0, clicks: 0, orders: 0, order_amount: 0 }
    const m = map[s.nm_id]
    m.spend += s.spend; m.views += s.views; m.clicks += s.clicks
    m.orders += s.orders; m.order_amount += s.order_amount
  }
  return Object.values(map).map(m => ({
    ...m,
    spend: Math.round(m.spend * 100) / 100,
    order_amount: Math.round(m.order_amount * 100) / 100,
    ctr: m.views > 0 ? (m.clicks / m.views * 100).toFixed(2) : '0.00',
    roas: m.spend > 0 ? (m.order_amount / m.spend).toFixed(2) : '0.00',
  })).sort((a, b) => b.spend - a.spend)
})

const chartOption = computed(() => {
  const byDate = {}
  for (const s of stats.value) {
    if (!byDate[s.date]) byDate[s.date] = { spend: 0, order_amount: 0 }
    byDate[s.date].spend += s.spend
    byDate[s.date].order_amount += s.order_amount
  }
  const dates = Object.keys(byDate).sort()
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e5e7eb',
      textStyle: { color: '#1e293b', fontFamily: 'Plus Jakarta Sans' },
    },
    legend: { data: ['花费', '订单金额'], textStyle: { color: '#64748b' } },
    grid: { left: 50, right: 30, bottom: 30, top: 40 },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8' },
    },
    series: [
      { name: '花费', type: 'bar', data: dates.map(d => byDate[d].spend.toFixed(2)), itemStyle: { color: '#3b82f6' } },
      { name: '订单金额', type: 'line', data: dates.map(d => byDate[d].order_amount.toFixed(2)), itemStyle: { color: '#f59e0b' }, smooth: true },
    ],
  }
})

async function fetchData() {
  const params = { date_from: currentFrom, date_to: currentTo }
  try {
    const campRes = await api.get('/api/ads/campaigns', { params })
    campaign.value = campRes.data.find(c => c.id === Number(campaignId)) || {}
  } catch (e) { /* skip */ }
  try {
    const res = await api.get(`/api/ads/campaigns/${campaignId}/stats`, { params })
    stats.value = res.data
  } catch (e) {
    stats.value = []
  }
}

onMounted(fetchData)
</script>
