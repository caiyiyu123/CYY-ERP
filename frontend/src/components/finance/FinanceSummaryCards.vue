<template>
  <el-row :gutter="12" v-loading="loading">
    <el-col :span="6"><el-card class="ts-card">
      <div class="ts-card-title">订单数</div>
      <div class="ts-card-val">{{ summary.order_count }}</div>
    </el-card></el-col>
    <el-col :span="6"><el-card class="ts-card">
      <div class="ts-card-title">应付卖家</div>
      <div class="ts-card-val">{{ fmt(summary.total_net_to_seller) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6"><el-card class="ts-card">
      <div class="ts-card-title">佣金</div>
      <div class="ts-card-val">{{ fmt(summary.total_commission) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6"><el-card class="ts-card">
      <div class="ts-card-title">配送费</div>
      <div class="ts-card-val">{{ fmt(summary.total_delivery_fee) }} {{ symbol }}</div>
    </el-card></el-col>

    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">采购成本</div>
      <div class="ts-card-val">{{ fmt(summary.total_purchase_cost) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">仓储</div>
      <div class="ts-card-val">{{ fmt(byType.storage) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">罚款</div>
      <div class="ts-card-val">{{ fmt(byType.fine) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">扣款</div>
      <div class="ts-card-val">{{ fmt(byType.deduction) }} {{ symbol }}</div>
    </el-card></el-col>

    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">物流调整</div>
      <div class="ts-card-val">{{ fmt(byType.logistics_adjust) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">其他</div>
      <div class="ts-card-val">{{ fmt(byType.other) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="12" style="margin-top: 12px"><el-card class="ts-card ts-card-final">
      <div class="ts-card-title">最终利润</div>
      <div class="ts-card-val" :style="{ color: summary.final_profit >= 0 ? '#16a34a' : '#dc2626', fontWeight: 700 }">
        {{ fmt(summary.final_profit) }} {{ symbol }}
      </div>
    </el-card></el-col>
  </el-row>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  summary: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})
const symbol = computed(() => props.summary.currency === 'CNY' ? '¥' : '₽')
const byType = computed(() => props.summary.other_fees_by_type || {
  storage: 0, fine: 0, deduction: 0, logistics_adjust: 0, other: 0,
})
function fmt(v) {
  if (v === null || v === undefined) return '0.00'
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<style scoped>
.ts-card { text-align: center; }
.ts-card-title { font-size: 12px; color: #64748b; margin-bottom: 6px; }
.ts-card-val { font-size: 20px; font-weight: 600; color: #1e293b; }
.ts-card-final .ts-card-val { font-size: 22px; }
</style>
