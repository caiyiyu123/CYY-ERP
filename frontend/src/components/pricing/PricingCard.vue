<template>
  <el-card shadow="hover">
    <el-row :gutter="16">
      <!-- 左侧: 商品信息 -->
      <el-col :span="10">
        <div style="display: flex; gap: 12px; margin-bottom: 12px">
          <el-input v-model="form.name" placeholder="方案名,例如 春季定价" style="flex: 1" />
          <el-select
            v-model="form.product_id"
            placeholder="搜索 SKU (可留空)"
            filterable
            remote
            clearable
            :remote-method="searchProducts"
            :loading="productLoading"
            style="flex: 1"
            @change="onProductChange"
          >
            <el-option
              v-for="p in productOptions"
              :key="p.id"
              :label="`${p.sku} ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </div>

        <div style="display: flex; gap: 12px; align-items: flex-start">
          <!-- 图片 -->
          <div style="width: 80px; height: 80px; border: 1px dashed #dcdfe6; display: flex; align-items: center; justify-content: center; overflow: hidden">
            <el-image
              v-if="form.image_url"
              :src="imgUrl(form.image_url)"
              fit="contain"
              style="width: 100%; height: 100%"
            />
            <span v-else style="color: #ccc; font-size: 12px">无图</span>
          </div>

          <el-form label-width="80px" label-position="top" style="flex: 1">
            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="采购成本 (¥)">
                  <el-input-number v-model="form.purchase_cost" :precision="2" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="重量 (kg)">
                  <el-input-number v-model="form.weight_kg" :precision="3" :step="0.1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="8">
              <el-col :span="8">
                <el-form-item label="长 (cm)">
                  <el-input-number v-model="form.length_cm" :precision="1" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="宽 (cm)">
                  <el-input-number v-model="form.width_cm" :precision="1" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="高 (cm)">
                  <el-input-number v-model="form.height_cm" :precision="1" :step="1" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <div style="color: #909399; font-size: 13px; margin-top: 4px">
              体积 {{ calc.volume != null ? calc.volume.toFixed(4) : '-' }} m³
              | 密度 {{ calc.density != null ? calc.density.toFixed(2) : '-' }} kg/m³
            </div>
          </el-form>
        </div>

        <!-- 三个类目 -->
        <el-form label-width="100px" style="margin-top: 12px">
          <el-form-item label="WB 本土类目">
            <CommissionRateSelect v-model="form.wb_local_rate_id" platform="wb_local" />
          </el-form-item>
          <el-form-item label="WB 跨境类目">
            <CommissionRateSelect v-model="form.wb_cross_rate_id" platform="wb_cross_border" />
          </el-form-item>
          <el-form-item label="OZON 本土类目">
            <CommissionRateSelect v-model="form.ozon_local_rate_id" platform="ozon_local" />
          </el-form-item>
        </el-form>
      </el-col>

      <el-col :span="14">
        <div style="border-left: 1px solid #ebeef5; padding-left: 16px">
          <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px; color: #303133">
            WB 跨境 FBS
          </div>

          <!-- 第 1 行: 定价双向 + 折扣 -->
          <el-row :gutter="12">
            <el-col :span="8">
              <label style="font-size: 12px; color: #606266">定价 (RUB)</label>
              <el-input
                :model-value="platform0.price_rub"
                type="number"
                step="1"
                size="default"
                @input="onChangeRub"
              />
            </el-col>
            <el-col :span="8">
              <label style="font-size: 12px; color: #606266">定价 (RMB)</label>
              <el-input
                :model-value="platform0.price_rmb"
                type="number"
                step="0.1"
                size="default"
                @input="onChangeRmb"
              />
            </el-col>
            <el-col :span="8">
              <label style="font-size: 12px; color: #606266">平台折扣 (%)</label>
              <el-input-number
                v-model="platform0.discount_pct"
                :precision="1" :step="1" :min="0" :max="100"
                style="width: 100%"
              />
            </el-col>
          </el-row>

          <!-- 第 2 行: 派生字段 -->
          <el-descriptions :column="2" border size="small" style="margin-top: 12px">
            <el-descriptions-item label="前台售价 (RUB)">
              {{ fmt(calc.frontPriceRub, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="头程单价 (USD)">
              {{ fmt(calc.headPriceUsd, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="头程费用 (¥)">
              {{ fmt(calc.headFee, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="订单处理费 (¥)">
              {{ fmt(calc.orderFee, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="尾程运费 (¥)">
              {{ fmt(calc.tailFee, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="佣金率 (%)">
              {{ fmt(calc.commissionRatePct, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="佣金 (¥)">
              {{ fmt(calc.commission, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="提现手续费 (¥)">
              {{ fmt(calc.withdrawalFee, 2) }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- 利润汇总 -->
          <div style="margin-top: 12px; padding: 10px; background: #f5f7fa; border-radius: 4px; display: flex; justify-content: space-around">
            <div>
              <div style="font-size: 12px; color: #909399">利润 (¥)</div>
              <div style="font-size: 18px; font-weight: 600" :style="{ color: profitColor }">
                {{ fmt(calc.profit, 2) }}
              </div>
            </div>
            <div>
              <div style="font-size: 12px; color: #909399">利润率</div>
              <div style="font-size: 18px; font-weight: 600" :style="{ color: profitColor }">
                {{ calc.profitRatePct != null ? calc.profitRatePct.toFixed(1) + '%' : '-' }}
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <div style="margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px">
      <el-button v-if="isDraft" @click="$emit('cancel')">取消</el-button>
      <el-popconfirm v-if="!isDraft" title="确定删除此方案?" @confirm="remove">
        <template #reference>
          <el-button type="danger" link>删除</el-button>
        </template>
      </el-popconfirm>
      <el-button type="primary" :loading="saving" @click="save">{{ isDraft ? '保存' : '更新' }}</el-button>
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
  if (!query) { productOptions.value = []; return }
  await loadAllProducts()
  const q = query.toLowerCase()
  productOptions.value = allProducts.value.filter(p =>
    (p.sku || '').toLowerCase().includes(q) ||
    (p.name || '').toLowerCase().includes(q)
  ).slice(0, 20)
}

async function onProductChange(productId) {
  if (!productId) return
  const p = productOptions.value.find(x => x.id === productId)
  if (p) {
    form.sku = p.sku || form.sku
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
