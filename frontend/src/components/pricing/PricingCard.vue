<template>
  <el-card shadow="hover" class="pricing-card" :body-style="{ padding: '10px' }">
    <!-- ========== 顶部:商品信息区 (Excel 风格表格) ========== -->
    <div class="product-info">
      <!-- 左侧:图片 -->
      <div class="product-img-cell">
        <el-image
          v-if="form.image_url"
          :src="imgUrl(form.image_url)"
          fit="contain"
          style="width: 100%; height: 100%"
        />
        <span v-else class="no-img">无图</span>
      </div>

      <!-- 右侧:信息表格 -->
      <div class="info-table">
        <!-- 第 1 组:类目 + 体积/密度 -->
        <div class="info-row header">
          <div class="info-cell">WB本土类目</div>
          <div class="info-cell">WB跨境类目</div>
          <div class="info-cell">OZON本土类目</div>
          <div class="info-cell">体积 (m³)</div>
          <div class="info-cell">密度 (kg/m³)</div>
        </div>
        <div class="info-row">
          <div class="info-cell"><CommissionRateSelect v-model="form.wb_local_rate_id" platform="wb_local" /></div>
          <div class="info-cell"><CommissionRateSelect v-model="form.wb_cross_rate_id" platform="wb_cross_border" /></div>
          <div class="info-cell"><CommissionRateSelect v-model="form.ozon_local_rate_id" platform="ozon_local" /></div>
          <div class="info-cell readonly">{{ calc.volume != null ? calc.volume.toFixed(4) : '-' }}</div>
          <div class="info-cell readonly">{{ calc.density != null ? calc.density.toFixed(2) : '-' }}</div>
        </div>

        <!-- 第 2 组:采购成本 + 尺寸 -->
        <div class="info-row header">
          <div class="info-cell">采购成本 (¥)</div>
          <div class="info-cell">重量 (kg)</div>
          <div class="info-cell">长 (cm)</div>
          <div class="info-cell">宽 (cm)</div>
          <div class="info-cell">高 (cm)</div>
        </div>
        <div class="info-row">
          <div class="info-cell"><el-input-number v-model="form.purchase_cost" :precision="2" :step="1" :min="0" size="small" :controls="false" /></div>
          <div class="info-cell"><el-input-number v-model="form.weight_kg" :precision="3" :step="0.1" :min="0" size="small" :controls="false" /></div>
          <div class="info-cell"><el-input-number v-model="form.length_cm" :precision="1" :step="1" :min="0" size="small" :controls="false" /></div>
          <div class="info-cell"><el-input-number v-model="form.width_cm" :precision="1" :step="1" :min="0" size="small" :controls="false" /></div>
          <div class="info-cell"><el-input-number v-model="form.height_cm" :precision="1" :step="1" :min="0" size="small" :controls="false" /></div>
        </div>
      </div>
    </div>

    <!-- ========== 商品名称 + SKU 一行 ========== -->
    <div class="name-sku-row">
      <span class="label">商品名称</span>
      <el-input v-model="form.name" size="small" placeholder="商品名称" />
      <span class="label">SKU</span>
      <el-select
        v-model="form.product_id"
        size="small"
        placeholder="搜索 SKU (可留空)"
        filterable
        remote
        clearable
        :remote-method="searchProducts"
        :loading="productLoading"
        @change="onProductChange"
      >
        <el-option v-for="p in productOptions" :key="p.id" :label="p.sku" :value="p.id">
          <span>{{ p.sku }}</span>
          <span style="color: #909399; margin-left: 8px; font-size: 12px">{{ p.name }}</span>
        </el-option>
      </el-select>
    </div>

    <!-- ========== 定价行表格 ========== -->
    <div class="pricing-table-wrap">
      <table class="pricing-table">
        <thead>
          <tr>
            <th class="platform-col">平台</th>
            <th>定价 (RUB)</th>
            <th>定价 (RMB)</th>
            <th>平台折扣</th>
            <th class="highlight">前台售价 (RUB)</th>
            <th>利润 (¥)</th>
            <th>利润率</th>
            <th>头程单价 (USD)</th>
            <th>头程费用 (¥)</th>
            <th>订单处理费 (¥)</th>
            <th>尾程运费 (¥)</th>
            <th>佣金率 (%)</th>
            <th>佣金 (¥)</th>
            <th>提现手续费 (¥)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="platform-col">WB 跨境 FBS</td>
            <td><el-input :model-value="platform0.price_rub" type="number" size="small" @input="onChangeRub" /></td>
            <td><el-input :model-value="platform0.price_rmb" type="number" size="small" @input="onChangeRmb" /></td>
            <td><el-input-number v-model="platform0.discount_pct" :precision="1" :step="1" :min="0" :max="100" size="small" :controls="false" /></td>
            <td class="highlight">{{ fmt(calc.frontPriceRub, 2) }}</td>
            <td :style="{ color: profitColor, fontWeight: 600 }">{{ fmt(calc.profit, 2) }}</td>
            <td :style="{ color: profitColor, fontWeight: 600 }">{{ calc.profitRatePct != null ? calc.profitRatePct.toFixed(1) + '%' : '-' }}</td>
            <td>{{ fmt(calc.headPriceUsd, 2) }}</td>
            <td>{{ fmt(calc.headFee, 2) }}</td>
            <td>{{ fmt(calc.orderFee, 2) }}</td>
            <td>{{ fmt(calc.tailFee, 2) }}</td>
            <td>{{ fmt(calc.commissionRatePct, 2) }}</td>
            <td>{{ fmt(calc.commission, 2) }}</td>
            <td>{{ fmt(calc.withdrawalFee, 2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ========== 操作栏 ========== -->
    <div class="action-bar">
      <el-button v-if="isDraft" size="small" @click="$emit('cancel')">取消</el-button>
      <el-popconfirm v-if="!isDraft" title="确定删除此方案?" @confirm="remove">
        <template #reference>
          <el-button size="small" type="danger" link>删除</el-button>
        </template>
      </el-popconfirm>
      <el-button type="primary" size="small" :loading="saving" @click="save">{{ isDraft ? '保存' : '更新' }}</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import api from '../../api'
import { ElMessage } from 'element-plus'
import { usePricingCalc } from '../../composables/usePricingCalc.js'
import CommissionRateSelect from './CommissionRateSelect.vue'

const props = defineProps({
  item: { type: Object, required: true },
  params: { type: Object, required: true },
  shippingRates: { type: Array, required: true },
  isDraft: { type: Boolean, default: false },
})

const emit = defineEmits(['saved', 'deleted', 'cancel'])

const form = reactive(JSON.parse(JSON.stringify(props.item)))
const saving = ref(false)

// WB 跨境佣金率对象 (按 id 单独 fetch,用于 usePricingCalc 计算)
const wbCrossRate = ref(null)
watch(() => form.wb_cross_rate_id, async (id) => {
  if (!id) { wbCrossRate.value = null; return }
  try {
    const { data } = await api.get(`/api/pricing/rate/${id}`)
    wbCrossRate.value = data
  } catch { wbCrossRate.value = null }
}, { immediate: true })

// ======== SKU/Product 搜索 ========
// 后端 /api/products 直接返回全量数组,无分页和搜索参数,前端本地过滤
const productOptions = ref([])
const productLoading = ref(false)
const allProducts = ref([])

async function loadAllProducts() {
  if (allProducts.value.length > 0) return
  productLoading.value = true
  try {
    const { data } = await api.get('/api/products')
    allProducts.value = Array.isArray(data) ? data : []
  } catch { allProducts.value = [] } finally { productLoading.value = false }
}

async function searchProducts(query) {
  if (!query) {
    // 清空输入时保留当前选中项,避免 label 丢失
    const current = productOptions.value.find(p => p.id === form.product_id)
    productOptions.value = current ? [current] : []
    return
  }
  await loadAllProducts()
  const q = query.toLowerCase()
  const matched = allProducts.value.filter(p =>
    (p.sku || '').toLowerCase().includes(q) ||
    (p.name || '').toLowerCase().includes(q)
  ).slice(0, 20)
  const currentProduct = productOptions.value.find(p => p.id === form.product_id)
  if (currentProduct && !matched.some(p => p.id === currentProduct.id)) {
    productOptions.value = [currentProduct, ...matched]
  } else {
    productOptions.value = matched
  }
}

// 初始化: 如果 item 带有 product_id, 主动 fetch 对应 product 填入 options
// 否则刷新后 el-select 只显示原始数字 id
async function ensureInitialProduct(id) {
  if (!id) return
  if (productOptions.value.some(p => p.id === id)) return
  await loadAllProducts()
  const p = allProducts.value.find(x => x.id === id)
  if (p) productOptions.value = [p, ...productOptions.value]
}

watch(() => form.product_id, (id) => ensureInitialProduct(id), { immediate: true })

async function onProductChange(productId) {
  if (!productId) return
  const p = productOptions.value.find(x => x.id === productId)
  if (p) {
    form.sku = p.sku || form.sku
    form.name = p.name || form.name
    form.image_url = p.image || p.image_url || ''
    form.purchase_cost = p.purchase_price || 0
    form.weight_kg = p.weight || 0
    form.length_cm = p.length || 0
    form.width_cm = p.width || 0
    form.height_cm = p.height || 0
  }
}

// ======== 计算 (platform0 是第一条 platform - 本期只有 wb_cross_fbs) ========
const platform0 = computed(() => form.platforms[0] || {})

const calc = usePricingCalc(
  computed(() => form),
  platform0,
  computed(() => props.params),
  wbCrossRate,
  computed(() => props.shippingRates),
)

// ======== 保存/删除 ========
async function save() {
  saving.value = true
  try {
    const payload = { ...form }
    if (props.isDraft) {
      await api.post('/api/pricing/items', payload)
      ElMessage.success('保存成功')
    } else {
      await api.put(`/api/pricing/items/${form.id}`, payload)
      ElMessage.success('更新成功')
    }
    emit('saved')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally { saving.value = false }
}

async function remove() {
  try {
    await api.delete(`/api/pricing/items/${form.id}`)
    ElMessage.success('已删除')
    emit('deleted')
  } catch { ElMessage.error('删除失败') }
}

function imgUrl(u) {
  if (!u) return ''
  if (u.startsWith('http')) return u
  return u
}

// ======== 双向换算 + 格式化 ========

function onChangeRub(v) {
  const num = Number(v) || 0
  form.platforms[0].price_rub = num
  form.platforms[0].price_rmb = props.params.rate_rub_cny
    ? Number((num * props.params.rate_rub_cny).toFixed(2))
    : 0
}

function onChangeRmb(v) {
  const num = Number(v) || 0
  form.platforms[0].price_rmb = num
  form.platforms[0].price_rub = props.params.rate_rub_cny
    ? Number((num / props.params.rate_rub_cny).toFixed(2))
    : 0
}

function fmt(v, digits = 2) {
  return v == null || Number.isNaN(v) ? '-' : Number(v).toFixed(digits)
}

const profitColor = computed(() => {
  const p = calc.value.profit
  if (p == null) return '#909399'
  return p >= 0 ? '#67c23a' : '#f56c6c'
})
</script>

<style scoped>
.pricing-card {
  font-size: 12px;
}

/* ========== 商品信息区 ========== */
.product-info {
  display: flex;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.product-img-cell {
  width: 100px;
  flex-shrink: 0;
  background: #f5f7fa;
  border-right: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}

.no-img {
  color: #c0c4cc;
  font-size: 12px;
}

.info-table {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.info-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  border-bottom: 1px solid #ebeef5;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row.header {
  background: #f5f7fa;
  font-size: 11px;
  color: #606266;
  font-weight: 500;
}

.info-cell {
  padding: 1px 4px;
  border-right: 1px solid #ebeef5;
  font-size: 12px;
  min-height: 24px;
  display: flex;
  align-items: center;
}

.info-cell:last-child {
  border-right: none;
}

.info-cell.readonly {
  color: #303133;
  font-weight: 500;
  background: #fafafa;
}

/* 让输入组件占满单元格 */
.info-cell :deep(.el-input),
.info-cell :deep(.el-select),
.info-cell :deep(.el-input-number) {
  width: 100%;
}

/* ========== 商品名称 + SKU 行 ========== */
.name-sku-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.name-sku-row .label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  white-space: nowrap;
}

.name-sku-row .el-input,
.name-sku-row .el-select {
  flex: 1;
}

/* ========== 定价行表格 ========== */
.pricing-table-wrap {
  overflow-x: auto;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  margin-bottom: 6px;
}

.pricing-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.pricing-table th,
.pricing-table td {
  border: 1px solid #ebeef5;
  padding: 3px 4px;
  text-align: center;
  white-space: nowrap;
  min-width: 72px;
}

.pricing-table th {
  background: #e7f0fe;
  color: #303133;
  font-weight: 500;
  font-size: 11px;
  line-height: 1.3;
}

.pricing-table td {
  color: #303133;
}

.pricing-table th.highlight,
.pricing-table td.highlight {
  background: #fff7d6;
  font-weight: 600;
}

.pricing-table .platform-col {
  background: #ede7f6;
  color: #6b4ea0;
  font-weight: 600;
  min-width: 100px;
}

.pricing-table thead .platform-col {
  background: #e7f0fe;
  color: #303133;
}

/* 表格内输入框紧凑化 */
.pricing-table :deep(.el-input),
.pricing-table :deep(.el-input-number) {
  width: 100%;
}

.pricing-card :deep(.el-input__wrapper) {
  padding: 0 6px;
  box-shadow: 0 0 0 1px transparent inset;
}

.pricing-card :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c0c4cc inset;
}

/* 取消 el-input-number 的加减按钮后让输入居中对齐 */
.pricing-card :deep(.el-input-number .el-input__inner) {
  text-align: center;
  padding: 0 4px;
}

/* 整体输入框缩小高度 */
.pricing-card :deep(.el-input--small),
.pricing-card :deep(.el-input-number--small),
.pricing-card :deep(.el-select--small .el-input) {
  --el-component-size: 24px;
}
.pricing-card :deep(.el-input--small .el-input__wrapper),
.pricing-card :deep(.el-input-number--small .el-input__wrapper) {
  min-height: 24px;
}

/* ========== 操作栏 ========== */
.action-bar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
