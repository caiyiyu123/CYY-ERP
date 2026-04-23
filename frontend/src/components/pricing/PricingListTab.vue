<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <el-input
        v-model="search"
        placeholder="搜索 SKU 或商品名称"
        style="width: 300px"
        clearable
        @clear="fetchItems"
        @keyup.enter="fetchItems"
      />
      <el-button type="primary" @click="addDraft">新增定价方案</el-button>
    </div>

    <el-empty v-if="!loading && items.length === 0 && !hasDraft" description="暂无定价方案,点右上角新增" />

    <div v-loading="loading" style="display: flex; flex-direction: column; gap: 8px">
      <PricingCard
        v-for="it in items"
        :key="it.id"
        :item="it"
        :params="params"
        :shipping-rates="shippingRates"
        @saved="fetchItems"
        @deleted="fetchItems"
      />
      <PricingCard
        v-if="draftItem"
        :item="draftItem"
        :params="params"
        :shipping-rates="shippingRates"
        :is-draft="true"
        @saved="onDraftSaved"
        @cancel="draftItem = null"
      />
    </div>

    <el-pagination
      v-if="total > pageSize"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="p => { page = p; fetchItems() }"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api'
import { ElMessage } from 'element-plus'
import PricingCard from './PricingCard.vue'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const loading = ref(false)

const params = ref({})
const shippingRates = ref([])

const draftItem = ref(null)
const hasDraft = computed(() => !!draftItem.value)

function emptyItem() {
  return {
    id: null,
    name: '',
    sku: '',
    product_id: null,
    image_url: '',
    purchase_cost: 0,
    weight_kg: 0,
    length_cm: 0, width_cm: 0, height_cm: 0,
    wb_local_rate_id: null,
    wb_cross_rate_id: null,
    ozon_local_rate_id: null,
    platforms: [{ platform: 'wb_cross_fbs', price_rub: 0, price_rmb: 0, discount_pct: 0, extra: {} }],
  }
}

function addDraft() {
  if (draftItem.value) return
  draftItem.value = emptyItem()
}

function onDraftSaved() {
  draftItem.value = null
  fetchItems()
}

async function fetchItems() {
  loading.value = true
  try {
    const { data } = await api.get('/api/pricing/items', {
      params: { page: page.value, page_size: pageSize.value, search: search.value },
    })
    items.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('加载定价列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchParams() {
  try {
    const { data } = await api.get('/api/pricing/params')
    params.value = data
  } catch { /* 用默认 */ }
}

async function fetchDefaultShipping() {
  try {
    const { data: d } = await api.get('/api/shipping/default-template')
    if (!d.id) return
    const { data: templates } = await api.get('/api/shipping/templates')
    const tpl = templates.find(t => t.id === d.id)
    if (tpl) shippingRates.value = tpl.rates || []
  } catch { /* 没配默认模板, shippingRates 保持 [] */ }
}

onMounted(async () => {
  await Promise.all([fetchParams(), fetchDefaultShipping()])
  await fetchItems()
})
</script>
