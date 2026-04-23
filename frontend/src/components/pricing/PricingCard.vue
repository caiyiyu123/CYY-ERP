<template>
  <el-card shadow="hover">
    <div>
      <strong>{{ form.name || '(未命名)' }}</strong>
      <span style="margin-left: 8px; color: #909399">SKU: {{ form.sku || '-' }}</span>
    </div>
    <div style="margin-top: 8px; color: #c0c4cc; font-size: 13px">
      (定价卡片 Task 11/12 实现中)
    </div>
    <div style="margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px">
      <el-button v-if="isDraft" size="small" @click="$emit('cancel')">取消草稿</el-button>
      <el-button v-if="!isDraft" size="small" type="danger" link @click="$emit('deleted')">删除</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { reactive } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  params: { type: Object, required: true },
  shippingRates: { type: Array, required: true },
  isDraft: { type: Boolean, default: false },
})
defineEmits(['saved', 'deleted', 'cancel'])

const form = reactive(JSON.parse(JSON.stringify(props.item)))
</script>
