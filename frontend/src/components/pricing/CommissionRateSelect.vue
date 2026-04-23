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
      :label="`${r.category} / ${r.product_name} (${(r.rate * 100).toFixed(2)}%)`"
      :value="r.id"
    />
  </el-select>
</template>

<script setup>
import { ref } from 'vue'
import api from '../../api'

const props = defineProps({
  modelValue: { type: Number, default: null },
  platform: { type: String, required: true },
})
defineEmits(['update:modelValue'])

const options = ref([])
const loading = ref(false)

async function search(query) {
  if (!query) { options.value = []; return }
  loading.value = true
  try {
    const { data } = await api.get('/api/commission/rates', {
      params: { platform: props.platform, product: query, page: 1, page_size: 30 },
    })
    options.value = data.rates || []
  } catch { options.value = [] } finally { loading.value = false }
}
</script>
