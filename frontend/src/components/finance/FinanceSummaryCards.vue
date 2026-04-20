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
      <div class="ts-card-title">订单利润</div>
      <div class="ts-card-val" :style="{ color: summary.total_net_profit >= 0 ? '#16a34a' : '#dc2626' }">
        {{ fmt(summary.total_net_profit) }} {{ symbol }}
      </div>
    </el-card></el-col>
    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
      <div class="ts-card-title">非订单费用</div>
      <div class="ts-card-val">{{ fmt(summary.total_other_fees) }} {{ symbol }}</div>
    </el-card></el-col>
    <el-col :span="6" style="margin-top: 12px"><el-card class="ts-card">
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
function fmt(v) {
  if (v === null || v === undefined) return '0.00'
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<style scoped>
.ts-card { text-align: center; }
.ts-card-title { font-size: 12px; color: #64748b; margin-bottom: 6px; }
.ts-card-val { font-size: 20px; font-weight: 600; color: #1e293b; }
</style>
