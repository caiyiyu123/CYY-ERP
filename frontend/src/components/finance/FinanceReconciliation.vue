<template>
  <el-collapse v-model="open">
    <el-collapse-item name="recon">
      <template #title>
        <span class="ts-title">对账
          <el-tag v-if="totalDiff > 0" type="danger" size="small" effect="dark" style="margin-left: 8px">
            {{ totalDiff }} 条差异
          </el-tag>
          <el-tag v-else type="success" size="small" effect="plain" style="margin-left: 8px">无差异</el-tag>
        </span>
      </template>

      <div class="ts-section-label">财报多（Orders 未同步的订单，共 {{ missingInOrders.length }} 条）</div>
      <el-table :data="missingInOrders" stripe :fit="false" max-height="280" v-loading="loading">
        <el-table-column prop="srid" label="订单号" width="260" show-overflow-tooltip />
        <el-table-column prop="shop_name" label="店铺" width="140" />
        <el-table-column label="下单日期" width="100">
          <template #default="{ row }">{{ fmtDate(row.order_date) }}</template>
        </el-table-column>
        <el-table-column label="结算日期" width="100">
          <template #default="{ row }">{{ fmtDate(row.sale_date) }}</template>
        </el-table-column>
        <el-table-column label="应付卖家" width="130" align="right">
          <template #default="{ row }">{{ fmt(row.net_to_seller) }} {{ row.currency === 'CNY' ? '¥' : '₽' }}</template>
        </el-table-column>
      </el-table>

      <div class="ts-section-label" style="margin-top: 16px">
        Orders 多（财报未结算的订单，共 {{ missingInFinance.length }} 条）
      </div>
      <el-table :data="missingInFinance" stripe :fit="false" max-height="280" v-loading="loading">
        <el-table-column prop="srid" label="订单号" width="260" show-overflow-tooltip />
        <el-table-column prop="shop_name" label="店铺" width="140" />
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">{{ fmtDate(String(row.created_at || '').slice(0, 10)) }}</template>
        </el-table-column>
        <el-table-column label="订单状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :color="statusColor(row.status)" size="small" effect="dark" style="border:none;color:#fff">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_price" label="金额" width="120" align="right">
          <template #default="{ row }">{{ fmt(row.total_price) }}</template>
        </el-table-column>
      </el-table>
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
})
const open = ref([])
const missingInOrders = ref([])
const missingInFinance = ref([])
const loading = ref(false)
const totalDiff = computed(() => missingInOrders.value.length + missingInFinance.value.length)

function fmt(v) { return Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
const STATUS_MAP = { pending: '待发货', in_transit: '配送中', completed: '已完成', cancelled: '已取消', rejected: '已拒收', returned: '已退货' }
const STATUS_COLOR = { pending: '#606266', in_transit: '#409eff', completed: '#67c23a', cancelled: '#e6a23c', rejected: '#f56c6c', returned: '#909399' }
function statusLabel(s) { return STATUS_MAP[s] || s || '—' }
function statusColor(s) { return STATUS_COLOR[s] || '#909399' }
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
    const params = { shop_type: props.shopType }
    if (props.shopId) params.shop_id = props.shopId
    if (props.dateFrom) params.date_from = props.dateFrom
    if (props.dateTo) params.date_to = props.dateTo
    if (props.orderDateFrom) params.order_date_from = props.orderDateFrom
    if (props.orderDateTo) params.order_date_to = props.orderDateTo
    const { data } = await api.get('/api/finance/reconciliation', { params })
    missingInOrders.value = data.missing_in_orders
    missingInFinance.value = data.missing_in_finance
    if (totalDiff.value > 0 && !open.value.includes('recon')) open.value.push('recon')
  } catch (e) { console.warn('recon error', e) }
  finally { loading.value = false }
}

watch(() => [props.shopType, props.shopId, props.dateFrom, props.dateTo, props.orderDateFrom, props.orderDateTo], refresh)
onMounted(refresh)
</script>

<style scoped>
.ts-title { font-weight: 600; color: #1e293b; }
.ts-section-label { font-size: 13px; color: #475569; margin: 6px 0; }
</style>
