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

      <!-- 右侧: 定价区 (Task 12 实现) -->
      <el-col :span="14">
        <div style="border-left: 1px solid #ebeef5; padding-left: 16px; min-height: 300px; color: #909399">
          WB 跨境 FBS 定价区 (Task 12 实现)
          <div style="margin-top: 12px; font-size: 12px">
            body { calc 已就绪, 可参考 }:<br/>
            体积 {{ calc.volume }}, 密度 {{ calc.density }}, 利润 {{ calc.profit }}
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
const productOptions = ref([])
const productLoading = ref(false)

async function searchProducts(query) {
  if (!query) { productOptions.value = []; return }
  productLoading.value = true
  try {
    const { data } = await api.get('/api/products', {
      params: { page: 1, page_size: 20, search: query },
    })
    productOptions.value = data.products || data.items || []
  } catch { productOptions.value = [] } finally { productLoading.value = false }
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
</script>
