<template>
  <el-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)"
             title="手动同步财务报告" width="600px" :close-on-click-modal="false">
    <div v-if="!running">
      <el-form label-width="100px">
        <el-form-item label="店铺">
          <el-select v-model="selectedShops" multiple placeholder="选择店铺（可多选）" style="width: 100%">
            <el-option v-for="s in shops" :key="s.id" :label="`${s.name} (${s.type === 'cross_border' ? 'CNY' : 'RUB'})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="快捷">
          <el-button size="small" @click="setRange('lastWeek')">上周</el-button>
          <el-button size="small" @click="setRange('last90d')">近 90 天（全历史）</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div v-else class="ts-progress">
      <div v-for="log in logs" :key="log.id" class="ts-log-row">
        <span class="ts-log-shop">{{ log.shop_name }}</span>
        <el-tag :type="statusType(log.status)" size="small">{{ statusLabel(log.status) }}</el-tag>
        <span v-if="log.status === 'success'" class="ts-log-stats">
          {{ log.rows_fetched }} 行 → {{ log.orders_merged }} 订单 + {{ log.other_fees_count }} 其他
        </span>
        <span v-if="log.status === 'failed'" class="ts-log-err" :title="log.error_message">
          {{ log.error_message || '失败' }}
        </span>
      </div>
    </div>

    <template #footer>
      <el-button @click="close" :disabled="running && !allDone">关闭</el-button>
      <el-button v-if="!running" type="primary" @click="startSync" :disabled="!canSubmit">
        开始同步
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

const shops = ref([])
const selectedShops = ref([])
const dateRange = ref(getLast90Range())
const running = ref(false)
const logs = ref([])
const pollTimer = ref(null)
let pollIds = []

function getLast90Range() {
  const end = new Date(); const start = new Date(end.getTime() - 89 * 86400000)
  const fmt = d => d.toISOString().slice(0, 10)
  return [fmt(start), fmt(end)]
}
function setRange(key) {
  const today = new Date(); const day = today.getDay() || 7
  const fmt = d => d.toISOString().slice(0, 10)
  if (key === 'lastWeek') {
    const lastMon = new Date(today.getTime() - (day + 6) * 86400000)
    const lastSun = new Date(today.getTime() - day * 86400000)
    dateRange.value = [fmt(lastMon), fmt(lastSun)]
  } else { dateRange.value = getLast90Range() }
}

const canSubmit = computed(() => selectedShops.value.length > 0 && dateRange.value && dateRange.value[0])
const allDone = computed(() => logs.value.length > 0 && logs.value.every(l => l.status !== 'running'))

async function fetchShops() {
  try {
    const { data } = await api.get('/api/shops')
    shops.value = data || []
  } catch (e) { console.warn('shops error', e) }
}

async function startSync() {
  try {
    const { data } = await api.post('/api/finance/sync', {
      shop_ids: selectedShops.value,
      date_from: dateRange.value[0], date_to: dateRange.value[1],
    })
    pollIds = data.sync_log_ids
    running.value = true
    logs.value = pollIds.map(id => ({ id, status: 'running', shop_name: '...' }))
    startPolling()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '触发同步失败')
  }
}

function startPolling() {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    try {
      const { data } = await api.get('/api/finance/sync-logs', { params: { ids: pollIds.join(',') } })
      logs.value = data
      if (data.every(l => l.status !== 'running')) {
        clearInterval(pollTimer.value); pollTimer.value = null
      }
    } catch (e) { console.warn('poll err', e) }
  }, 3000)
}

function statusType(s) { return s === 'success' ? 'success' : s === 'failed' ? 'danger' : 'info' }
function statusLabel(s) { return { running: '进行中', success: '完成', failed: '失败' }[s] || s }

function close() {
  if (pollTimer.value) { clearInterval(pollTimer.value); pollTimer.value = null }
  emit('update:modelValue', false)
  if (allDone.value) {
    window.dispatchEvent(new Event('finance-sync-done'))
  }
  setTimeout(() => { running.value = false; logs.value = [] }, 300)
}

watch(() => props.modelValue, v => { if (v) { fetchShops() } })
onMounted(fetchShops)
onUnmounted(() => { if (pollTimer.value) clearInterval(pollTimer.value) })
</script>

<style scoped>
.ts-progress { max-height: 400px; overflow-y: auto; padding: 8px; }
.ts-log-row { display: flex; gap: 10px; align-items: center; padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
.ts-log-shop { font-weight: 600; min-width: 140px; }
.ts-log-stats { color: #64748b; font-size: 12px; }
.ts-log-err { color: #dc2626; font-size: 12px; }
</style>
