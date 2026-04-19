<template>
  <el-card>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="店铺管理" name="shops">
        <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
          <el-button v-if="isAdmin" type="primary" @click="openDialog()">添加店铺</el-button>
        </div>
        <el-table :data="shops" stripe>
          <el-table-column prop="name" label="店铺名称" />
          <el-table-column prop="type" label="类型">
            <template #default="{ row }">
              <el-tag :type="row.type === 'local' ? 'success' : 'warning'">{{ row.type === 'local' ? '本土' : '跨境' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最后同步">
            <template #default="{ row }">{{ formatTime(row.last_sync_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <el-button size="small" @click="openDialog(row)">编辑</el-button>
              <el-button size="small" type="success" @click="$router.push(`/shops/${row.id}/sku-mappings`)">SKU关联</el-button>
              <el-button size="small" type="warning" :loading="syncing === row.id" @click="syncShop(row.id)">同步</el-button>
              <el-popconfirm v-if="isAdmin" title="确定删除该店铺？此操作不可恢复！" confirm-button-text="确认删除" cancel-button-text="取消" confirm-button-type="danger" @confirm="deleteShop(row.id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane v-if="isAdmin" label="汇率设置" name="rates">
        <!-- 卢布汇率 -->
        <div style="margin-bottom: 20px">
          <div style="font-size: 15px; font-weight: bold; margin-bottom: 10px">卢布汇率 <span style="color: #bbb; font-size: 12px; font-weight: normal">(对本土店使用)</span></div>
          <div style="display: flex; align-items: flex-start; gap: 20px; flex-wrap: wrap">
            <div>
              <div style="font-size: 13px; color: #606266; margin-bottom: 4px">人民币 → 卢布</div>
              <el-input-number :model-value="exchangeRate" :precision="2" :step="0.1" :min="0" style="width: 160px" @change="onRubCnyChange" />
              <div style="color: #bbb; font-size: 12px; margin-top: 2px">1 CNY = {{ exchangeRate }} RUB</div>
            </div>
            <div>
              <div style="font-size: 13px; color: #606266; margin-bottom: 4px">卢布 → 人民币</div>
              <el-input-number :model-value="exchangeRateRev" :precision="4" :step="0.001" :min="0" style="width: 160px" @change="onRubRevChange" />
              <div style="color: #bbb; font-size: 12px; margin-top: 2px">1 RUB = {{ exchangeRateRev }} CNY</div>
            </div>
            <el-button type="primary" size="small" style="margin-top: 22px" @click="saveRate('cny_rub')">保存</el-button>
          </div>
        </div>
        <!-- 美元汇率 -->
        <div>
          <div style="font-size: 15px; font-weight: bold; margin-bottom: 10px">美元汇率 <span style="color: #bbb; font-size: 12px; font-weight: normal">(对头程运费使用)</span></div>
          <div style="display: flex; align-items: flex-start; gap: 20px; flex-wrap: wrap">
            <div>
              <div style="font-size: 13px; color: #606266; margin-bottom: 4px">人民币 → 美元</div>
              <el-input-number :model-value="exchangeRateUsd" :precision="4" :step="0.01" :min="0" style="width: 160px" @change="onUsdCnyChange" />
              <div style="color: #bbb; font-size: 12px; margin-top: 2px">1 CNY = {{ exchangeRateUsd }} USD</div>
            </div>
            <div>
              <div style="font-size: 13px; color: #606266; margin-bottom: 4px">美元 → 人民币</div>
              <el-input-number :model-value="exchangeRateUsdRev" :precision="2" :step="0.1" :min="0" style="width: 160px" @change="onUsdRevChange" />
              <div style="color: #bbb; font-size: 12px; margin-top: 2px">1 USD = {{ exchangeRateUsdRev }} CNY</div>
            </div>
            <el-button type="primary" size="small" style="margin-top: 22px" @click="saveRate('cny_usd')">保存</el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isAdmin" label="AI-API KEY" name="aikeys">
        <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
          <el-button type="primary" @click="openAiKeyDialog()">添加API KEY</el-button>
        </div>
        <el-table :data="aiKeys" stripe>
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="model" label="模型" min-width="200" />
          <el-table-column prop="api_key_masked" label="API KEY" min-width="200" />
          <el-table-column label="创建时间" min-width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button size="small" @click="openAiKeyDialog(row)">编辑</el-button>
              <el-popconfirm title="确定删除？" @confirm="deleteAiKey(row.id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <el-dialog v-model="showAiKeyDialog" :title="aiKeyForm.id ? '编辑 API KEY' : '添加 API KEY'" width="500px">
    <el-form :model="aiKeyForm" label-width="100px">
      <el-form-item label="名称">
        <el-input v-model="aiKeyForm.name" placeholder="请输入名称" />
      </el-form-item>
      <el-form-item label="模型">
        <el-input v-model="aiKeyForm.model" placeholder="请输入模型名" />
      </el-form-item>
      <el-form-item label="API KEY">
        <el-input v-model="aiKeyForm.api_key" type="password" show-password :placeholder="aiKeyForm.id ? '留空则不修改' : '请输入 API KEY'" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showAiKeyDialog = false">取消</el-button>
      <el-button type="primary" @click="saveAiKey">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="showDialog" :title="form.id ? '编辑店铺' : '添加店铺'" width="500px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="店铺名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.type">
          <el-option label="本土" value="local" />
          <el-option label="跨境" value="cross_border" />
        </el-select>
      </el-form-item>
      <el-form-item label="API Token"><el-input v-model="form.api_token" type="password" show-password /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showDialog = false">取消</el-button>
      <el-button type="primary" @click="saveShop">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

const activeTab = ref('shops')
const shops = ref([])
const showDialog = ref(false)
const syncing = ref(null)
const defaultForm = { id: null, name: '', type: 'local', api_token: '' }
const form = reactive({ ...defaultForm })
const exchangeRate = ref(0)
const exchangeRateRev = ref(0)
const exchangeRateUsd = ref(0)
const exchangeRateUsdRev = ref(0)

const aiKeys = ref([])
const showAiKeyDialog = ref(false)
const defaultAiKeyForm = { id: null, name: '', model: '', api_key: '' }
const aiKeyForm = reactive({ ...defaultAiKeyForm })

function onRubCnyChange(val) {
  exchangeRate.value = val
  exchangeRateRev.value = val ? parseFloat((1 / val).toFixed(4)) : 0
}
function onRubRevChange(val) {
  exchangeRateRev.value = val
  exchangeRate.value = val ? parseFloat((1 / val).toFixed(2)) : 0
}
function onUsdCnyChange(val) {
  exchangeRateUsd.value = val
  exchangeRateUsdRev.value = val ? parseFloat((1 / val).toFixed(2)) : 0
}
function onUsdRevChange(val) {
  exchangeRateUsdRev.value = val
  exchangeRateUsd.value = val ? parseFloat((1 / val).toFixed(4)) : 0
}

function formatTime(dt) {
  if (!dt) return '-'
  const utcDt = String(dt).endsWith('Z') ? dt : dt + 'Z'
  return new Date(utcDt).toLocaleString('zh-CN', { timeZone: 'Europe/Moscow' })
}

async function fetchShops() {
  const { data } = await api.get('/api/shops')
  shops.value = data
}

function openDialog(row) {
  if (row) {
    Object.assign(form, { ...row, api_token: '' })
  } else {
    Object.assign(form, defaultForm)
  }
  showDialog.value = true
}

async function saveShop() {
  try {
    if (form.id) {
      const payload = { name: form.name, type: form.type }
      if (form.api_token) payload.api_token = form.api_token
      await api.put(`/api/shops/${form.id}`, payload)
    } else {
      const { name, type, api_token } = form
      await api.post('/api/shops', { name, type, api_token })
    }
    showDialog.value = false
    fetchShops()
    ElMessage.success('保存成功')
  } catch (e) {
    console.error('Shop save error:', e)
    const msg = e.response?.data?.detail || e.message || '保存失败'
    ElMessage.error(`保存失败: ${msg}`)
  }
}

async function deleteShop(id) {
  await api.delete(`/api/shops/${id}`)
  fetchShops()
  ElMessage.success('删除成功')
}

let syncPollTimer = null

async function syncShop(id) {
  if (syncing.value === id) return
  syncing.value = id
  try {
    await api.post(`/api/shops/${id}/sync`)
    // Poll for completion
    let pollCount = 0
    syncPollTimer = setInterval(async () => {
      pollCount++
      if (pollCount > 60) {
        clearInterval(syncPollTimer)
        syncPollTimer = null
        syncing.value = null
        ElMessage.warning('同步超时，请稍后重试')
        return
      }
      try {
        const { data } = await api.get(`/api/shops/${id}/sync-status`)
        if (data.status === 'done') {
          clearInterval(syncPollTimer)
          syncPollTimer = null
          syncing.value = null
          ElMessage.success('同步完成')
          fetchShops()
        } else if (data.status === 'error') {
          clearInterval(syncPollTimer)
          syncPollTimer = null
          syncing.value = null
          ElMessageBox.alert(data.detail || '未知错误', '同步失败', { type: 'error', confirmButtonText: '确定' })
        }
      } catch {
        clearInterval(syncPollTimer)
        syncPollTimer = null
        syncing.value = null
      }
    }, 3000)
  } catch {
    ElMessage.error('同步请求失败')
    syncing.value = null
  }
}

async function fetchExchangeRate() {
  try {
    const { data } = await api.get('/api/shops/exchange-rates')
    exchangeRate.value = data.cny_rub || 0
    exchangeRateRev.value = exchangeRate.value ? parseFloat((1 / exchangeRate.value).toFixed(4)) : 0
    exchangeRateUsd.value = data.cny_usd || 0
    exchangeRateUsdRev.value = exchangeRateUsd.value ? parseFloat((1 / exchangeRateUsd.value).toFixed(2)) : 0
  } catch {}
}

async function saveRate(type) {
  try {
    const rate = type === 'cny_rub' ? exchangeRate.value : exchangeRateUsd.value
    await api.put('/api/shops/exchange-rate', { type, rate })
    ElMessage.success('汇率已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function fetchAiKeys() {
  try {
    const { data } = await api.get('/api/ai-keys')
    aiKeys.value = data
  } catch {}
}

function openAiKeyDialog(row) {
  if (row) {
    Object.assign(aiKeyForm, { id: row.id, name: row.name, model: row.model, api_key: '' })
  } else {
    Object.assign(aiKeyForm, defaultAiKeyForm)
  }
  showAiKeyDialog.value = true
}

async function saveAiKey() {
  if (!aiKeyForm.name || !aiKeyForm.model) {
    ElMessage.warning('请填写名称和模型')
    return
  }
  if (!aiKeyForm.id && !aiKeyForm.api_key) {
    ElMessage.warning('请填写 API KEY')
    return
  }
  try {
    if (aiKeyForm.id) {
      const payload = { name: aiKeyForm.name, model: aiKeyForm.model }
      if (aiKeyForm.api_key) payload.api_key = aiKeyForm.api_key
      await api.put(`/api/ai-keys/${aiKeyForm.id}`, payload)
    } else {
      await api.post('/api/ai-keys', { name: aiKeyForm.name, model: aiKeyForm.model, api_key: aiKeyForm.api_key })
    }
    showAiKeyDialog.value = false
    fetchAiKeys()
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteAiKey(id) {
  try {
    await api.delete(`/api/ai-keys/${id}`)
    fetchAiKeys()
    ElMessage.success('删除成功')
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchShops()
  fetchExchangeRate()
  if (isAdmin.value) fetchAiKeys()
})

onUnmounted(() => {
  if (syncPollTimer) {
    clearInterval(syncPollTimer)
    syncPollTimer = null
  }
})
</script>
