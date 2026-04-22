<template>
  <div class="ts-orders">
    <div class="ts-orders-toolbar">
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
      <el-checkbox v-model="onlyReturn" @change="refresh">仅退货</el-checkbox>
      <el-checkbox v-model="onlyUnmapped" @change="refresh">仅未映射</el-checkbox>
      <span class="ts-count">共 {{ total }} 条</span>
    </div>

    <el-table
      ref="tableRef"
      :data="items"
      stripe
      :fit="false"
      v-loading="loading"
      max-height="640"
      :row-class-name="rowClass"
      @expand-change="onExpand"
      @row-click="toggleExpand"
    >
      <el-table-column type="expand" width="40">
        <template #default="{ row }">
          <div class="ts-expand">
            <div><b>条码：</b>{{ row.barcode }}</div>
            <div><b>品类：</b>{{ row.category }}</div>
            <div><b>尺码：</b>{{ row.size }}</div>
            <div><b>仓库：</b>{{ row.warehouse }}</div>
            <div><b>国家：</b>{{ row.country }}</div>
            <div><b>销售方式：</b>{{ row.sale_type }}</div>
            <div><b>佣金金额：</b>{{ fmt(row.commission_amount) }} {{ symbol }}</div>
            <div><b>退货数：</b>{{ row.return_quantity }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="srid" label="订单号" width="180" show-overflow-tooltip />
      <el-table-column label="下单日期" width="100">
        <template #default="{ row }">{{ fmtDate(row.order_date) }}</template>
      </el-table-column>
      <el-table-column label="结算日期" width="100">
        <template #default="{ row }">{{ fmtDate(row.sale_date) }}</template>
      </el-table-column>
      <el-table-column prop="shop_sku" label="SKU" width="130" show-overflow-tooltip />
      <el-table-column label="产品名" width="150">
        <template #default="{ row }">
          <div class="ts-name-ru" :title="row.product_name">{{ truncate(row.product_name, 16) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="订单状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.order_status" :color="statusColor(row.order_status)" size="small" effect="dark" style="border:none;color:#fff">
            {{ statusLabel(row.order_status) }}
          </el-tag>
          <span v-else class="ts-missing">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="80" align="center" />
      <el-table-column label="售价" width="100" align="right">
        <template #default="{ row }">{{ fmt(row.sold_price) }}</template>
      </el-table-column>
      <el-table-column label="应付卖家" width="110" align="right">
        <template #default="{ row }">{{ fmt(row.net_to_seller) }}</template>
      </el-table-column>
      <el-table-column prop="commission_rate" label="佣金率%" width="80" align="center" />
      <el-table-column label="配送费" width="100" align="right">
        <template #default="{ row }">{{ fmt(row.delivery_fee) }}</template>
      </el-table-column>
      <el-table-column label="其他费用" width="100" align="right">
        <template #default="{ row }">{{ fmt(row.fine + row.storage_fee + row.deduction) }}</template>
      </el-table-column>
      <el-table-column label="采购成本" width="110" align="right">
        <template #default="{ row }">
          <span v-if="row.has_sku_mapping">{{ fmt(row.purchase_cost) }}</span>
          <span v-else class="ts-missing">—</span>
        </template>
      </el-table-column>
      <el-table-column label="净利润" width="110" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.net_profit >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }">
            {{ fmt(row.net_profit) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="映射状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.has_sku_mapping" type="success" size="small">已映射</el-tag>
          <el-tag v-else type="warning" size="small">未映射</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="ts-pagi"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @current-change="refresh"
      @size-change="refresh"
    />
  </div>
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
const emit = defineEmits(['reload'])

const items = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const onlyReturn = ref(false)
const onlyUnmapped = ref(false)
const sridSearch = ref('')
const tableRef = ref(null)

const symbol = computed(() => props.currency === 'CNY' ? '¥' : '₽')

async function refresh() {
  loading.value = true
  try {
    const params = {
      shop_type: props.shopType,
      page: page.value, page_size: pageSize.value,
    }
    if (props.shopId) params.shop_id = props.shopId
    if (props.dateFrom) params.date_from = props.dateFrom
    if (props.dateTo) params.date_to = props.dateTo
    if (props.orderDateFrom) params.order_date_from = props.orderDateFrom
    if (props.orderDateTo) params.order_date_to = props.orderDateTo
    if (onlyReturn.value) params.has_return = true
    if (onlyUnmapped.value) params.has_mapping = false
    if (sridSearch.value.trim()) params.srid = sridSearch.value.trim()
    const { data } = await api.get('/api/finance/orders', { params })
    items.value = data.items
    total.value = data.total
  } catch (e) { console.warn('orders error', e) }
  finally { loading.value = false }
}

function rowClass({ row }) {
  return row.has_sku_mapping ? '' : 'ts-row-missing'
}
function toggleExpand(row, col) {
  if (col?.type === 'expand') return
  tableRef.value?.toggleRowExpansion(row)
}
function onExpand() {}
function onSearch() { page.value = 1; refresh() }
function truncate(t, n) { return !t ? '' : t.length > n ? t.slice(0, n) + '…' : t }
function fmt(v) { return Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtDate(v) {
  if (!v) return ''
  const m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/)
  if (!m) return String(v)
  const date = `${m[1].slice(2)}/${parseInt(m[2])}/${parseInt(m[3])}`
  return m[4] ? `${date} ${m[4]}:${m[5]}` : date
}
const STATUS_MAP = { pending: '待发货', in_transit: '配送中', completed: '已完成', cancelled: '已取消', rejected: '已拒收', returned: '已退货' }
const STATUS_COLOR = { pending: '#606266', in_transit: '#409eff', completed: '#67c23a', cancelled: '#e6a23c', rejected: '#f56c6c', returned: '#909399' }
function statusLabel(s) { return STATUS_MAP[s] || s }
function statusColor(s) { return STATUS_COLOR[s] || '#909399' }

watch(() => [props.shopType, props.shopId, props.dateFrom, props.dateTo, props.orderDateFrom, props.orderDateTo], () => { page.value = 1; refresh() })
onMounted(refresh)
defineExpose({ refresh })
</script>

<style scoped>
.ts-orders { margin-top: 12px; }
.ts-orders-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }
.ts-count { color: #64748b; font-size: 13px; margin-left: auto; }
.ts-pagi { margin-top: 12px; justify-content: flex-end; }
.ts-name-ru { font-size: 13px; font-weight: 600; color: #1e293b; }
.ts-missing { color: #f59e0b; }
:deep(.ts-row-missing) { background: #fffbeb !important; }
.ts-expand { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px 24px; padding: 8px 16px; color: #475569; font-size: 13px; }
</style>
