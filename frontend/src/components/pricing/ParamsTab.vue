<template>
  <div style="max-width: 500px">
    <el-form v-loading="loading" label-width="180px">
      <el-form-item label="RUB→RMB 汇率">
        <el-input-number v-model="params.rate_rub_cny" :precision="4" :step="0.001" :min="0.0001" />
        <span style="margin-left: 8px; color: #909399">1 RUB = ? RMB</span>
      </el-form-item>
      <el-form-item label="USD→RMB 汇率">
        <el-input-number v-model="params.rate_usd_cny" :precision="2" :step="0.1" :min="0.01" />
        <span style="margin-left: 8px; color: #909399">1 USD = ? RMB</span>
      </el-form-item>
      <el-form-item label="订单处理费阈值 (kg)">
        <el-input-number v-model="params.order_fee_threshold_kg" :precision="1" :step="0.1" :min="0" />
      </el-form-item>
      <el-form-item label="阈值以下 (RMB)">
        <el-input-number v-model="params.order_fee_light" :precision="2" :step="0.5" :min="0" />
      </el-form-item>
      <el-form-item label="阈值以上 (RMB)">
        <el-input-number v-model="params.order_fee_heavy" :precision="2" :step="0.5" :min="0" />
      </el-form-item>
      <el-form-item label="提现手续费率">
        <el-input-number v-model="params.withdrawal_rate" :precision="4" :step="0.001" :min="0" :max="1" />
        <span style="margin-left: 8px; color: #909399">0.015 = 1.5%</span>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import api from '../../api'
import { ElMessage } from 'element-plus'

const params = reactive({
  rate_rub_cny: 0.08,
  rate_usd_cny: 7.2,
  order_fee_threshold_kg: 2,
  order_fee_light: 6,
  order_fee_heavy: 10,
  withdrawal_rate: 0.015,
})
const loading = ref(false)
const saving = ref(false)

async function fetchParams() {
  loading.value = true
  try {
    const { data } = await api.get('/api/pricing/params')
    Object.assign(params, data)
  } catch {
    ElMessage.error('加载参数失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await api.put('/api/pricing/params', params)
    ElMessage.success('参数已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(fetchParams)
</script>
