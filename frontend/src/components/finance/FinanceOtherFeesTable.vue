<template>
  <el-collapse v-model="open">
    <el-collapse-item name="fees">
      <template #title>
        <span class="ts-title">其他费用 ({{ total }} 条)</span>
      </template>
      <div class="ts-fees-toolbar" @click.stop>
        <el-input
          v-model="sridSearch"
          placeholder="按订单号搜索"
          clearable
          size="small"
          style="width: 240px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-button size="small" type="primary" @click="onSearch">搜索</el-button>
      </div>
      <el-table :data="items" stripe :fit="false" v-loading="loading" max-height="400">
        <el-table-column prop="srid" label="订单号" width="200" show-overflow-tooltip />
        <el-table-column label="下单日期" width="100">
          <template #default="{ row }">{{ fmtDate(row.order_date) }}</template>
        </el-table-column>
        <el-table-column label="结算日期" width="100">
          <template #default="{ row }">{{ fmtDate(row.sale_date) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <el-tag :type="typeColor(row.fee_type)" size="small">{{ typeLabel(row.fee_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="140" align="right">
          <template #default="{ row }">{{ fmt(row.amount) }} {{ symbol }}</template>
        </el-table-column>
        <el-table-column prop="fee_description" label="描述" min-width="300" show-overflow-tooltip />
      </el-table>
      <el-pagination
        class="ts-fees-pagi"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @current-change="refresh"
        @size-change="refresh"
      />
    </el-collapse-item>
  </el-collapse>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '../../api'

const props = defineProps({
  shopType: String, shopId: [Number, null],
  dateFrom: String, dateTo: String,
  orderDateFrom: String, orderDateTo: String,
  currency: String,
})
const open = ref([])
const items = ref([])
const total = ref(0)
const loading = ref(false)
const sridSearch = ref('')
const page = ref(1)
const pageSize = ref(50)
const symbol = computed(() => props.currency === 'CNY' ? '¥' : '₽')

const TYPE_LABEL = { storage: '仓储', fine: '罚款', deduction: '扣款', logistics_adjust: '物流调整', other: '其他' }
const TYPE_COLOR = { storage: 'info', fine: 'danger', deduction: 'warning', logistics_adjust: '', other: '' }
function typeLabel(t) { return TYPE_LABEL[t] || t }
function typeColor(t) { return TYPE_COLOR[t] || '' }
function fmt(v) { return Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtDate(v) {
  if (!v) return ''
  const m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/)
  if (!m) return String(v)
  const date = `${m[1].slice(2)}/${parseInt(m[2])}/${parseInt(m[3])}`
  return m[4] ? `${date} ${m[4]}:${m[5]}` : date
}

async function refresh() {
  loading.value = true
  try {
    const params = { shop_type: props.shopType, page: page.value, page_size: pageSize.value }
    if (props.shopId) params.shop_id = props.shopId
    if (props.dateFrom) params.date_from = props.dateFrom
    if (props.dateTo) params.date_to = props.dateTo
    if (props.orderDateFrom) params.order_date_from = props.orderDateFrom
    if (props.orderDateTo) params.order_date_to = props.orderDateTo
    if (sridSearch.value.trim()) params.srid = sridSearch.value.trim()
    const { data } = await api.get('/api/finance/other-fees', { params })
    items.value = data.items
    total.value = data.total
    if (total.value > 0 && !open.value.includes('fees')) open.value.push('fees')
  } catch (e) { console.warn('other-fees error', e) }
  finally { loading.value = false }
}

function onSearch() { page.value = 1; refresh() }

watch(() => [props.shopType, props.shopId, props.dateFrom, props.dateTo, props.orderDateFrom, props.orderDateTo], () => { page.value = 1; refresh() })
onMounted(refresh)
</script>

<style scoped>
.ts-title { font-weight: 600; color: #1e293b; }
.ts-fees-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }
.ts-fees-pagi { margin-top: 12px; justify-content: flex-end; }
</style>
