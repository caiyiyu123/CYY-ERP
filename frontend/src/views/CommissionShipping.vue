<template>
  <el-card>
    <el-tabs v-model="mainTab">
      <!-- ====== 平台佣金 Tab ====== -->
      <el-tab-pane label="平台佣金" name="commission">
        <el-tabs v-model="platformTab" type="card" style="margin-bottom: 16px">
          <el-tab-pane label="WB本土" name="wb_local" />
          <el-tab-pane label="WB跨境" name="wb_cross_border" />
          <el-tab-pane label="OZON本土" name="ozon_local" />
        </el-tabs>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
          <div style="display: flex; align-items: center; gap: 12px">
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".xlsx,.xls"
              :on-change="onFileSelected"
            >
              <el-button type="primary">上传佣金表格</el-button>
            </el-upload>
            <span v-if="commissionInfo.filename" style="color: #909399; font-size: 13px">
              当前文件：{{ commissionInfo.filename }}（{{ commissionInfo.uploaded_at }}）
            </span>
          </div>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索类目/商品名"
            clearable
            style="width: 240px"
          />
        </div>

        <el-table :data="filteredRates" stripe max-height="600" v-loading="loadingRates">
          <el-table-column prop="category" label="类目" min-width="180" />
          <el-table-column prop="product_name" label="商品名称" min-width="180" />
          <el-table-column
            v-if="platformTab !== 'ozon_local'"
            prop="rate"
            label="佣金率(%)"
            width="120"
            align="center"
          />
          <el-table-column
            v-for="h in extraHeaders"
            :key="h"
            :prop="h"
            :label="h"
            width="140"
            align="center"
          />
        </el-table>
      </el-tab-pane>

      <!-- ====== 头程运费 Tab ====== -->
      <el-tab-pane label="头程运费" name="shipping">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
          <span style="font-size: 16px; font-weight: 500">运费模板</span>
          <el-button type="primary" @click="openShippingDialog()">新增运费模板</el-button>
        </div>

        <el-table :data="shippingTemplates" stripe v-loading="loadingTemplates">
          <el-table-column prop="name" label="头程名称" min-width="160" />
          <el-table-column prop="date" label="日期" width="130" align="center" />
          <el-table-column prop="rate_count" label="区间数" width="100" align="center" />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="openShippingDialog(row)">编辑</el-button>
              <el-popconfirm title="确定删除该模板?" @confirm="deleteTemplate(row.id)">
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

  <!-- 运费模板编辑对话框 -->
  <el-dialog v-model="showShippingDialog" :title="shippingForm.id ? '编辑运费模板' : '新增运费模板'" width="600px">
    <el-form :model="shippingForm" label-width="80px">
      <el-form-item label="头程名称">
        <el-input v-model="shippingForm.name" placeholder="如：空运-莫斯科" />
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker v-model="shippingForm.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="密度区间">
        <div style="width: 100%">
          <div
            v-for="(r, idx) in shippingForm.rates"
            :key="idx"
            style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px"
          >
            <el-input-number v-model="r.density_min" :min="0" :precision="1" placeholder="下限" controls-position="right" style="width: 130px" />
            <span>~</span>
            <el-input-number v-model="r.density_max" :min="0" :precision="1" placeholder="上限" controls-position="right" style="width: 130px" />
            <el-input-number v-model="r.price_usd" :min="0" :precision="2" placeholder="运费USD" controls-position="right" style="width: 140px" />
            <el-button :icon="Delete" circle size="small" @click="shippingForm.rates.splice(idx, 1)" />
          </div>
          <el-button type="primary" link @click="shippingForm.rates.push({ density_min: 0, density_max: 0, price_usd: 0 })">
            + 添加行
          </el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showShippingDialog = false">取消</el-button>
      <el-button type="primary" @click="saveTemplate">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import api from '../api'

// ==================== 佣金部分 ====================
const mainTab = ref('commission')
const platformTab = ref('wb_local')
const searchKeyword = ref('')
const commissionRates = ref([])
const extraHeaders = ref([])
const commissionInfo = reactive({ filename: null, uploaded_at: null })
const loadingRates = ref(false)

const filteredRates = computed(() => {
  if (!searchKeyword.value) return commissionRates.value
  const kw = searchKeyword.value.toLowerCase()
  return commissionRates.value.filter(
    r => r.category.toLowerCase().includes(kw) || r.product_name.toLowerCase().includes(kw)
  )
})

async function fetchCommissionRates() {
  loadingRates.value = true
  try {
    const { data } = await api.get('/api/commission/rates', { params: { platform: platformTab.value } })
    commissionRates.value = data.rates || []
    extraHeaders.value = data.headers || []
  } catch { ElMessage.error('加载佣金数据失败') }
  finally { loadingRates.value = false }
}

async function fetchCommissionInfo() {
  try {
    const { data } = await api.get('/api/commission/info', { params: { platform: platformTab.value } })
    commissionInfo.filename = data.filename
    commissionInfo.uploaded_at = data.uploaded_at ? new Date(data.uploaded_at).toLocaleString('zh-CN') : null
  } catch { /* ignore */ }
}

async function onFileSelected(file) {
  const formData = new FormData()
  formData.append('file', file.raw)
  try {
    loadingRates.value = true
    const { data } = await api.post(`/api/commission/upload?platform=${platformTab.value}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`上传成功，共 ${data.count} 条数据`)
    fetchCommissionRates()
    fetchCommissionInfo()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally { loadingRates.value = false }
}

watch(platformTab, () => {
  searchKeyword.value = ''
  fetchCommissionRates()
  fetchCommissionInfo()
})

// ==================== 运费模板部分 ====================
const shippingTemplates = ref([])
const loadingTemplates = ref(false)
const showShippingDialog = ref(false)
const shippingForm = reactive({ id: null, name: '', date: '', rates: [] })

async function fetchShippingTemplates() {
  loadingTemplates.value = true
  try {
    const { data } = await api.get('/api/shipping/templates')
    shippingTemplates.value = data
  } catch { ElMessage.error('加载运费模板失败') }
  finally { loadingTemplates.value = false }
}

function openShippingDialog(row) {
  if (row) {
    shippingForm.id = row.id
    shippingForm.name = row.name
    shippingForm.date = row.date
    shippingForm.rates = row.rates.map(r => ({ ...r }))
  } else {
    shippingForm.id = null
    shippingForm.name = ''
    shippingForm.date = ''
    shippingForm.rates = [{ density_min: 0, density_max: 0, price_usd: 0 }]
  }
  showShippingDialog.value = true
}

async function saveTemplate() {
  if (!shippingForm.name || !shippingForm.date) {
    ElMessage.warning('请填写名称和日期')
    return
  }
  const payload = { name: shippingForm.name, date: shippingForm.date, rates: shippingForm.rates }
  try {
    if (shippingForm.id) {
      await api.put(`/api/shipping/templates/${shippingForm.id}`, payload)
    } else {
      await api.post('/api/shipping/templates', payload)
    }
    showShippingDialog.value = false
    fetchShippingTemplates()
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteTemplate(id) {
  try {
    await api.delete(`/api/shipping/templates/${id}`)
    fetchShippingTemplates()
    ElMessage.success('删除成功')
  } catch { ElMessage.error('删除失败') }
}

onMounted(() => {
  fetchCommissionRates()
  fetchCommissionInfo()
  fetchShippingTemplates()
})
</script>
