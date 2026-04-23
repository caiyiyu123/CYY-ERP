<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    placeholder="搜索商品名"
    :remote-method="search"
    :loading="loading"
    style="width: 100%"
    @update:model-value="v => $emit('update:modelValue', v)"
  >
    <el-option
      v-for="r in options"
      :key="r.id"
      :label="`${r.product_name} (${(r.rate * 100).toFixed(2)}%)`"
      :value="r.id"
    >
      <span style="color: #909399; font-size: 12px">{{ r.category }}</span>
      <span style="margin-left: 8px">{{ r.product_name }}</span>
      <span style="color: #409eff; margin-left: 8px; font-size: 12px">{{ (r.rate * 100).toFixed(2) }}%</span>
    </el-option>
  </el-select>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../../api'

const props = defineProps({
  modelValue: { type: Number, default: null },
  platform: { type: String, required: true },
})
defineEmits(['update:modelValue'])

const options = ref([])
const loading = ref(false)

// 初始 fetch: 如果外部传入了 modelValue, 主动取出对应 rate 以显示 label
// 否则刷新后 options 为空, el-select 会直接展示原始数字 id
async function ensureInitialOption(id) {
  if (!id) return
  if (options.value.some(r => r.id === id)) return
  try {
    const { data } = await api.get(`/api/pricing/rate/${id}`)
    options.value = [data, ...options.value]
  } catch { /* ignore */ }
}

watch(() => props.modelValue, (id) => ensureInitialOption(id), { immediate: true })

async function search(query) {
  if (!query) {
    // 清空输入时保留当前选中项,避免 label 丢失
    const current = options.value.find(r => r.id === props.modelValue)
    options.value = current ? [current] : []
    return
  }
  loading.value = true
  try {
    const { data } = await api.get('/api/commission/rates', {
      params: { platform: props.platform, product: query, page: 1, page_size: 30 },
    })
    const fetched = data.rates || []
    const currentRate = options.value.find(r => r.id === props.modelValue)
    if (currentRate && !fetched.some(r => r.id === currentRate.id)) {
      options.value = [currentRate, ...fetched]
    } else {
      options.value = fetched
    }
  } catch { options.value = [] } finally { loading.value = false }
}
</script>
